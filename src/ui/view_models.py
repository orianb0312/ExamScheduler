"""View models used by the desktop calendar widgets."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class ScheduledExamViewModel:
    """Calendar-ready exam data after the scheduler output has been enriched."""

    course_name: str
    exam_date: date
    instructor: str
    course_id: int | None = None
    program_ids: tuple[int, ...] = ()
    requirement_types: tuple[str, ...] = ()

    @property
    def calendar_label(self) -> str:
        # Course number is part of the Phase 2 schedule display requirement.
        if self.course_id is None:
            return self.course_name
        return f"{self.course_name} ({self.course_id})"

    @property
    def calendar_detail(self) -> str:
        # Keep each exam compact while still showing program and requirement.
        parts: list[str] = []
        if self.program_ids:
            # Multiple selected programs can be affected by one shared course.
            parts.append(", ".join(str(program_id) for program_id in self.program_ids))
        if self.requirement_types:
            parts.append(", ".join(self.requirement_types))
        return " | ".join(parts)


@dataclass(frozen=True)
class ExclusionViewModel:
    start_date: date
    end_date: date | None


@dataclass(frozen=True)
class ExamPeriodViewModel:
    semester_label: str
    term_label: str
    start_date: date
    end_date: date
    exclusions: tuple[ExclusionViewModel, ...] = field(default_factory=tuple)
    scheduled_exams: tuple[ScheduledExamViewModel, ...] = field(default_factory=tuple)

    def is_date_in_period(self, current_date: date) -> bool:
        return self.start_date <= current_date <= self.end_date

    def is_date_excluded(self, current_date: date) -> bool:
        for exclusion in self.exclusions:
            if exclusion.end_date is None:
                if current_date == exclusion.start_date:
                    return True
                continue

            if exclusion.start_date <= current_date <= exclusion.end_date:
                return True

        return False

    def exams_on(self, current_date: date) -> tuple[ScheduledExamViewModel, ...]:
        return tuple(
            exam for exam in self.scheduled_exams if exam.exam_date == current_date
        )
