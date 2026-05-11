import time
from datetime import date, timedelta
from typing import List, Dict, Optional
from src.models.academic import Course
from src.models.scheduling import ExamPeriod
from src.interfaces import ISchedulingRule


class Scheduler:
    """
        The core engine responsible for generating all valid exam schedule permutations.
        Uses a backtracking approach to find collision-free systems.
    """

    def __init__(self, rules: List[ISchedulingRule]):
        self.rules = rules
        self.all_valid_schedules: List[Dict[Course, date]] = []

    def run(self, courses: List[Course], period: ExamPeriod) -> List[Dict[Course, date]]:
        """
            Initializes the recursive generation process and returns all found schedules.
        """
        self.all_valid_schedules = []
        available_dates = self._get_available_dates(period)

        # Start the recursive search
        self._backtrack({}, courses, available_dates)

        return self.all_valid_schedules

    def _get_available_dates(self, period: ExamPeriod) -> List[date]:
        """Generates all valid dates within the period, excluding blocked dates."""
        available = []
        current = period.start_date
        while current <= period.end_date:
            if period.is_date_valid(current):
                available.append(current)
            current += timedelta(days=1)
        return available

    def _backtrack(self, current_state: Dict[Course, date], remaining_courses: List[Course], available_dates: List[date]):
        """Recursive backtracking function to build exam systems."""
        # Base Case: All courses have been scheduled
        if not remaining_courses:
            self.all_valid_schedules.append(current_state.copy())
            return

        # Pick the next course to schedule
        course = remaining_courses[0]
        next_remaining = remaining_courses[1:]

        for exam_date in available_dates:
            # Create a potential assignment
            current_state[course] = exam_date

            # Validate the assignment against all rules (Conflict Logic)
            if self._is_state_valid(current_state):
                # Recurse to the next course
                self._backtrack(current_state, next_remaining, available_dates)

            # Backtrack: Remove the assignment before trying the next date
            del current_state[course]

    def _is_state_valid(self, state: Dict[Course, date]) -> bool:
        """Checks the current assignment state against all registered scheduling rules."""
        for rule in self.rules:
            if not rule.is_valid(state):
                return False
        return True