"""Persist exams exported to the device calendar for later UID-based revocation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from src.models.enums import Semester, Term
from src.output.output_models import ScheduledExam

# Increment this value whenever the on-disk registry format changes.
# Older registry files will be ignored if their version does not match.
REGISTRY_VERSION = 1


@dataclass(frozen=True)
class ExportedExamRecord:
    """One exam the app previously published to a device calendar."""

    course_id: int
    course_name: str
    exam_date: date
    semester: Semester
    term: Term
    instructor: str

    def dedupe_key(self) -> tuple[int, str]:
        """
        Return a unique identifier for an exported exam.

        The combination of course ID and exam date is used to prevent
        duplicate exports of the same exam event.
        """
        return (self.course_id, self.exam_date.isoformat())

    def to_scheduled_exam(self) -> ScheduledExam:
        """
        Reconstruct a ScheduledExam object from the stored registry record.

        This allows previously exported exams to be converted back into the
        format expected by the ICS formatter when generating cancellation files.
        """
        return ScheduledExam(
            course_name=self.course_name,
            course_id=self.course_id,
            semester=self.semester,
            term=self.term,
            exam_date=self.exam_date,
            instructor=self.instructor,
        )

    def to_dict(self) -> dict[str, str | int]:
        """
        Convert the record into a JSON-serializable dictionary.

        Enum values and dates are converted into string representations
        suitable for persistence.
        """
        return {
            "course_id": self.course_id,
            "course_name": self.course_name,
            "exam_date": self.exam_date.isoformat(),
            "semester": self.semester.value,
            "term": self.term.value,
            "instructor": self.instructor,
        }

    @classmethod
    def from_scheduled_exam(cls, exam: ScheduledExam) -> "ExportedExamRecord":
        """
        Create a registry record from a ScheduledExam instance.

        This is used whenever newly exported exams are added to the registry.
        """
        return cls(
            course_id=exam.course_id,
            course_name=exam.course_name,
            exam_date=exam.exam_date,
            semester=exam.semester,
            term=exam.term,
            instructor=exam.instructor,
        )

    @classmethod
    def from_dict(cls, payload: dict) -> "ExportedExamRecord":
        """
        Reconstruct a registry record from persisted JSON data.
        """
        return cls(
            course_id=int(payload["course_id"]),
            course_name=str(payload["course_name"]),
            exam_date=date.fromisoformat(str(payload["exam_date"])),
            semester=Semester(str(payload["semester"])),
            term=Term(str(payload["term"])),
            instructor=str(payload.get("instructor", "TBD")),
        )


class CalendarExportRegistry:
    """
    Track every exam this app exported so cancel files target only our UIDs.

    The registry acts as a local source of truth for all events previously
    exported by this application.
    """

    def __init__(self, storage_file: str | Path) -> None:
        self._storage_file = Path(storage_file)

    @property
    def storage_file(self) -> Path:
        """Return the registry file path."""
        return self._storage_file

    def is_empty(self) -> bool:
        """Return True when no exported exam records are stored."""
        return not self.all_records()

    def all_records(self) -> tuple[ExportedExamRecord, ...]:
        """
        Return all exported exam records currently stored in the registry.
        """
        return tuple(self._load_records().values())

    def all_exams(self) -> tuple[ScheduledExam, ...]:
        """
        Return all exported exams as ScheduledExam instances.

        This is primarily used when generating a cancellation file for all
        previously exported calendar entries.
        """
        return tuple(record.to_scheduled_exam() for record in self.all_records())

    def add_exams(self, exams: list[ScheduledExam]) -> int:
        """
        Add exported exams to the registry.

        Existing entries are updated while new entries are counted toward
        the returned total.
        """
        records = self._load_records()
        added = 0

        for exam in exams:
            record = ExportedExamRecord.from_scheduled_exam(exam)
            key = record.dedupe_key()

            if key not in records:
                added += 1

            records[key] = record

        self._save_records(records)
        return added

    def remove_exams(self, exams: list[ScheduledExam]) -> int:
        """
        Remove matching exams from the registry.

        Returns the number of records successfully removed.
        """
        records = self._load_records()
        removed = 0

        for exam in exams:
            key = (exam.course_id, exam.exam_date.isoformat())

            if key in records:
                del records[key]
                removed += 1

        self._save_records(records)
        return removed

    def clear(self) -> None:
        """
        Delete the registry file entirely.

        This is used after generating a cancellation file that revokes every
        event previously exported by the application.
        """
        if self._storage_file.is_file():
            self._storage_file.unlink()

    def _load_records(self) -> dict[tuple[int, str], ExportedExamRecord]:
        """
        Load all registry records from disk.

        Corrupted, invalid, or incompatible files are treated as empty
        registries to avoid interrupting user workflows.
        """
        if not self._storage_file.is_file():
            return {}

        try:
            payload = json.loads(
                self._storage_file.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return {}

        # Ignore registry files created with unsupported formats.
        if payload.get("version") != REGISTRY_VERSION:
            return {}

        records: dict[tuple[int, str], ExportedExamRecord] = {}

        for item in payload.get("exported_exams", []):
            try:
                record = ExportedExamRecord.from_dict(item)
            except (KeyError, TypeError, ValueError):
                # Skip malformed entries while keeping valid ones.
                continue

            records[record.dedupe_key()] = record

        return records

    def _save_records(
        self,
        records: dict[tuple[int, str], ExportedExamRecord],
    ) -> None:
        """
        Persist registry contents to disk.

        Records are written in a deterministic order to make debugging,
        testing, and version-control diffs easier to read.
        """
        self._storage_file.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "version": REGISTRY_VERSION,
            "exported_exams": [
                record.to_dict()
                for record in sorted(
                    records.values(),
                    key=lambda record: (
                        record.exam_date,
                        record.course_id,
                    ),
                )
            ],
        }

        self._storage_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )