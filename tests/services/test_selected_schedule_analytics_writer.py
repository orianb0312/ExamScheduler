from __future__ import annotations

import json
from datetime import date

import pytest

from src.services.schedule_output_service import (
    ScheduleExamCohort,
    ScheduleExamDisplay,
    SchedulePeriodDisplay,
    ScheduleSystem,
)
from src.services.selected_schedule_analytics_writer import (
    SelectedScheduleAnalyticsWriter,
)
from src.sorting.schedule_priority import MAX_DAILY_EXAMS


def test_selected_schedule_analytics_writer_saves_json(tmp_path) -> None:
    writer = SelectedScheduleAnalyticsWriter()
    schedule = ScheduleSystem(
        number=2,
        text="raw schedule",
        periods=(
            SchedulePeriodDisplay(
                semester_label="FALL",
                term_label="Aleph",
                exams=(
                    ScheduleExamDisplay(
                        course_name="Algorithms",
                        course_id=10001,
                        exam_date=date(2026, 1, 10),
                        instructor="Dr. Ada",
                        cohorts=(
                            ScheduleExamCohort(
                                program_id=83101,
                                year=1,
                                requirement_type="Obligatory",
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    saved_path = writer.write(
        schedule,
        tmp_path / "selected_report",
        active_priorities=(MAX_DAILY_EXAMS,),
    )

    assert saved_path == tmp_path / "selected_report.json"
    payload = json.loads(saved_path.read_text(encoding="utf-8"))
    assert payload["reports"][0]["schedule_number"] == 2
    assert payload["reports"][0]["metric_values"][0]["key"] == MAX_DAILY_EXAMS


def test_selected_schedule_analytics_writer_rejects_missing_schedule(tmp_path) -> None:
    writer = SelectedScheduleAnalyticsWriter()

    with pytest.raises(ValueError, match="No schedule"):
        writer.write(None, tmp_path / "selected_report.json")

