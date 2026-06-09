"""Application state used to prepare scheduler input from the UI."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from src.models.academic import Attendance, Course, Exam, Project
from src.models.scheduling import ExamPeriod
from src.services.day_status_service import (
    copy_exam_period,
    exclude_day,
    format_exam_periods,
    restore_day,
    update_period_dates,
)


class SchedulerInputState:
    """Keep selected programs and expose them through the existing file input flow."""

    def __init__(self, runtime_dir: Path) -> None:
        self._runtime_dir = runtime_dir
        self._selected_program_ids: tuple[str, ...] = ()
        self._courses: tuple[Course, ...] = ()
        self._exam_periods: tuple[ExamPeriod, ...] = ()

    @property
    def selected_program_ids(self) -> tuple[str, ...]:
        return self._selected_program_ids

    @property
    def exam_periods(self) -> tuple[ExamPeriod, ...]:
        return self._exam_periods

    def set_selected_programs(self, program_ids: Sequence[str]) -> None:
        self._selected_program_ids = tuple(str(program_id) for program_id in program_ids)

    def set_courses(self, courses: Sequence[Course]) -> None:
        self._courses = tuple(courses)

    def set_exam_periods(self, periods: Sequence[ExamPeriod]) -> None:
        self._exam_periods = tuple(copy_exam_period(period) for period in periods)

    def exclude_day(self, period_index: int, day) -> None:
        exclude_day(self._period_at(period_index), day)

    def restore_day(self, period_index: int, day) -> None:
        restore_day(self._period_at(period_index), day)

    def update_period_dates(self, period_index: int, start_date, end_date) -> None:
        update_period_dates(self._period_at(period_index), start_date, end_date)

    def write_selected_programs_file(self) -> Path:
        if not self._selected_program_ids:
            raise ValueError("Select at least one study program before generating schedules.")

        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        programs_file = self._runtime_dir / "ui_selected_programs.txt"
        programs_file.write_text(", ".join(self._selected_program_ids), encoding="utf-8")
        return programs_file

    def write_courses_file(self) -> Path | None:
        if not self._courses:
            return None

        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        courses_file = self._runtime_dir / "ui_courses.txt"
        courses_file.write_text(
            format_courses(self._courses),
            encoding="utf-8",
        )
        return courses_file

    def write_exam_dates_file(self) -> Path | None:
        if not self._exam_periods:
            return None

        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        exam_dates_file = self._runtime_dir / "ui_exam_dates.txt"
        exam_dates_file.write_text(
            format_exam_periods(self._exam_periods),
            encoding="utf-8",
        )
        return exam_dates_file

    def _period_at(self, period_index: int) -> ExamPeriod:
        if period_index < 0:
            raise ValueError(f"Unknown exam period index: {period_index}")
        try:
            return self._exam_periods[period_index]
        except IndexError as exc:
            raise ValueError(f"Unknown exam period index: {period_index}") from exc


def format_courses(courses: Sequence[Course]) -> str:
    blocks: list[str] = []
    for course in courses:
        lines = [
            "$$$$",
            str(course.name),
            str(course.course_id),
            str(course.instructor),
        ]
        for affiliation in course.affiliations:
            lines.append(
                ",".join(
                    [
                        str(affiliation.program_id),
                        str(affiliation.year),
                        str(affiliation.semester.value),
                        str(affiliation.requirement_type.value),
                    ]
                )
            )
        lines.append(_evaluation_name(course))
        blocks.append("\n".join(lines))

    return "\n".join(blocks) + ("\n" if blocks else "")


def _evaluation_name(course: Course) -> str:
    evaluation = course.evaluation
    if isinstance(evaluation, Exam):
        return "Exam"
    if isinstance(evaluation, Project):
        return "Project"
    if isinstance(evaluation, Attendance):
        return "Attendance"
    raise ValueError(f"Unsupported evaluation type: {type(evaluation).__name__}")
