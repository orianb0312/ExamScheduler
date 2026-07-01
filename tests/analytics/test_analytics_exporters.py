from __future__ import annotations

import json
from datetime import date

import pytest

from src.analytics.exporters import AnalyticsExportService
from src.analytics.models import AnalyticsCohort, AnalyticsExam
from src.analytics.schedule_analytics import ScheduleAnalyticsEngine
from src.sorting.schedule_priority import MAX_DAILY_EXAMS


def test_json_text_and_csv_exporters_write_diagnostic_files(tmp_path) -> None:
    report = ScheduleAnalyticsEngine().analyze(
        (
            AnalyticsExam(
                course_name="A Very Long Course Name That Should Still Wrap Cleanly",
                exam_date=date(2026, 1, 10),
                cohorts=(
                    AnalyticsCohort(
                        program_id=83101,
                        year=1,
                        requirement_type="Obligatory",
                    ),
                ),
            ),
        ),
        (MAX_DAILY_EXAMS,),
        schedule_label="Schedule",
        schedule_number=1,
    )

    paths = AnalyticsExportService().export(
        (report,),
        ("json", "txt", "csv"),
        tmp_path,
        "analytics_output",
    )

    assert {path.suffix for path in paths} == {".json", ".txt", ".csv"}
    payload = json.loads((tmp_path / "analytics_output.json").read_text(encoding="utf-8"))
    assert payload["calculation_mode"] == "deterministic_rules"
    assert payload["reports"][0]["metric_values"][0]["key"] == MAX_DAILY_EXAMS
    assert payload["reports"][0]["scheduled_exams"][0]["course_name"].startswith(
        "A Very Long"
    )
    assert payload["reports"][0]["cross_sectional_insights"]
    assert payload["reports"][0]["functional_justification"]

    text = (tmp_path / "analytics_output.txt").read_text(encoding="utf-8")
    assert "DETERMINISTIC SCHEDULE ANALYTICS" in text
    assert "max_daily_exams" in text
    assert "Cross-sectional insights" in text
    assert "Functional justification" in text

    csv_text = (tmp_path / "analytics_output.csv").read_text(encoding="utf-8")
    assert "section,schedule_number,schedule_label" in csv_text
    assert "scheduled_exam" in csv_text
    assert "cross_sectional_insight" in csv_text
    assert "daily_density" in csv_text
    assert "bottleneck" in csv_text
    assert "functional_justification" in csv_text


def test_pdf_exporter_writes_reportlab_document(tmp_path) -> None:
    pytest.importorskip("reportlab")
    report = ScheduleAnalyticsEngine().analyze(
        (
            AnalyticsExam(
                course_name=(
                    "A Long Course Name For PDF Wrapping And Pagination Checks"
                ),
                exam_date=date(2026, 1, 10),
                cohorts=(
                    AnalyticsCohort(
                        program_id=83101,
                        year=1,
                        requirement_type="Obligatory",
                    ),
                ),
            ),
        ),
        (MAX_DAILY_EXAMS,),
        schedule_label="Schedule",
        schedule_number=1,
    )

    paths = AnalyticsExportService().export(
        (report,),
        ("pdf",),
        tmp_path,
        "analytics_output",
    )

    assert paths == [tmp_path / "analytics_output.pdf"]
    assert paths[0].read_bytes().startswith(b"%PDF")
