"""Adapters for schedule text produced by the existing CLI output path."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

from src.models.academic import Course
from src.process_protocol import BATCH_END_MARKER, LAZY_NEXT_COMMAND, LAZY_STOP_COMMAND


_MARKER_PATTERN = re.compile(r"(?m)^(Complete System|Schedule) #(?P<number>\d+)\s*$")
_SEMESTER_PATTERN = re.compile(r"^===\s*SEMESTER:\s*(?P<semester>.*?)\s*===\s*$")
_TERM_PATTERN = re.compile(r"^\s*\[TERM:\s*(?P<term>.*?)\]\s*$")
_TOTAL_PATTERNS = (
    re.compile(r"(?mi)^Total complete systems:\s*(?P<count>[\d,]+)\s*$"),
    re.compile(r"(?mi)^Complete systems:\s*(?P<count>[\d,]+)\s*$"),
    re.compile(r"(?mi)^Total schedules across periods:\s*(?P<count>[\d,]+)\s*$"),
)
_MAX_PREFIX_BUFFER = 64


@dataclass(frozen=True)
class ScheduleExamDisplay:
    """One exam placement in the shape the output screen needs.

    Program IDs and requirement types come from the course catalog, because the
    scheduler output text itself only carries the course name, date, and lecturer.
    """

    course_name: str
    exam_date: date | None
    instructor: str
    course_id: int | None = None
    program_ids: tuple[int, ...] = ()
    requirement_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class SchedulePeriodDisplay:
    """The exams scheduled for one semester and term."""

    semester_label: str
    term_label: str
    exams: tuple[ScheduleExamDisplay, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ScheduleSystem:
    """One schedule system ready for the UI data layer."""

    number: int
    text: str
    label: str = "Schedule"
    periods: tuple[SchedulePeriodDisplay, ...] = field(default_factory=tuple)


@dataclass
class _PeriodBuilder:
    semester_label: str
    term_label: str = ""
    exams: list[ScheduleExamDisplay] = field(default_factory=list)

    def build(self) -> SchedulePeriodDisplay:
        return SchedulePeriodDisplay(
            semester_label=self.semester_label,
            term_label=self.term_label,
            exams=tuple(self.exams),
        )


class ScheduleOutputDataAdapter:
    """Convert v1 scheduler text blocks into output-screen display data."""

    def __init__(
        self,
        courses: Iterable[Course] = (),
        selected_program_ids: Iterable[int | str] = (),
    ) -> None:
        self.update_course_catalog(courses, selected_program_ids)

    def update_course_catalog(
        self,
        courses: Iterable[Course],
        selected_program_ids: Iterable[int | str] = (),
    ) -> None:
        # Rebuild the lookup whenever data is loaded or the selected programs change.
        self._course_catalog = _CourseCatalog(courses, selected_program_ids)

    def convert(self, systems: Iterable[ScheduleSystem]) -> list[ScheduleSystem]:
        return [self.convert_system(system) for system in systems]

    def convert_system(self, system: ScheduleSystem) -> ScheduleSystem:
        return ScheduleSystem(
            number=system.number,
            text=system.text,
            label=system.label,
            periods=tuple(self._parse_periods(system.text)),
        )

    def _parse_periods(self, text: str) -> list[SchedulePeriodDisplay]:
        periods: list[SchedulePeriodDisplay] = []
        current_period: _PeriodBuilder | None = None

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            semester_match = _SEMESTER_PATTERN.match(line)
            if semester_match:
                if current_period is not None:
                    periods.append(current_period.build())
                current_period = _PeriodBuilder(
                    semester_label=semester_match.group("semester").strip()
                )
                continue

            term_match = _TERM_PATTERN.match(line)
            if term_match and current_period is not None:
                current_period.term_label = term_match.group("term").strip()
                continue

            exam = self._parse_exam_line(line)
            if exam is not None and current_period is not None:
                current_period.exams.append(exam)

        if current_period is not None:
            periods.append(current_period.build())

        return periods

    def _parse_exam_line(self, line: str) -> ScheduleExamDisplay | None:
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 3:
            return None

        course_name, date_text, instructor = parts[:3]
        exam_date = _parse_iso_date(date_text)
        if not course_name or exam_date is None:
            return None

        # The output file only keeps the printed course name, so the catalog
        # fills in the extra course fields used by the schedule view.
        course = self._course_catalog.find(course_name, instructor)
        if course is None:
            return ScheduleExamDisplay(
                course_name=course_name,
                exam_date=exam_date,
                instructor=instructor,
            )

        return ScheduleExamDisplay(
            course_name=course.name,
            course_id=course.course_id,
            exam_date=exam_date,
            instructor=course.instructor,
            program_ids=self._course_catalog.program_ids_for(course),
            requirement_types=self._course_catalog.requirement_types_for(course),
        )


class _CourseCatalog:
    """Small lookup table used to add course metadata back onto printed schedules."""

    def __init__(
        self,
        courses: Iterable[Course],
        selected_program_ids: Iterable[int | str],
    ) -> None:
        self._selected_program_ids = _clean_program_ids(selected_program_ids)
        self._by_name: dict[str, list[Course]] = {}
        self._by_name_and_instructor: dict[tuple[str, str], Course] = {}

        for course in courses:
            name_key = _normalize_text(course.name)
            instructor_key = _normalize_text(course.instructor)
            # Keep both lookups: exact matches first, unique-name fallback second.
            self._by_name.setdefault(name_key, []).append(course)
            self._by_name_and_instructor[(name_key, instructor_key)] = course

    def find(self, course_name: str, instructor: str) -> Course | None:
        name_key = _normalize_text(course_name)
        instructor_key = _normalize_text(instructor)

        course = self._by_name_and_instructor.get((name_key, instructor_key))
        if course is not None:
            return course

        # If the instructor was shortened or changed in an older file, a unique
        # name match is still good enough for display-only enrichment.
        matches = self._by_name.get(name_key, [])
        return matches[0] if len(matches) == 1 else None

    def program_ids_for(self, course: Course) -> tuple[int, ...]:
        ids: list[int] = []
        for affiliation in course.affiliations:
            program_id = affiliation.program_id
            # Show the program context from the user's current selection.
            if self._selected_program_ids and program_id not in self._selected_program_ids:
                continue
            # A course may list the same program more than once for different rows.
            if program_id not in ids:
                ids.append(program_id)

        return tuple(ids)

    def requirement_types_for(self, course: Course) -> tuple[str, ...]:
        values: list[str] = []
        for affiliation in course.affiliations:
            # Requirement status should describe the same selected programs.
            if (
                self._selected_program_ids
                and affiliation.program_id not in self._selected_program_ids
            ):
                continue

            value = _enum_display_value(affiliation.requirement_type)
            # The compact calendar line only needs each status once.
            if value and value not in values:
                values.append(value)

        return tuple(values)


class StdoutScheduleParser:
    """Stateful parser for schedule blocks that may arrive in partial chunks."""

    def __init__(self) -> None:
        self._buffer = ""

    def feed(self, text: str) -> list[ScheduleSystem]:
        """Consume a stdout chunk and return newly completed systems."""
        if not text:
            return []

        self._buffer += text

        if BATCH_END_MARKER in self._buffer:
            return self._extract_blocks_until_batch_markers()

        self._drop_text_before_first_marker()
        return self._extract_complete_blocks(keep_last=True)

    def flush(self) -> list[ScheduleSystem]:
        """Return any final block left after the process exits."""
        systems = self._extract_complete_blocks(keep_last=False)
        self._buffer = ""
        return systems

    def reset(self) -> None:
        self._buffer = ""

    def _drop_text_before_first_marker(self) -> None:
        match = _MARKER_PATTERN.search(self._buffer)
        if match:
            if match.start() > 0:
                self._buffer = self._buffer[match.start():]
            return

        if len(self._buffer) > _MAX_PREFIX_BUFFER:
            self._buffer = self._buffer[-_MAX_PREFIX_BUFFER:]

    def _extract_complete_blocks(self, keep_last: bool) -> list[ScheduleSystem]:
        matches = list(_MARKER_PATTERN.finditer(self._buffer))
        if not matches:
            return []

        limit = len(matches) - 1 if keep_last else len(matches)
        systems: list[ScheduleSystem] = []

        for index in range(limit):
            start = matches[index].start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(self._buffer)
            system = self._build_system(matches[index], self._buffer[start:end])
            if system is not None:
                systems.append(system)

        if keep_last:
            self._buffer = self._buffer[matches[-1].start():]
        else:
            self._buffer = ""

        return systems

    def _extract_blocks_until_batch_markers(self) -> list[ScheduleSystem]:
        systems: list[ScheduleSystem] = []

        while BATCH_END_MARKER in self._buffer:
            before_marker, after_marker = self._buffer.split(BATCH_END_MARKER, 1)
            self._buffer = before_marker
            self._drop_text_before_first_marker()
            systems.extend(self._extract_complete_blocks(keep_last=False))
            self._buffer = after_marker.lstrip("\r\n")

        self._drop_text_before_first_marker()
        systems.extend(self._extract_complete_blocks(keep_last=True))
        return systems

    @staticmethod
    def _build_system(match: re.Match[str], block: str) -> ScheduleSystem | None:
        text = block.strip()
        if not text:
            return None
        return ScheduleSystem(
            number=int(match.group("number")),
            text=text,
            label=match.group(1),
        )


def _parse_iso_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parse_schedule_total(text: str) -> int | None:
    """Read the total schedule count from CLI summary text, when it is present."""
    for pattern in _TOTAL_PATTERNS:
        match = pattern.search(text)
        if match:
            return int(match.group("count").replace(",", ""))
    return None


def _clean_program_ids(values: Iterable[int | str]) -> set[int]:
    ids: set[int] = set()
    for value in values:
        try:
            ids.add(int(str(value).strip()))
        except (TypeError, ValueError):
            continue
    return ids


def _normalize_text(value: str) -> str:
    return " ".join(str(value).casefold().split())


def _enum_display_value(value) -> str:
    raw_value = getattr(value, "value", value)
    return "" if raw_value is None else str(raw_value)


