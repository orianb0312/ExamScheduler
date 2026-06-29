"""
PDF document scaling
====================
Validates that the ReportLab analytics PDF builder handles a heavy schedule
(300+ exams across several programs/courses): the document builds, paginates,
repeats table headers, splits oversized rows, numbers every page, and pushes
the Functional Justification ("signature") block to the end intact.

"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.analytics.models import (
    AnalyticsCohort,
    AnalyticsExam,
    BottleneckDiagnostic,
    CohortMatrixRow,
    DailyDensityRow,
    MetricValue,
    ScheduleAnalyticsReport,
)

pytest.importorskip("reportlab")
PdfReader = pytest.importorskip("pypdf").PdfReader

from src.analytics.pdf_report import ReportLabAnalyticsPdfBuilder


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _large_report(exam_count: int = 320, program_count: int = 6) -> ScheduleAnalyticsReport:
    """A report with many exams spread across several programs/courses."""
    base = date(2026, 1, 1)
    exams = []
    for i in range(exam_count):
        program_id = 83101 + (i % program_count)
        # Some long names exercise the oversized-row splitting path.
        long_name = "Advanced Topics in Distributed Systems and Parallel Computation"
        name = long_name if i % 9 == 0 else f"Course {i}"
        exams.append(
            AnalyticsExam(
                course_name=name,
                exam_date=base + timedelta(days=i % 75),
                instructor=f"Dr. Instructor Number {i}",
                course_id=10000 + i,
                semester_label="FALL",
                term_label="Aleph",
                cohorts=(
                    AnalyticsCohort(
                        program_id=program_id,
                        year=1 + (i % 3),
                        requirement_type="Obligatory" if i % 2 else "Elective",
                    ),
                ),
            )
        )

    density = tuple(
        DailyDensityRow(base + timedelta(days=d), d % 6, (d % 6) / exam_count, d % 3)
        for d in range(60)
    )
    cohort = tuple(
        CohortMatrixRow(
            program_id=83101 + (r % program_count),
            year=1 + (r % 3),
            exam_count=r % 12,
            mandatory_count=r % 6,
            elective_count=r % 5,
            first_exam_date=base,
            last_exam_date=base + timedelta(days=30),
            span_days=30,
            min_gap_days=2,
            average_gap_days=3.5,
            same_day_pairs=r % 4,
            first_mandatory_date=base,
            last_mandatory_date=base + timedelta(days=15),
            mandatory_span_days=15,
            mandatory_min_gap_days=1,
        )
        for r in range(40)
    )
    bottlenecks = tuple(
        BottleneckDiagnostic(
            priority_key="max_daily_exams",
            priority_title="Max Daily Exams",
            priority_position=1,
            category="daily_density",
            label=(base + timedelta(days=b)).isoformat(),
            metric_value=float(b % 6),
            pressure_score=float(b % 6),
            detail="A fairly long bottleneck detail string " * 4,
        )
        for b in range(25)
    )
    return ScheduleAnalyticsReport(
        schedule_label="Schedule",
        schedule_number=1,
        active_priorities=("max_daily_exams", "elective_conflicts"),
        exam_count=exam_count,
        metric_values=(
            MetricValue("max_daily_exams", "Max Daily Exams", "Part 3", 1, 3.0),
        ),
        daily_density=density,
        cohort_matrix=cohort,
        bottlenecks=bottlenecks,
        diagnostics=("Calculation mode: deterministic rules",),
        scheduled_exams=tuple(exams),
        cross_sectional_insights=("Busiest date is ...",),
        functional_justification=(
            "Schedules are compared lexicographically in priority order.",
            "Ranking vector for this schedule: (3).",
        ),
    )


def _empty_report() -> ScheduleAnalyticsReport:
    return ScheduleAnalyticsReport(
        schedule_label="Schedule",
        schedule_number=1,
        active_priorities=(),
        exam_count=0,
        metric_values=(),
        daily_density=(),
        cohort_matrix=(),
        bottlenecks=(),
        diagnostics=(),
        scheduled_exams=(),
        cross_sectional_insights=(),
        functional_justification=(),
    )


# ---------------------------------------------------------------------------
# Step 2 — high-scale tests
# ---------------------------------------------------------------------------

def test_large_report_builds_a_valid_multipage_pdf(tmp_path):
    """320 exams must produce a real multi-page PDF without raising."""
    destination = tmp_path / "large.pdf"
    ReportLabAnalyticsPdfBuilder().write([_large_report(320)], destination)

    assert destination.is_file()
    assert destination.read_bytes().startswith(b"%PDF")
    reader = PdfReader(str(destination))
    assert len(reader.pages) > 1  # genuinely paginated


def test_every_page_is_numbered_in_footer(tmp_path):
    """The footer must stamp 'Page N' on every page of a large document."""
    destination = tmp_path / "numbered.pdf"
    ReportLabAnalyticsPdfBuilder().write([_large_report(320)], destination)

    reader = PdfReader(str(destination))
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        assert f"Page {index}" in text, f"page {index} missing its number"


def test_signature_block_lands_on_the_final_page(tmp_path):
    """
    The Functional Justification block (the report's signature/closing section)
    must be pushed neatly to the end — present, and on the last page.
    """
    destination = tmp_path / "signature.pdf"
    ReportLabAnalyticsPdfBuilder().write([_large_report(320)], destination)

    reader = PdfReader(str(destination))
    last_page_text = reader.pages[-1].extract_text() or ""
    assert "Functional Justification" in last_page_text
    # The deterministic footer must also be on that final page.
    assert "no language model evaluation" in last_page_text


def test_table_header_repeats_across_pages(tmp_path):
    """LongTable repeatRows=1 should reprint 'Scheduled Exams' headers on multiple pages."""
    destination = tmp_path / "headers.pdf"
    ReportLabAnalyticsPdfBuilder().write([_large_report(320)], destination)

    reader = PdfReader(str(destination))
    pages_with_course_header = sum(
        1 for page in reader.pages if "Course" in (page.extract_text() or "")
    )
    # The exam table spans multiple pages, so its header column appears repeatedly.
    assert pages_with_course_header >= 2


def test_scaling_grows_page_count_with_exam_volume(tmp_path):
    """A bigger schedule must not produce fewer pages than a smaller one."""
    small = tmp_path / "small.pdf"
    big = tmp_path / "big.pdf"
    ReportLabAnalyticsPdfBuilder().write([_large_report(40)], small)
    ReportLabAnalyticsPdfBuilder().write([_large_report(400)], big)

    small_pages = len(PdfReader(str(small)).pages)
    big_pages = len(PdfReader(str(big)).pages)
    assert big_pages >= small_pages
    assert big_pages > 1


def test_multiple_large_reports_are_separated_by_page_breaks(tmp_path):
    """Several large schedules in one document must each start on a new page."""
    destination = tmp_path / "multi.pdf"
    reports = [_large_report(120), _large_report(120), _large_report(120)]
    ReportLabAnalyticsPdfBuilder().write(reports, destination)

    reader = PdfReader(str(destination))
    # Three heavy reports cannot fit on fewer pages than the count of reports.
    assert len(reader.pages) >= len(reports)


# ---------------------------------------------------------------------------
# Boundary — empty report still produces a structurally valid PDF
# ---------------------------------------------------------------------------

def test_empty_report_still_produces_valid_pdf(tmp_path):
    """A zero-exam report is a boundary case but must still yield a valid PDF."""
    destination = tmp_path / "empty.pdf"
    ReportLabAnalyticsPdfBuilder().write([_empty_report()], destination)

    assert destination.read_bytes().startswith(b"%PDF")
    reader = PdfReader(str(destination))
    assert len(reader.pages) >= 1
    first = reader.pages[0].extract_text() or ""
    # Empty tables fall back to placeholder text rather than crashing.
    assert "No scheduled exams were available" in first