from __future__ import annotations

from datetime import date

from src.analytics.models import AnalyticsCohort, AnalyticsExam
from src.analytics.schedule_analytics import ScheduleAnalyticsEngine
from src.sorting.schedule_priority import (
    ELECTIVE_CONFLICTS,
    MANDATORY_MIN_GAP,
    MAX_DAILY_EXAMS,
)


def _exam(
    day: int,
    course_name: str,
    *cohorts: AnalyticsCohort,
) -> AnalyticsExam:
    return AnalyticsExam(
        course_name=course_name,
        exam_date=date(2026, 1, day),
        instructor="Dr. Ada",
        cohorts=cohorts,
    )


def _cohort(program_id: int, year: int, requirement: str) -> AnalyticsCohort:
    return AnalyticsCohort(
        program_id=program_id,
        year=year,
        requirement_type=requirement,
    )


def test_analytics_engine_builds_density_and_priority_bottlenecks() -> None:
    report = ScheduleAnalyticsEngine().analyze(
        (
            _exam(1, "Algorithms", _cohort(83101, 1, "Obligatory")),
            _exam(3, "Databases", _cohort(83101, 1, "Obligatory")),
            _exam(3, "Graphics", _cohort(83102, 2, "Elective")),
            _exam(3, "Security", _cohort(83102, 2, "Elective")),
        ),
        (MANDATORY_MIN_GAP, ELECTIVE_CONFLICTS, MAX_DAILY_EXAMS),
        schedule_number=7,
    )

    assert report.exam_count == 4
    assert len(report.scheduled_exams) == 4
    assert [(row.exam_date.day, row.exam_count) for row in report.daily_density] == [
        (1, 1),
        (3, 3),
    ]
    assert report.daily_density[1].density_share == 0.75
    assert {metric.key: metric.value for metric in report.metric_values} == {
        MANDATORY_MIN_GAP: 2.0,
        ELECTIVE_CONFLICTS: 1.0,
        MAX_DAILY_EXAMS: 3.0,
    }

    cohort_rows = {
        (row.program_id, row.year): row
        for row in report.cohort_matrix
    }
    assert cohort_rows[(83101, 1)].mandatory_min_gap_days == 2
    assert cohort_rows[(83101, 1)].mandatory_span_days == 2
    assert cohort_rows[(83102, 2)].same_day_pairs == 1

    assert [row.priority_key for row in report.bottlenecks[:3]] == [
        MANDATORY_MIN_GAP,
        ELECTIVE_CONFLICTS,
        MAX_DAILY_EXAMS,
    ]
    assert report.calculation_mode == "deterministic_rules"
    assert any("Calculation mode: deterministic rules" in line for line in report.diagnostics)
    assert any("Busiest date" in line for line in report.cross_sectional_insights)
    assert any(
        "Ranking vector" in line
        for line in report.functional_justification
    )


def test_no_active_priorities_keeps_report_deterministic_but_quiet() -> None:
    report = ScheduleAnalyticsEngine().analyze(
        (_exam(5, "Algorithms", _cohort(83101, 1, "Obligatory")),),
        (),
    )

    assert report.metric_values == ()
    assert report.bottlenecks == ()
    assert len(report.daily_density) == 1
    assert report.diagnostics[2] == "Active priorities: none"
    assert "no Part 3 sorting priorities" in report.functional_justification[0]
