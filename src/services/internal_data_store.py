"""Internal storage for parsed scheduler input data."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

from src.models.academic import (
    Attendance,
    Course,
    Evaluation,
    Exam,
    ProgramAffiliation,
    Project,
)
from src.models.enums import RequirementType, Semester, Term
from src.models.scheduling import DateExclusion, ExamPeriod


CACHE_VERSION = 1
DEFAULT_INTERNAL_DATA_FILE = Path(".exam_scheduler_cache") / "processed_input.json"


@dataclass(frozen=True)
class InternalDataSnapshot:
    """Processed data restored from the internal data file."""

    courses: tuple[Course, ...]
    exam_periods: tuple[ExamPeriod, ...]


class InternalDataStore:
    """Save and restore processed courses and exam periods for unchanged files."""

    def __init__(self, storage_file: str | Path = DEFAULT_INTERNAL_DATA_FILE) -> None:
        self._storage_file = Path(storage_file)

    @classmethod
    def default(cls) -> "InternalDataStore":
        return cls(DEFAULT_INTERNAL_DATA_FILE)

    @property
    def storage_file(self) -> Path:
        return self._storage_file

    def load_if_current(
        self,
        courses_file: str | Path,
        exam_dates_file: str | Path,
    ) -> InternalDataSnapshot | None:
        if not self._storage_file.is_file():
            return None

        try:
            payload = json.loads(self._storage_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        if payload.get("version") != CACHE_VERSION:
            return None

        if payload.get("source_files") != _source_fingerprints(courses_file, exam_dates_file):
            return None

        try:
            return InternalDataSnapshot(
                courses=tuple(_course_from_dict(item) for item in payload["courses"]),
                exam_periods=tuple(
                    _exam_period_from_dict(item) for item in payload["exam_periods"]
                ),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def save(
        self,
        courses_file: str | Path,
        exam_dates_file: str | Path,
        courses: Sequence[Course],
        exam_periods: Sequence[ExamPeriod],
    ) -> None:
        self._storage_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": CACHE_VERSION,
            "source_files": _source_fingerprints(courses_file, exam_dates_file),
            "courses": [_course_to_dict(course) for course in courses],
            "exam_periods": [_exam_period_to_dict(period) for period in exam_periods],
        }

        # Student note: write to a temporary file first so a crash will not leave
        # a half-written cache file behind.
        temp_file = self._storage_file.with_suffix(self._storage_file.suffix + ".tmp")
        temp_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_file.replace(self._storage_file)


def _source_fingerprints(
    courses_file: str | Path,
    exam_dates_file: str | Path,
) -> dict[str, dict[str, str]]:
    return {
        "courses_file": _file_fingerprint(courses_file),
        "exam_dates_file": _file_fingerprint(exam_dates_file),
    }


def _file_fingerprint(path: str | Path) -> dict[str, str]:
    source_path = Path(path)
    return {
        "path": str(source_path.resolve()),
        "sha256": _sha256(source_path),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _course_to_dict(course: Course) -> dict:
    return {
        "course_id": course.course_id,
        "name": course.name,
        "instructor": course.instructor,
        "evaluation": _evaluation_to_name(course.evaluation),
        "affiliations": [
            {
                "program_id": affiliation.program_id,
                "year": affiliation.year,
                "semester": affiliation.semester.value,
                "requirement_type": affiliation.requirement_type.value,
            }
            for affiliation in course.affiliations
        ],
    }


def _course_from_dict(data: dict) -> Course:
    course = Course(
        course_id=int(data["course_id"]),
        name=str(data["name"]),
        instructor=str(data["instructor"]),
        evaluation=_evaluation_from_name(str(data["evaluation"])),
    )
    for affiliation_data in data.get("affiliations", []):
        course.add_affiliation(
            ProgramAffiliation(
                program_id=int(affiliation_data["program_id"]),
                year=int(affiliation_data["year"]),
                semester=Semester(str(affiliation_data["semester"])),
                requirement_type=RequirementType(
                    str(affiliation_data["requirement_type"])
                ),
            )
        )
    return course


def _exam_period_to_dict(period: ExamPeriod) -> dict:
    return {
        "semester": period.semester.value,
        "term": period.term.value,
        "start_date": period.start_date.isoformat(),
        "end_date": period.end_date.isoformat(),
        "exclusions": [
            {
                "start_date": exclusion.start_date.isoformat(),
                "end_date": (
                    exclusion.end_date.isoformat()
                    if exclusion.end_date is not None
                    else None
                ),
            }
            for exclusion in period.exclusions
        ],
    }


def _exam_period_from_dict(data: dict) -> ExamPeriod:
    period = ExamPeriod(
        semester=Semester(str(data["semester"])),
        term=Term(str(data["term"])),
        start_date=date.fromisoformat(str(data["start_date"])),
        end_date=date.fromisoformat(str(data["end_date"])),
    )
    for exclusion_data in data.get("exclusions", []):
        end_date_text = exclusion_data.get("end_date")
        period.add_exclusion(
            DateExclusion(
                start_date=date.fromisoformat(str(exclusion_data["start_date"])),
                end_date=(
                    date.fromisoformat(str(end_date_text))
                    if end_date_text is not None
                    else None
                ),
            )
        )
    return period


def _evaluation_to_name(evaluation: Evaluation) -> str:
    if isinstance(evaluation, Exam):
        return "Exam"
    if isinstance(evaluation, Project):
        return "Project"
    if isinstance(evaluation, Attendance):
        return "Attendance"
    raise ValueError(f"Unsupported evaluation type: {type(evaluation).__name__}")


def _evaluation_from_name(name: str) -> Evaluation:
    if name == "Exam":
        return Exam()
    if name == "Project":
        return Project()
    if name == "Attendance":
        return Attendance()
    raise ValueError(f"Unsupported evaluation type: {name}")
