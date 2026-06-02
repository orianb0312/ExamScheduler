"""Load selected input files through the existing parser pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from src.models.academic import Course
from src.models.scheduling import ExamPeriod
from src.parser.course_factory import build_courses_from_json
from src.parser.file_parser import parse_catalog_text, parse_periods_text
from src.parser.period_factory import build_periods_from_json


class FileLoadingError(ValueError):
    """Raised when selected input files cannot be loaded for scheduling."""


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
    ) -> LoadedSchedulerInput:
        course_path = _require_existing_file(courses_file, "Courses file")
        dates_path = _require_existing_file(exam_dates_file, "Exam dates file")

        try:
            loaded_data = self._parser_adapter.parse_files(course_path, dates_path)
        except (OSError, KeyError, ValueError) as exc:
            raise FileLoadingError(f"Could not load selected files: {exc}") from exc

        self._loaded_data = loaded_data
        return loaded_data

    def clear(self) -> None:
        self._loaded_data = None


def _require_existing_file(path: str | Path, label: str) -> Path:
    candidate = Path(path)
    if not str(candidate).strip():
        raise FileLoadingError(f"{label} was not selected.")
    if not candidate.is_file():
        raise FileLoadingError(f"{label} does not exist: {candidate}")
    return candidate


def _summarize_programs(courses: tuple[Course, ...]) -> tuple[ProgramSummary, ...]:
    counts: dict[int, int] = {}

    for course in courses:
        for affiliation in course.affiliations:
            counts[affiliation.program_id] = counts.get(affiliation.program_id, 0) + 1

    return tuple(
        ProgramSummary(program_id=program_id, course_count=counts[program_id])
        for program_id in sorted(counts)
    )

