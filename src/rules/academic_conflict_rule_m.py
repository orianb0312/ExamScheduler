from datetime import date
from typing import Dict, List, Tuple
from src.interfaces import ISchedulingRule
from src.models.academic import Course, ProgramAffiliation
from src.models.enums import RequirementType

class AcademicConflictRule(ISchedulingRule):
    """
    Implements the core Version 1.0 academic conflict rule:
    No two exams belonging to the same program AND same year may be
    scheduled on the same date, UNLESS both courses are Elective in
    that shared program/year combination.
    """

    def is_valid(self, attempt_state: Dict[Course, date]) -> bool:
        """
        Checks all scheduled course pairs for critical conflicts.
        Returns False as soon as a conflict is found (fail-fast).
        """
        scheduled_courses = list(attempt_state.keys())

        for i in range(len(scheduled_courses)):
            for j in range(i + 1, len(scheduled_courses)):
                course1 = scheduled_courses[i]
                course2 = scheduled_courses[j]

                if attempt_state[course1] == attempt_state[course2]:
                    if self._courses_have_critical_conflict(course1, course2):
                        return False

        return True

    def _courses_have_critical_conflict(
        self, course1: Course, course2: Course
    ) -> bool:
        """
        Returns True if any shared (program, year) affiliation pair
        constitutes a critical conflict.

        A conflict is critical when at least one of the two courses
        is Obligatory in the shared program/year — i.e., the only
        allowed same-day case is when BOTH are Elective.
        """
        for affil1 in course1.affiliations:
            for affil2 in course2.affiliations:
                if self._share_program_and_year(affil1, affil2):
                    if not self._both_elective(affil1, affil2):
                        return True  # Critical conflict found
        return False
    
    @staticmethod
    def _share_program_and_year(affil1: ProgramAffiliation, affil2: ProgramAffiliation) -> bool:
        """Returns True if both affiliations belong to the same program and year."""
        return affil1.program_id == affil2.program_id and affil1.year == affil2.year

    @staticmethod
    def _both_elective(affil1: ProgramAffiliation, affil2: ProgramAffiliation) -> bool:
        """Returns True only if both affiliations are Elective (the allowed exception)."""
        return (
            affil1.requirement_type == RequirementType.ELECTIVE
            and affil2.requirement_type == RequirementType.ELECTIVE
        )