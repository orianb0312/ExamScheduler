"""V1 academic conflict rule implemented through the shared rule interface."""

from datetime import date
from typing import Dict
from src.interfaces import ISchedulingRule
from src.models.academic import Course
from src.models.enums import RequirementType


class AcademicConflictRule(ISchedulingRule):
    """
    Implements the version 1.0 rule: Two exams from the same year and in the same program may
    not be scheduled on the same day, unless both exams are for elective courses.
    """

    def is_valid(self, attempt_state: Dict[Course, date]) -> bool:
        """Reject same-day conflicts for cohorts where at least one course is mandatory."""
        # Grouping by date keeps the common no-conflict path small.
        dates_to_courses = {}
        for course, exam_date in attempt_state.items():
            if exam_date not in dates_to_courses:
                dates_to_courses[exam_date] = []
            dates_to_courses[exam_date].append(course)

        for exam_date, courses in dates_to_courses.items():
            if len(courses) < 2:
                continue

            # Checking each pair of courses that are scheduled on the same day
            for i in range(len(courses)):
                for j in range(i + 1, len(courses)):
                    if self._has_critical_conflict(courses[i], courses[j]):
                        return False
        return True

    def _has_critical_conflict(self, c1: Course, c2: Course) -> bool:
        """Return True when two courses share a cohort and need separate days."""
        for aff1 in c1.affiliations:
            for aff2 in c2.affiliations:
                # Checking if they are in the same program in the same year
                if aff1.program_id == aff2.program_id and aff1.year == aff2.year:
                    # A critical conflict exists if at least one of them is mandatory.
                    if (aff1.requirement_type == RequirementType.OBLIGATORY or
                            aff2.requirement_type == RequirementType.OBLIGATORY):
                        return True
        return False
