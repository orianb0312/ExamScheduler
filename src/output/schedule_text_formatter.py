"""Text formatting boundary for scheduler-generated schedule data.

The schedulers should decide *which* exams go on *which* dates. This module
decides how those decisions are written for the current CLI and desktop UI.
"""

from __future__ import annotations

from datetime import date
from typing import Mapping, Protocol, Sequence

from src.models.academic import Course
from src.models.scheduling import ExamPeriod


class ScheduleTextFormatter(Protocol):
    """Format scheduler results without making solver classes own text layout."""

    def format_master_header(self) -> str:
        """Return the period-schedule file header."""
        ...

    def format_empty_period(self, period: ExamPeriod) -> str:
        """Return text for a period that has no schedulable exams."""
        ...

    def format_period_schedule(
        self,
        schedule_number: int,
        courses: Sequence[Course],
        period: ExamPeriod,
        assignment: Mapping[int, date],
    ) -> str:
        """Return one numbered period schedule."""
        ...

    def format_period_schedule_block(
        self,
        period: ExamPeriod,
        courses: Sequence[Course],
        assignment: Mapping[int, date],
    ) -> str:
        """Return an unnumbered period block for complete systems."""
        ...

    def format_complete_header(
        self,
        complete_system_count: int,
        period_schedule_counts: Sequence[int],
        period_course_counts: Sequence[int] | None = None,
        auto_limit_seconds: float | None = None,
    ) -> str:
        """Return the complete-system file or stream header."""
        ...

    def format_complete_system(
        self,
        system_number: int,
        period_blocks: Sequence[str],
    ) -> str:
        """Return one complete schedule system."""
        ...

    def format_complete_truncation(
        self,
        written_count: int,
        complete_system_count: int,
    ) -> str:
        """Return the explicit complete-write truncation notice."""
        ...

    def format_auto_truncation(
        self,
        written_count: int,
        complete_system_count: int,
        time_limit_seconds: float,
    ) -> str:
        """Return the auto-mode truncation notice."""
        ...


class PlainTextScheduleFormatter:
    """Plain text format used by the current CLI and PyQt process protocol.

    Keep changes here careful: the PyQt output adapter reads this text from
    stdout/files, so this class is the compatibility point for the current v2
    protocol.
    """

    def format_master_header(self) -> str:
        return "OFFICIAL UNIVERSITY MASTER EXAM SCHEDULE\n" + "=" * 65 + "\n\n"

    def format_empty_period(self, period: ExamPeriod) -> str:
        return (
            f"=== SEMESTER: {period.semester.value} ===\n"
            f"  [TERM: {period.term.value}]\n"
            "  EMPTY SCHEDULE: No exams have been scheduled for this period.\n\n"
        )

    def format_period_schedule(
        self,
        schedule_number: int,
        courses: Sequence[Course],
        period: ExamPeriod,
        assignment: Mapping[int, date],
    ) -> str:
        return (
            f"Schedule #{schedule_number}\n"
            + self.format_period_schedule_block(period, courses, assignment)
            + "\n"
            + "*" * 70
            + "\n\n"
        )

    def format_period_schedule_block(
        self,
        period: ExamPeriod,
        courses: Sequence[Course],
        assignment: Mapping[int, date],
    ) -> str:
        # Complete systems reuse the same period block without a "Schedule #"
        # prefix, so the block is intentionally separate from the numbered case.
        lines = [
            f"=== SEMESTER: {period.semester.value} ===\n",
            f"  [TERM: {period.term.value}]\n",
            "  " + "-" * 40 + "\n",
        ]

        if not assignment:
            lines.append("  EMPTY PERIOD: No exams scheduled for this period.\n")
            return "".join(lines)

        for course_index, exam_date in _sorted_assignment_items(courses, assignment):
            course = courses[course_index]
            lines.append(f"  {course.name} | {exam_date} | {course.instructor}\n")

        return "".join(lines)

    def format_complete_header(
        self,
        complete_system_count: int,
        period_schedule_counts: Sequence[int],
        period_course_counts: Sequence[int] | None = None,
        auto_limit_seconds: float | None = None,
    ) -> str:
        # Some modes show only schedule counts; auto/streaming also shows course
        # counts and time limits. One formatter method keeps that variation out
        # of the scheduler.
        lines = [
            "OFFICIAL UNIVERSITY COMPLETE EXAM SYSTEMS\n",
            "=" * 65 + "\n",
            f"Total complete systems: {complete_system_count:,}\n",
        ]
        if period_course_counts is not None:
            lines.append(
                "Period course counts: "
                + ", ".join(f"{count:,}" for count in period_course_counts)
                + "\n"
            )
        lines.append(
            "Period schedule counts: "
            + ", ".join(f"{count:,}" for count in period_schedule_counts)
            + "\n"
        )
        if auto_limit_seconds is not None:
            lines.append(f"Auto time limit: {auto_limit_seconds:.2f} seconds\n")
        lines.append("\n")
        return "".join(lines)

    def format_complete_system(
        self,
        system_number: int,
        period_blocks: Sequence[str],
    ) -> str:
        return (
            f"Complete System #{system_number}\n"
            + "".join(period_blocks)
            + "\n"
            + "*" * 70
            + "\n\n"
        )

    def format_complete_truncation(
        self,
        written_count: int,
        complete_system_count: int,
    ) -> str:
        return (
            f"\n... Stopped after writing {written_count:,} of "
            f"{complete_system_count:,} complete systems ...\n"
        )

    def format_auto_truncation(
        self,
        written_count: int,
        complete_system_count: int,
        time_limit_seconds: float,
    ) -> str:
        return (
            f"\n... Auto limit wrote {written_count:,} of "
            f"{complete_system_count:,} complete systems within "
            f"{time_limit_seconds:.2f} seconds ...\n"
        )


def _sorted_assignment_items(
    courses: Sequence[Course],
    assignment: Mapping[int, date],
) -> list[tuple[int, date]]:
    # Sorting is an output decision, not a search decision. Keeping it here
    # means future UI ordering changes do not touch the solver.
    return sorted(
        assignment.items(),
        key=lambda item: (item[1], courses[item[0]].name.lower()),
    )
