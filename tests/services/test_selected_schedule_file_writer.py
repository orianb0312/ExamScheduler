from __future__ import annotations

from datetime import date

import pytest

from src.services.schedule_output_service import (
    ScheduleExamDisplay,
    SchedulePeriodDisplay,
    ScheduleSystem,
)
from src.services.selected_schedule_file_writer import SelectedScheduleFileWriter


def test_selected_schedule_writer_saves_readable_text_file(tmp_path) -> None:
    writer = SelectedScheduleFileWriter()
    schedule = ScheduleSystem(
        number=3,
        text=(
            "Complete System #3\n"
            "=== SEMESTER: FALL ===\n"
            "  [TERM: Aleph]\n"
            "  Algorithms | 2026-01-10 | Dr. Ada\n"
        ),
    )

    saved_path = writer.write(schedule, tmp_path / "selected_schedule")

    assert saved_path == tmp_path / "selected_schedule.txt"
    content = saved_path.read_text(encoding="utf-8")
    assert "SELECTED EXAM SCHEDULE" in content
    assert "Complete System #3" in content
    assert "Algorithms | 2026-01-10 | Dr. Ada" in content


def test_selected_schedule_writer_rejects_missing_schedule(tmp_path) -> None:
    writer = SelectedScheduleFileWriter()

    with pytest.raises(ValueError, match="No schedule"):
        writer.write(None, tmp_path / "schedule.txt")


def test_selected_schedule_writer_uses_display_course_details_when_available(
    tmp_path,
) -> None:
    writer = SelectedScheduleFileWriter()
    schedule = ScheduleSystem(
        number=1,
        text="raw fallback text",
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
                        program_ids=(83101,),
                        requirement_types=("Obligatory",),
                    ),
                ),
            ),
        ),
    )

    saved_path = writer.write(schedule, tmp_path / "selected_schedule.txt")

    content = saved_path.read_text(encoding="utf-8")
    assert "Algorithms (10001) | 2026-01-10 | Dr. Ada" in content
    assert "Programs: 83101" in content
    assert "Requirements: Obligatory" in content
    assert "raw fallback text" not in content
