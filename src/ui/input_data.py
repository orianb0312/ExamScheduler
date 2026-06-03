"""UI-local readers for Stage 2 input-screen previews."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


RECORD_SEPARATOR = "$$$$"
PROGRAM_LINE_PATTERN = re.compile(
    r"^(?P<program_id>\d{5}),(?P<year>[1-4]),(?P<semester>[A-Z]{4}),(?P<requirement>[^,\s]+)$"
)


@dataclass(frozen=True)
class CoursePreview:
    course_id: str
    name: str
    year: str
    semester: str
    requirement: str
    evaluation: str


@dataclass
class ProgramPreview:
    program_id: str
    name: str
    courses: list[CoursePreview] = field(default_factory=list)


@dataclass(frozen=True)
class PeriodPreview:
    semester: str
    term: str
    start_date: str
    end_date: str
    exclusions: tuple[str, ...]


class InputDataStore:
    """Store UI-side data loaded from selected input files."""

    def __init__(self) -> None:
        self._course_records: dict[str, str] = {}
        self._period_records: dict[tuple[str, str], str] = {}

    @property
    def is_empty(self) -> bool:
        return not self._course_records and not self._period_records

    def replace(self, course_file: Path, dates_file: Path) -> None:
        self._course_records = _read_course_records(course_file)
        self._period_records = _read_period_records(dates_file)

    def add(self, course_file: Path, dates_file: Path) -> None:
        self._add_missing_records(self._course_records, _read_course_records(course_file))
        self._add_missing_records(self._period_records, _read_period_records(dates_file))

    def programs(self) -> list[ProgramPreview]:
        programs: dict[str, ProgramPreview] = {}

        for record in self._course_records.values():
            course = _parse_course_record(record)
            if course is None:
                continue

            for program_id, preview in course:
                program = programs.setdefault(
                    program_id,
                    ProgramPreview(
                        program_id=program_id,
                        name=f"Program {program_id}",
                    ),
                )
                program.courses.append(preview)

        return sorted(programs.values(), key=lambda program: program.program_id)

    def periods(self) -> list[PeriodPreview]:
        periods = []
        for record in self._period_records.values():
            period = _parse_period_record(record)
            if period is not None:
                periods.append(period)
        return sorted(periods, key=lambda period: (period.semester, period.term))

    def write_runtime_files(
        self,
        target_dir: Path,
        selected_program_ids: list[str],
        period_rows: list[PeriodPreview],
    ) -> tuple[Path, Path, Path]:
        target_dir.mkdir(parents=True, exist_ok=True)

        course_file = target_dir / "ui_courses.txt"
        dates_file = target_dir / "ui_exam_dates.txt"
        programs_file = target_dir / "ui_programs.txt"

        course_file.write_text(_records_to_text(self._course_records.values()), encoding="utf-8")
        dates_file.write_text(_period_rows_to_text(period_rows), encoding="utf-8")
        programs_file.write_text(", ".join(selected_program_ids), encoding="utf-8")

        return course_file, dates_file, programs_file

    @staticmethod
    def _add_missing_records(target: dict, incoming: dict) -> None:
        for key, record in incoming.items():
            if key not in target:
                target[key] = record


def _read_records(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [part.strip() for part in text.split(RECORD_SEPARATOR) if part.strip()]


def _read_course_records(path: Path) -> dict[str, str]:
    records = {}
    for record in _read_records(path):
        lines = _clean_lines(record)
        if len(lines) >= 2:
            records[lines[1]] = record
    return records


def _read_period_records(path: Path) -> dict[tuple[str, str], str]:
    records = {}
    for record in _read_records(path):
        lines = _clean_lines(record)
        if len(lines) >= 2:
            header = [part.strip() for part in lines[0].split(",", maxsplit=1)]
            if len(header) == 2:
                records[(header[0], header[1])] = record
    return records


def _parse_course_record(record: str) -> list[tuple[str, CoursePreview]] | None:
    lines = _clean_lines(record)
    if len(lines) < 5:
        return None

    course_name = lines[0]
    course_id = lines[1]
    evaluation = lines[-1]
    previews = []

    for line in lines[3:-1]:
        match = PROGRAM_LINE_PATTERN.match(line.replace(" ", ""))
        if not match:
            continue
        program_id = match.group("program_id")
        previews.append(
            (
                program_id,
                CoursePreview(
                    course_id=course_id,
                    name=course_name,
                    year=match.group("year"),
                    semester=match.group("semester"),
                    requirement=match.group("requirement"),
                    evaluation=evaluation,
                ),
            )
        )

    return previews


def _parse_period_record(record: str) -> PeriodPreview | None:
    lines = _clean_lines(record)
    if len(lines) < 2:
        return None

    header = [part.strip() for part in lines[0].split(",", maxsplit=1)]
    bounds = [part.strip() for part in lines[1].split(",", maxsplit=1)]
    if len(header) != 2 or len(bounds) != 2:
        return None

    exclusions = tuple(line.lstrip("- ").strip() for line in lines[2:])
    return PeriodPreview(
        semester=header[0],
        term=header[1],
        start_date=bounds[0],
        end_date=bounds[1],
        exclusions=exclusions,
    )


def _period_rows_to_text(period_rows: list[PeriodPreview]) -> str:
    records = []
    for period in period_rows:
        lines = [
            f"{period.semester},{period.term}",
            f"{period.start_date}, {period.end_date}",
        ]
        lines.extend(f"- {exclusion}" for exclusion in period.exclusions if exclusion)
        records.append("\n".join(lines))
    return _records_to_text(records)


def _records_to_text(records) -> str:
    return "\n".join(f"{RECORD_SEPARATOR}\n{record.strip()}" for record in records) + "\n"


def _clean_lines(record: str) -> list[str]:
    return [line.strip() for line in record.splitlines() if line.strip()]
