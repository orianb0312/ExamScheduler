from __future__ import annotations

from dataclasses import dataclass

from src.models.academic import Course
from src.services.file_loading_service import LoadedSchedulerInput, ProgramSummary

BASELINE_PROGRAM_NAMES: dict[str, str] = {
    "83101": "Computer Engineering",
    "83102": "Electrical Engineering",
    "83103": "Electrical Engineering - Neuro Engineering Track",
    "83104": "Industrial Engineering and Information Systems",
    "83105": "Computer Engineering - Computer Hardware Track",
    "83107": "Data Engineering",
    "83108": "Software Engineering",
    "83109": "Materials Engineering",
    "83115": "Electrical Engineering - Biomedical Engineering Track",
    "83182": "Electrical Engineering - Quantum Engineering Track",
}


@dataclass(frozen=True)
class CourseRow:
    course_id: str
    name: str
    year: int
    semester: str
    status: str
    assessment: str

    @property
    def requirement(self) -> str:
        return self.status


class SelectedProgramsViewModel:
    """Resolve selected program IDs into display rows and course-detail rows."""

    def __init__(self) -> None:
        self._all_available_programs: dict[str, ProgramSummary] = {}
        self._all_courses: tuple[Course, ...] = ()
        self._selected_ids: list[str] = []

    def update_available_programs(self, loaded_data: LoadedSchedulerInput | None) -> None:
        if not loaded_data or not loaded_data.programs:
            self._all_available_programs = {}
            self._all_courses = ()
            return

        self._all_available_programs = {
            str(p.program_id): p for p in loaded_data.programs
        }
        self._all_courses = loaded_data.courses

    def set_selected_program_ids(self, program_ids: list[str]) -> None:
        self._selected_ids = list(program_ids)

    def get_selected_program_details(self) -> list[dict[str, str]]:
        details = []
        for pid in self._selected_ids:
            resolved_name = BASELINE_PROGRAM_NAMES.get(pid, f"Program {pid}")
            details.append({"program_id": pid, "display_name": resolved_name})
        return details

    def get_courses_for_program(self, program_id: str) -> list[CourseRow]:
        clean_pid = str(program_id).strip()
        pid_int = _try_parse_int(clean_pid)
        if pid_int is None:
            return []

        rows: list[CourseRow] = []
        for course in self._all_courses:
            for affiliation in course.affiliations:
                if affiliation.program_id != pid_int:
                    continue
                rows.append(CourseRow(
                    course_id=str(course.course_id),
                    name=course.name,
                    year=affiliation.year,
                    semester=_enum_display_value(affiliation.semester),
                    status=_enum_display_value(affiliation.requirement_type),
                    assessment=_evaluation_display_value(course.evaluation),
                ))

        rows.sort(key=lambda r: (r.year, _semester_sort_key(r.semester), r.course_id))
        return rows

    def get_program_display_name(self, program_id: str) -> str:
        clean_pid = str(program_id).strip()
        return BASELINE_PROGRAM_NAMES.get(clean_pid, f"Program {clean_pid}")


def _try_parse_int(value: str) -> int | None:
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _semester_sort_key(semester: str) -> int:
    order = {"FALL": 0, "SPRI": 1, "SUMM": 2}
    return order.get(semester, 99)


def _enum_display_value(value) -> str:
    raw_value = getattr(value, "value", value)
    if raw_value is None:
        return ""
    return str(raw_value)


def _evaluation_display_value(value) -> str:
    if value is None:
        return ""
    return value.__class__.__name__
