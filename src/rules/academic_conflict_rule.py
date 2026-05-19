from datetime import date
from typing import Dict, List
from src.interfaces import ISchedulingRule
from src.models.academic import Course, ProgramAffiliation
from src.models.enums import RequirementType


class AcademicConflictRule(ISchedulingRule):
    """
    Implements the version 1.0 rule: Two exams from the same year and in the same program may
    not be scheduled on the same day, unless both exams are for elective courses.
    """

    def is_valid(self, attempt_state: Dict[Course, date]) -> bool:
        # Check only for courses assigned on the exact same date
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
        for aff1 in c1.affiliations:
            for aff2 in c2.affiliations:
                # Checking if they are in the same program in the same year
                if aff1.program_id == aff2.program_id and aff1.year == aff2.year:
                    # A critical conflict exists if at least one of them is mandatory.
                    if (aff1.requirement_type == RequirementType.OBLIGATORY or
                            aff2.requirement_type == RequirementType.OBLIGATORY):
                        return True
        return False