"""Prepare selected schedule data for calendar-style display."""

from __future__ import annotations

from datetime import date

from src.services.schedule_output_service import ScheduleExamDisplay, ScheduleSystem


class ScheduleCalendarDataService:
    """Find the exams from one selected schedule that belong to a calendar period."""

    def exams_for_period(
        self,
        selected_schedule: ScheduleSystem | None,
        semester_label: str,
        term_label: str,
        start_date: date,
        end_date: date,
    ) -> tuple[ScheduleExamDisplay, ...]:
        if selected_schedule is None:
            return ()

        exams: list[ScheduleExamDisplay] = []
        for period in selected_schedule.periods:
            if not _same_label(period.semester_label, semester_label):
                continue
            if not _same_label(period.term_label, term_label):
                continue

            # A period label is the main match, but the date range keeps a stale
            # or hand-edited output file from painting exams into the wrong panel.
            for exam in period.exams:
                if exam.exam_date is None:
                    continue
                if start_date <= exam.exam_date <= end_date:
                    exams.append(exam)

        return tuple(
            sorted(
                exams,
                key=lambda exam: (exam.exam_date, exam.course_name.casefold()),
            )
        )


def _same_label(left: str, right: str) -> bool:
    return _normalize_label(left) == _normalize_label(right)


def _normalize_label(value: str) -> str:
    return " ".join(str(value).casefold().split())
