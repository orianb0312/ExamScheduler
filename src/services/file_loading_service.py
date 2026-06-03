"""Load selected input files through the existing parser pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Protocol

from src.models.academic import Course
from src.models.scheduling import ExamPeriod
from src.parser.course_factory import build_courses_from_json
from src.parser.file_parser import parse_catalog_text, parse_periods_text
from src.parser.period_factory import build_periods_from_json


class FileLoadingError(ValueError):
    """Raised when selected input files cannot be loaded for scheduling."""


class DataLoadMode(str, Enum):
    """Supported ways to apply newly parsed input files to stored data."""

    REPLACE = "replace"
    UPDATE = "update"

    @classmethod
    def from_value(cls, value: "DataLoadMode | str") -> "DataLoadMode":
        if isinstance(value, cls):
            return value
        try:
            return cls(value.strip().lower())
        except (AttributeError, ValueError) as exc:
            raise FileLoadingError(f"Unsupported data load mode: {value}") from exc


@dataclass(frozen=True)
class ProgramSummary:
    """Program option discovered from the parsed course catalog."""

    program_id: int
    course_count: int

    @property
    def display_name(self) -> str:
        return f"Program {self.program_id}"


@dataclass(frozen=True)
class LoadedSchedulerInput:
    """Parsed data kept in memory after a successful file load."""

    courses: tuple[Course, ...]
    exam_periods: tuple[ExamPeriod, ...]
    programs: tuple[ProgramSummary, ...]

    @property
    def course_count(self) -> int:
        return len(self.courses)

    @property
    def exam_period_count(self) -> int:
        return len(self.exam_periods)

    @property
    def program_count(self) -> int:
        return len(self.programs)

    @property
    def program_ids_as_strings(self) -> list[str]:
        """
        Extracts all loaded program IDs formatted as a list of strings.
        """
        return [str(program.program_id) for program in self.programs]


@dataclass(frozen=True)
class DataLoadResult:
    """User-facing result of applying parsed files to in-memory data."""

    course_mode: DataLoadMode
    exam_dates_mode: DataLoadMode
    loaded_data: LoadedSchedulerInput
    added_course_count: int
    added_exam_period_count: int
    duplicate_course_count: int = 0
    duplicate_exam_period_count: int = 0

    @property
    def message(self) -> str:
        if self.course_mode == DataLoadMode.REPLACE and self.exam_dates_mode == DataLoadMode.REPLACE:
            return (
                "Replaced loaded data with "
                f"{_count_phrase(self.loaded_data.course_count, 'course')}, "
                f"{_count_phrase(self.loaded_data.exam_period_count, 'exam period')}, "
                f"and {_count_phrase(self.loaded_data.program_count, 'study program')}."
            )

        course_text = _mode_result_text(
            label="Courses",
            mode=self.course_mode,
            added_count=self.added_course_count,
            duplicate_count=self.duplicate_course_count,
            total_count=self.loaded_data.course_count,
            item_name="course",
        )
        exam_dates_text = _mode_result_text(
            label="Exam dates",
            mode=self.exam_dates_mode,
            added_count=self.added_exam_period_count,
            duplicate_count=self.duplicate_exam_period_count,
            total_count=self.loaded_data.exam_period_count,
            item_name="exam period",
        )

        return (
            f"{course_text} {exam_dates_text} "
            f"The system now has {_count_phrase(self.loaded_data.course_count, 'course')}, "
            f"{_count_phrase(self.loaded_data.exam_period_count, 'exam period')}, "
            f"and {_count_phrase(self.loaded_data.program_count, 'study program')}."
        )


class FileParserAdapter(Protocol):
    """Boundary used by the service to call parser-backed loading."""

    def parse_files(self, courses_file: Path, exam_dates_file: Path) -> LoadedSchedulerInput:
        """Parse selected files and return data ready for UI consumption."""


class ExistingFileParserAdapter:
    """Adapter around the existing v1 file parser and factories."""

    def parse_files(self, courses_file: Path, exam_dates_file: Path) -> LoadedSchedulerInput:
        course_dicts = parse_catalog_text(courses_file.read_text(encoding="utf-8"))
        period_dicts = parse_periods_text(exam_dates_file.read_text(encoding="utf-8"))

        parser_json = json.dumps(
            {
                "courses_node": course_dicts,
                "periods_node": period_dicts,
                "user_node": [],
            },
            ensure_ascii=False,
        )

        courses = tuple(build_courses_from_json(parser_json))
        periods = tuple(build_periods_from_json(parser_json))
        programs = _summarize_programs(courses)

        return LoadedSchedulerInput(
            courses=courses,
            exam_periods=periods,
            programs=programs,
        )


class FileLoadingService:
    """Receive UI-selected paths, load parser data, and keep it in memory."""

    def __init__(self, parser_adapter: FileParserAdapter | None = None) -> None:
        self._parser_adapter = parser_adapter or ExistingFileParserAdapter()
        self._loaded_data: LoadedSchedulerInput | None = None

    @property
    def loaded_data(self) -> LoadedSchedulerInput | None:
        return self._loaded_data

    def load_selected_files(
        self,
        courses_file: str | Path,
        exam_dates_file: str | Path,
        course_mode: DataLoadMode | str = DataLoadMode.REPLACE,
        exam_dates_mode: DataLoadMode | str | None = None,
    ) -> DataLoadResult:
        selected_course_mode = DataLoadMode.from_value(course_mode)
        selected_exam_dates_mode = DataLoadMode.from_value(exam_dates_mode or course_mode)
        course_path = _require_existing_file(courses_file, "Courses file")
        dates_path = _require_existing_file(exam_dates_file, "Exam dates file")

        try:
            incoming_data = self._parser_adapter.parse_files(course_path, dates_path)
        except (OSError, KeyError, ValueError) as exc:
            raise FileLoadingError(f"Could not load selected files: {exc}") from exc

        existing_data = self._loaded_data
        existing_courses = existing_data.courses if existing_data is not None else ()
        existing_periods = existing_data.exam_periods if existing_data is not None else ()

        courses, course_stats = _apply_courses(
            existing_courses,
            incoming_data.courses,
            selected_course_mode,
        )
        periods, period_stats = _apply_exam_periods(
            existing_periods,
            incoming_data.exam_periods,
            selected_exam_dates_mode,
        )

        loaded_data = LoadedSchedulerInput(
            courses=courses,
            exam_periods=periods,
            programs=_summarize_programs(courses),
        )
        self._loaded_data = loaded_data
        return DataLoadResult(
            course_mode=selected_course_mode,
            exam_dates_mode=selected_exam_dates_mode,
            loaded_data=loaded_data,
            added_course_count=course_stats.added_count,
            added_exam_period_count=period_stats.added_count,
            duplicate_course_count=course_stats.duplicate_count,
            duplicate_exam_period_count=period_stats.duplicate_count,
        )

    def clear(self) -> None:
        self._loaded_data = None


def _require_existing_file(path: str | Path, label: str) -> Path:
    candidate = Path(path)
    if not str(candidate).strip():
        raise FileLoadingError(f"{label} was not selected.")
    if not candidate.is_file():
        raise FileLoadingError(f"{label} does not exist: {candidate}")
    return candidate


def _count_phrase(count: int, singular: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {singular}{suffix}"


def _mode_result_text(
    label: str,
    mode: DataLoadMode,
    added_count: int,
    duplicate_count: int,
    total_count: int,
    item_name: str,
) -> str:
    if mode == DataLoadMode.REPLACE:
        return f"{label}: replaced with {_count_phrase(total_count, item_name)}."

    duplicate_text = ""
    if duplicate_count and item_name == "course":
        duplicate_text = f" Merged {_count_phrase(duplicate_count, 'existing course')}."
    elif duplicate_count:
        duplicate_text = f" Ignored {_count_phrase(duplicate_count, 'duplicate record')}."
    return f"{label}: added {_count_phrase(added_count, 'new ' + item_name)}.{duplicate_text}"


def _summarize_programs(courses: tuple[Course, ...]) -> tuple[ProgramSummary, ...]:
    counts: dict[int, int] = {}

    for course in courses:
        for affiliation in course.affiliations:
            counts[affiliation.program_id] = counts.get(affiliation.program_id, 0) + 1

    return tuple(
        ProgramSummary(program_id=program_id, course_count=counts[program_id])
        for program_id in sorted(counts)
    )


@dataclass(frozen=True)
class _ApplyStats:
    added_count: int
    duplicate_count: int


def _apply_courses(
    existing_courses: tuple[Course, ...],
    incoming_courses: tuple[Course, ...],
    mode: DataLoadMode,
) -> tuple[tuple[Course, ...], _ApplyStats]:
    if mode == DataLoadMode.REPLACE:
        return incoming_courses, _ApplyStats(
            added_count=len(incoming_courses),
            duplicate_count=0,
        )

    merged_courses_by_id = {course.course_id: course for course in existing_courses}
    course_order = [course.course_id for course in existing_courses]
    duplicate_count = 0

    for course in incoming_courses:
        existing_course = merged_courses_by_id.get(course.course_id)
        if existing_course is not None:
            duplicate_count += 1
            merged_courses_by_id[course.course_id] = _merge_course_affiliations(
                existing_course,
                course,
            )
            continue

        course_order.append(course.course_id)
        merged_courses_by_id[course.course_id] = course

    merged_courses = [merged_courses_by_id[course_id] for course_id in course_order]
    return tuple(merged_courses), _ApplyStats(
        added_count=len(merged_courses) - len(existing_courses),
        duplicate_count=duplicate_count,
    )


def _merge_course_affiliations(existing_course: Course, incoming_course: Course) -> Course:
    affiliations = list(existing_course.affiliations)
    seen_program_ids = {affiliation.program_id for affiliation in affiliations}

    for affiliation in incoming_course.affiliations:
        if affiliation.program_id in seen_program_ids:
            continue
        seen_program_ids.add(affiliation.program_id)
        affiliations.append(affiliation)

    return replace(existing_course, affiliations=affiliations)


def _apply_exam_periods(
    existing_periods: tuple[ExamPeriod, ...],
    incoming_periods: tuple[ExamPeriod, ...],
    mode: DataLoadMode,
) -> tuple[tuple[ExamPeriod, ...], _ApplyStats]:
    if mode == DataLoadMode.REPLACE:
        return incoming_periods, _ApplyStats(
            added_count=len(incoming_periods),
            duplicate_count=0,
        )

    merged_periods = list(existing_periods)
    period_keys = {_period_key(period) for period in existing_periods}
    duplicate_count = 0

    for period in incoming_periods:
        key = _period_key(period)
        if key in period_keys:
            duplicate_count += 1
            continue

        period_keys.add(key)
        merged_periods.append(period)

    return tuple(merged_periods), _ApplyStats(
        added_count=len(merged_periods) - len(existing_periods),
        duplicate_count=duplicate_count,
    )


def _period_key(period: ExamPeriod) -> tuple[str, str]:
    return period.semester.value, period.term.value
