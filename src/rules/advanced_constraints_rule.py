from datetime import date
from typing import Dict
from src.interfaces import ISchedulingRule
from src.models.academic import Course
from src.models.enums import RequirementType


class AdvancedConstraintsRule(ISchedulingRule):
    """
    Implements advanced scheduling constraints:
    1. Elective Conflict Limit: Maximum allowed same-day conflicts between elective courses per program.
    2. Mandatory Exam Span: Minimum calendar days required from the first to the last mandatory exam per cohort.
    3. Daily Exam Cap: Absolute maximum number of exams allowed to be scheduled on any single calendar day.
    """

    def __init__(self, max_elective_conflicts: int, min_mandatory_span: int, max_daily_exams: int):
        """
        Initializes the rule with configurable thresholds for each constraint.
        """
        self.max_elective_conflicts = max_elective_conflicts
        self.min_mandatory_span = min_mandatory_span
        self.max_daily_exams = max_daily_exams

    def is_valid(self, attempt_state: Dict[Course, date]) -> bool:
        """
        Evaluates the current state of the schedule against all three advanced constraints.
        Returns False immediately if any constraint is violated, pruning the search branch.
        """
        # Constraint 3: Daily Exam Cap. Checked first as it's an O(N) operation and fastest to fail.
        if not self._check_daily_cap(attempt_state):
            return False

        # Constraint 2: Mandatory Exam Span.
        if not self._check_mandatory_span(attempt_state):
            return False

        # Constraint 1: Elective Conflict Limits.
        if not self._check_elective_conflicts(attempt_state):
            return False

        return True

    def _check_daily_cap(self, attempt_state: Dict[Course, date]) -> bool:
        """
        Validates that no calendar date exceeds the maximum allowed number of exams (max_daily_exams).
        """
        date_counts = {}
        for exam_date in attempt_state.values():
            date_counts[exam_date] = date_counts.get(exam_date, 0) + 1
            if date_counts[exam_date] > self.max_daily_exams:
                return False
        return True

    def _check_mandatory_span(self, attempt_state: Dict[Course, date]) -> bool:
        """
        Validates that the timeframe (span in days) between the very first and the very last
        mandatory exam for any specific cohort (program + year) meets the min_mandatory_span requirement.
        """
        cohort_mandatory_dates = {}
        # Group exam dates by cohort strictly for obligatory courses
        for course, exam_date in attempt_state.items():
            for aff in course.affiliations:
                if aff.requirement_type == RequirementType.OBLIGATORY:
                    key = (aff.program_id, aff.year)
                    if key not in cohort_mandatory_dates:
                        cohort_mandatory_dates[key] = []
                    cohort_mandatory_dates[key].append(exam_date)

        # Evaluate the day span for each cohort
        for dates in cohort_mandatory_dates.values():
            # A span can only be calculated if the cohort has at least two mandatory exams scheduled
            if len(dates) > 1:
                span = abs((max(dates) - min(dates)).days)
                if span < self.min_mandatory_span:
                    return False
        return True

    def _check_elective_conflicts(self, attempt_state: Dict[Course, date]) -> bool:
        """
        Validates that the total number of same-day conflicts between elective courses
        within a single study program does not exceed the max_elective_conflicts threshold.
        """
        program_date_counts = {}
        # Count how many elective exams a program has on any given date
        for course, exam_date in attempt_state.items():
            for aff in course.affiliations:
                if aff.requirement_type == RequirementType.ELECTIVE:
                    key = (aff.program_id, exam_date)
                    program_date_counts[key] = program_date_counts.get(key, 0) + 1

        program_conflicts = {}
        # Calculate the actual number of pairwise conflicts based on the date counts
        for (prog_id, _), count in program_date_counts.items():
            if count > 1:
                # If N exams are on the same day, the number of conflicts (unique pairs) is N*(N-1)/2
                conflicts = (count * (count - 1)) // 2
                program_conflicts[prog_id] = program_conflicts.get(prog_id, 0) + conflicts

        # Verify that no program exceeds the maximum allowed conflicts
        for total_conflicts in program_conflicts.values():
            if total_conflicts > self.max_elective_conflicts:
                return False
        return True