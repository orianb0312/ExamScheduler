from __future__ import annotations

from datetime import date

from src.services.schedule_calendar_service import ScheduleCalendarDataService
from src.services.schedule_output_service import (
    ScheduleExamDisplay,
    SchedulePeriodDisplay,
    ScheduleSystem,
)


def test_calendar_service_filters_by_period_label_and_date_range() -> None:
    service = ScheduleCalendarDataService()
    matching_exam = ScheduleExamDisplay(
        course_name="Algorithms",
        course_id=10001,
        exam_date=date(2026, 1, 2),
        instructor="Dr. Ada",
    )
    wrong_term_exam = ScheduleExamDisplay(
        course_name="Databases",
        course_id=10002,
        exam_date=date(2026, 1, 2),
        instructor="Dr. Codd",
    )
    stale_date_exam = ScheduleExamDisplay(
        course_name="Networks",
        course_id=10003,
        exam_date=date(2026, 2, 1),
        instructor="Dr. Tanenbaum",
    )
    schedule = ScheduleSystem(
        number=1,
        text="Schedule #1",
        periods=(
            SchedulePeriodDisplay(
                semester_label="FALL",
                term_label="Aleph",
                exams=(matching_exam, stale_date_exam),
            ),
            SchedulePeriodDisplay(
                semester_label="FALL",
                term_label="Bet",
                exams=(wrong_term_exam,),
            ),
        ),
    )

    exams = service.exams_for_period(
        schedule,
        semester_label=" fall ",
        term_label="ALEPH",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert exams == (matching_exam,)


def test_calendar_service_sorts_exams_inside_selected_period() -> None:
    service = ScheduleCalendarDataService()
    beta = ScheduleExamDisplay("Beta", date(2026, 1, 2), "Dr. B")
    alpha = ScheduleExamDisplay("Alpha", date(2026, 1, 2), "Dr. A")
    early = ScheduleExamDisplay("Early", date(2026, 1, 1), "Dr. E")
    schedule = ScheduleSystem(
        number=1,
        text="Schedule #1",
        periods=(
            SchedulePeriodDisplay(
                semester_label="FALL",
                term_label="Aleph",
                exams=(beta, alpha, early),
            ),
        ),
    )

    exams = service.exams_for_period(
        schedule,
        semester_label="FALL",
        term_label="Aleph",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert [exam.course_name for exam in exams] == ["Early", "Alpha", "Beta"]


def test_calendar_service_returns_empty_when_no_schedule_is_selected() -> None:
    service = ScheduleCalendarDataService()

    assert service.exams_for_period(
        None,
        semester_label="FALL",
        term_label="Aleph",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    ) == ()
