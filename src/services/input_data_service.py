"""Input preview data prepared through the existing v1 file parser."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from src.parser.file_parser import (
    RECORD_SEPARATOR,
    parse_catalog_text,
    parse_periods_text,
    split_records,
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


@dataclass(frozen=True)
class _ParsedRecord:
    text: str
    data: dict[str, Any]


class InputDataStore:
    """Store parsed input data for UI preview and runtime file generation."""

    def __init__(self) -> None:
        self._course_records: dict[str, _ParsedRecord] = {}
        self._period_records: dict[tuple[str, str], _ParsedRecord] = {}

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
            course = record.data
            for program in course["programs"]:
                program_id = program["number"]
                preview = programs.setdefault(
                    program_id,
                    ProgramPreview(
                        program_id=program_id,
                        name=f"Program {program_id}",
                    ),
                )
                preview.courses.append(
                    CoursePreview(
                        course_id=course["number"],
                        name=course["name"],
                        year=program["year"],
                        semester=program["semester"],
                        requirement=program["requirement"],
                        evaluation=course["evaluation"],
                    )
                )

        return sorted(programs.values(), key=lambda program: program.program_id)

    def periods(self) -> list[PeriodPreview]:
        periods = [
            _period_preview(record.data)
            for record in self._period_records.values()
        ]
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

        course_file.write_text(
            _records_to_text(record.text for record in self._course_records.values()),
            encoding="utf-8",
        )
        dates_file.write_text(_period_rows_to_text(period_rows), encoding="utf-8")
        programs_file.write_text(", ".join(selected_program_ids), encoding="utf-8")

        return course_file, dates_file, programs_file

    @staticmethod
    def _add_missing_records(target: dict, incoming: dict) -> None:
        for key, record in incoming.items():
            if key not in target:
                target[key] = record


def _read_course_records(path: Path) -> dict[str, _ParsedRecord]:
    text = path.read_text(encoding="utf-8")
    record_texts = split_records(text)
    parsed_courses = parse_catalog_text(text)

    records = {}
    for record_text, data in zip(record_texts, parsed_courses):
        records[data["number"]] = _ParsedRecord(text=record_text, data=data)
    return records


def _read_period_records(path: Path) -> dict[tuple[str, str], _ParsedRecord]:
    text = path.read_text(encoding="utf-8")
    record_texts = split_records(text)
    parsed_periods = parse_periods_text(text)

    records = {}
    for record_text, data in zip(record_texts, parsed_periods):
        records[(data["semester"], data["moed"])] = _ParsedRecord(text=record_text, data=data)
    return records


def _period_preview(period: dict[str, Any]) -> PeriodPreview:
    return PeriodPreview(
        semester=period["semester"],
        term=period["moed"],
        start_date=period["start_date"],
        end_date=period["end_date"],
        exclusions=tuple(_format_exclusion(exclusion) for exclusion in period["exclusions"]),
    )


def _format_exclusion(exclusion: dict[str, str | None]) -> str:
    text = exclusion["start_date"] or ""
    if exclusion.get("end_date"):
        text = f"{text}, {exclusion['end_date']}"
    if exclusion.get("comment"):
        comment = exclusion["comment"].lstrip("- ").strip()
        text = f"{text} {comment}"
    return text


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


def _records_to_text(records: Iterable[str]) -> str:
    clean_records = [record.strip() for record in records if record.strip()]
    if not clean_records:
        return ""
    return "\n".join(f"{RECORD_SEPARATOR}\n{record}" for record in clean_records) + "\n"
