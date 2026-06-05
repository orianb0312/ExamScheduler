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
    requirement: str
    assessment: str


class SelectedProgramsViewModel:

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
                # Safely extract string values from Enums and class type
                semester_val = affiliation.semester.value if affiliation.semester else ""
                req_val = affiliation.requirement_type.value if affiliation.requirement_type else ""
                assessment_val = course.evaluation.__class__.__name__ if course.evaluation else ""
                rows.append(CourseRow(
                    course_id=str(course.course_id),
                    name=course.name,
                    year=affiliation.year,
                    semester=semester_val,
                    requirement=req_val,
                    assessment=assessment_val,
                ))

        rows.sort(key=lambda r: r.course_id)
        return rows

    def get_program_display_name(self, program_id: str) -> str:
        clean_pid = str(program_id).strip()
        return BASELINE_PROGRAM_NAMES.get(clean_pid, f"Program {clean_pid}")


def _try_parse_int(value: str) -> int | None:
    try:
        return int(value)
    except (ValueError, TypeError):
        return None