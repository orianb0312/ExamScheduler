from __future__ import annotations
from datetime import date
import pytest

from src.models.enums import Semester, Term
from src.services.schedule_calendar_export_service import (
    CalendarExportError,
    ScheduleCalendarExportService,
)
from src.services.schedule_output_service import (
    ScheduleExamDisplay,
    SchedulePeriodDisplay,
    ScheduleSystem,
)


def _schedule(
        *,
        course_name: str = "Algorithms",
        course_id: int | None = 10001,
        exam_date: date | None = date(2026, 1, 10),
        semester_label: str = "FALL",
        term_label: str = "Aleph",
) -> ScheduleSystem:
    return ScheduleSystem(
        number=1,
        text="Schedule #1",
        periods=(
            SchedulePeriodDisplay(
                semester_label=semester_label,
                term_label=term_label,
                exams=(
                    ScheduleExamDisplay(
                        course_name=course_name,
                        course_id=course_id,
                        exam_date=exam_date,
                        instructor="Dr. Ada",
                    ),
                ),
            ),
        ),
    )


@pytest.fixture
def service(tmp_path) -> ScheduleCalendarExportService:
    return ScheduleCalendarExportService(tmp_path / "calendar")


def test_export_schedule_writes_publish_ics_and_updates_registry(service) -> None:
    result = service.export_schedule(_schedule())
    assert "METHOD:PUBLISH" in result.ics_content
    assert service.has_exported_entries()
    assert result.event_count == 1
    assert result.skipped_without_date == 0


def test_export_schedule_cancels_old_exams_not_in_new_schedule(service) -> None:
    # Export initial schedule
    service.export_schedule(_schedule(course_name="Algorithms", course_id=10001))

    # Export new schedule that replaces the old one
    result = service.export_schedule(_schedule(course_name="Databases", course_id=10002))

    # The formatter should PUBLISH the new and CANCEL the old in one file
    assert "METHOD:PUBLISH" in result.ics_content
    assert "STATUS:CANCELLED" in result.ics_content
    assert "STATUS:CONFIRMED" in result.ics_content
    assert "Algorithms" in result.ics_content
    assert "Databases" in result.ics_content


def test_revoke_all_exported_clears_registry(service) -> None:
    schedule = ScheduleSystem(
        number=1,
        text="Schedule #1",
        periods=(
            SchedulePeriodDisplay(
                semester_label="FALL",
                term_label="Aleph",
                exams=(
                    ScheduleExamDisplay(course_name="Alpha", course_id=1, exam_date=date(2026, 1, 10), instructor="A"),
                    ScheduleExamDisplay(course_name="Beta", course_id=2, exam_date=date(2026, 1, 11), instructor="B"),
                ),
            ),
        ),
    )
    service.export_schedule(schedule)
    result = service.revoke_all_exported()

    assert "METHOD:PUBLISH" in result.ics_content
    assert "STATUS:CANCELLED" in result.ics_content
    assert result.event_count == 2
    assert not service.has_exported_entries()


def test_revoke_all_exported_raises_when_registry_empty(service) -> None:
    with pytest.raises(CalendarExportError, match="No marked calendar entries"):
        service.revoke_all_exported()


def test_semester_and_term_labels_are_normalized(service) -> None:
    schedule = _schedule(semester_label=" fall ", term_label="ALEPH")
    result = service.export_schedule(schedule)
    assert result.event_count == 1

    assert "SUMMARY:Algorithms (10001)" in result.ics_content
    assert "DESCRIPTION:Exam: Algorithms (10001) - Aleph" in result.ics_content


def test_skips_exams_without_dates(service) -> None:
    schedule = ScheduleSystem(
        number=1,
        text="Schedule #1",
        periods=(
            SchedulePeriodDisplay(
                semester_label="FALL",
                term_label="Aleph",
                exams=(
                    ScheduleExamDisplay("No Date", None, "Dr. Ada", 10001),
                    ScheduleExamDisplay("With Date", date(2026, 1, 10), "Dr. Ada", 10002),
                ),
            ),
        ),
    )
    result = service.export_schedule(schedule)
    assert result.event_count == 1
    assert result.skipped_without_date == 1


def test_missing_course_id_uses_stable_fallback(service) -> None:
    first = service.export_schedule(_schedule(course_name="Philosophy", course_id=None))
    second = service.export_schedule(_schedule(course_name="Philosophy", course_id=None))

    first_uid = next(line for line in first.ics_content.splitlines() if line.startswith("UID:"))
    second_uid = next(line for line in second.ics_content.splitlines() if line.startswith("UID:"))
    assert first_uid == second_uid


def test_unknown_semester_label_raises(service) -> None:
    with pytest.raises(CalendarExportError, match="Unknown semester"):
        service.export_schedule(_schedule(semester_label="Winter"))