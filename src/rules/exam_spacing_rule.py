"""Stage 3 minimum-spacing constraints for mandatory and cohort exams."""

from datetime import date
from typing import Dict
from src.interfaces import ISchedulingRule
from src.models.academic import Course
from src.models.enums import RequirementType


class ExamSpacingRule(ISchedulingRule):
    """
    Implements the minimum day spacing constraints for the scheduler (Constraints 2.1 and 2.2).
    - Constraint 2.1: Mandatory courses in the same program and year must be spaced by at least 'k' days.
    - Constraint 2.2: Any two courses in the same program and year must be spaced by at least 'm' days.

    Note: The day difference is calculated absolutely using calendar dates,
    which implicitly includes weekends (Saturdays) and holidays in the count.
    """

    def __init__(self, k_days_mandatory: int, m_days_any: int):
        """
        Initialize the spacing rule with configurable minimum day gaps.
        """
        self.k_days_mandatory = k_days_mandatory
        self.m_days_any = m_days_any

    def is_valid(self, attempt_state: Dict[Course, date]) -> bool:
        """
        Evaluates a partial or complete schedule attempt to ensure no spacing rules are violated.
        Returns False immediately if any scheduled pair is placed too closely together.
        """
        courses = list(attempt_state.keys())

        # Iterate over every unique pair of scheduled courses to check their date distance
        for i in range(len(courses)):
            for j in range(i + 1, len(courses)):
                c1 = courses[i]
                c2 = courses[j]
                date1 = attempt_state[c1]
                date2 = attempt_state[c2]

                # Calculate the absolute difference in days between the two exam dates
                delta_days = abs((date1 - date2).days)

                # If the specific pair violates the spacing rules, the entire schedule branch is invalid
                if self._has_spacing_conflict(c1, c2, delta_days):
                    return False

        return True

    def _has_spacing_conflict(self, c1: Course, c2: Course, delta_days: int) -> bool:
        """
        Checks if two courses violate the defined 'k' or 'm' spacing constraints based on their affiliations.
        """
        for aff1 in c1.affiliations:
            for aff2 in c2.affiliations:
                # Spacing rules are strictly applied only to courses sharing the same program and academic year cohort
                if aff1.program_id == aff2.program_id and aff1.year == aff2.year:

                    # Constraint 2.2: Any two courses in the same cohort must have at least 'm' days between them
                    if delta_days < self.m_days_any:
                        return True

                    # Constraint 2.1: Two mandatory (obligatory) courses must have at least 'k' days between them
                    both_obligatory = (
                            aff1.requirement_type == RequirementType.OBLIGATORY
                            and aff2.requirement_type == RequirementType.OBLIGATORY
                    )
                    if both_obligatory and delta_days < self.k_days_mandatory:
                        return True

        # No conflict detected for this specific pair
        return False
