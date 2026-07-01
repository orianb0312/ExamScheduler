"""Build calendar files natively from UI schedules and track export history."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

from src.models.enums import Semester, Term
from src.output.output_models import ScheduledExam
from src.services.calendar_export_registry import CalendarExportRegistry
from src.services.schedule_output_service import ScheduleExamDisplay, ScheduleSystem
from src.output.ics_formatter import ICSFormatter

_SEMESTER_ALIASES = {
    "fall": Semester.FALL,
    "spri": Semester.SPRING,
    "spring": Semester.SPRING,
    "summ": Semester.SUMMER,
    "summer": Semester.SUMMER,
}

_TERM_ALIASES = {
    "aleph": Term.ALEPH,
    "bet": Term.BET,
    "gimel": Term.GIMEL,
}

@dataclass(frozen=True)
class CalendarExportResult:
    """Outcome of generating ICS calendar integration data."""
    event_count: int
    skipped_without_date: int
    ics_content: str = ""

class CalendarExportError(ValueError):
    """Raised when there is nothing valid to publish."""

class ScheduleCalendarExportService:
    """Coordinates extracting exams, mapping them to structured domains, and formatting to ICS."""

    def __init__(self, storage_dir: str | Path) -> None:
        self._storage_dir = Path(storage_dir)
        self._registry = CalendarExportRegistry(self._storage_dir / "export_registry.json")

    @property
    def registry(self) -> CalendarExportRegistry:
        return self._registry

    def has_exported_entries(self) -> bool:
        return not self._registry.is_empty()

    def _build_structured_data(self, exams: list[ScheduledExam]) -> dict[Semester, dict[Term, list[ScheduledExam]]]:
        """Maps flat exam lists into the structured dictionary required by IOutputFormatter."""
        structured_data: dict[Semester, dict[Term, list[ScheduledExam]]] = {}
        for exam in exams:
            if exam.semester not in structured_data:
                structured_data[exam.semester] = {}
            if exam.term not in structured_data[exam.semester]:
                structured_data[exam.semester][exam.term] = []
            structured_data[exam.semester][exam.term].append(exam)
        return structured_data

    def export_schedule(self, schedule: ScheduleSystem | None) -> CalendarExportResult:
        new_exams, skipped = self._exams_from_schedule(schedule)
        if not new_exams:
            raise CalendarExportError("The selected schedule has no dated exams to export.")

        old_exams = list(self._registry.all_exams())
        new_keys = {(exam.course_id, exam.exam_date.isoformat()) for exam in new_exams}

        # Only explicitly cancel exams that are completely missing from the new schedule
        exams_to_cancel = [
            exam for exam in old_exams
            if (exam.course_id, exam.exam_date.isoformat()) not in new_keys
        ]

        formatter = ICSFormatter()
        ics_content = formatter.format(
            publish_data=self._build_structured_data(new_exams),
            cancel_data=self._build_structured_data(exams_to_cancel)
        )

        self._registry.clear()
        self._registry.add_exams(new_exams)

        return CalendarExportResult(len(new_exams), skipped, ics_content)

    def revoke_all_exported(self) -> CalendarExportResult:
        exams = list(self._registry.all_exams())
        if not exams:
            raise CalendarExportError("No marked calendar entries were found to revoke.")

        formatter = ICSFormatter()
        ics_content = formatter.format(cancel_data=self._build_structured_data(exams))

        self._registry.clear()
        return CalendarExportResult(len(exams), 0, ics_content)

    def _exams_from_schedule(self, schedule: ScheduleSystem | None) -> tuple[list[ScheduledExam], int]:
        if schedule is None:
            raise CalendarExportError("No schedule is currently selected.")

        exams: list[ScheduledExam] = []
        skipped = 0

        for period in schedule.periods:
            semester = _parse_semester(period.semester_label)
            term = _parse_term(period.term_label)

            for exam in period.exams:
                if exam.exam_date is None:
                    skipped += 1
                    continue
                exams.append(ScheduledExam(
                    course_name=exam.course_name,
                    course_id=exam.course_id if exam.course_id is not None else 99999,
                    semester=semester,
                    term=term,
                    exam_date=exam.exam_date,
                    instructor=exam.instructor or "TBD",
                ))

        return exams, skipped

def _parse_semester(label: str) -> Semester:
    normalized = " ".join(str(label).casefold().split())
    if normalized in _SEMESTER_ALIASES: return _SEMESTER_ALIASES[normalized]
    raise CalendarExportError(f"Unknown semester label: {label!r}")

def _parse_term(label: str) -> Term:
    normalized = " ".join(str(label).casefold().split())
    if normalized in _TERM_ALIASES: return _TERM_ALIASES[normalized]
    raise CalendarExportError(f"Unknown term label: {label!r}")