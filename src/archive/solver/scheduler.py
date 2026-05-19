import time
from datetime import date, timedelta
from itertools import product
from pathlib import Path
from typing import List, Dict, Set, Optional, Generator

from src.models.academic import Course
from src.models.scheduling import ExamPeriod
from src.interfaces import ISchedulingRule


class Scheduler:
    def __init__(self, rules: List[ISchedulingRule]):
        # The rules we must follow to avoid exam clashes
        self.rules = rules

    def run_to_file(
            self,
            courses: List[Course],
            period: ExamPeriod,
            output_path: Path,
            enforce_unique: bool = False
    ) -> int:
        # Start the clock to make sure we don't pass the 30-second limit
        start_time = time.perf_counter()

        # Get all dates that are actually available for exams
        available_dates = self._get_available_dates(period)

        # Split courses into groups (components). This makes the solver much faster
        components = self._build_components(courses)

        component_solutions = []
        for comp in components:
            # Find all valid date combinations for this specific group
            solutions = list(self._solve_component(comp, available_dates))
            if not solutions:
                # If one group can't be scheduled, there is no valid solution for the whole faculty
                print(f"Warning: No solutions for component starting with {comp[0].name}")
                return 0
            component_solutions.append(solutions)

        total_schedules = 0
        # Open the file once and stream the results to save memory and time
        with open(output_path, "w", encoding="utf-8") as f:
            # 'product' combines solutions from different groups to create a full schedule
            for combination in product(*component_solutions):
                full_schedule = {}
                for sol in combination:
                    full_schedule.update(sol)

                total_count = total_schedules + 1
                total_schedules = total_count

                # Write the specific result to the file
                self._write_schedule(f, total_schedules, full_schedule)

                # Safety check: If we have millions of results, stop before the 30-second deadline
                if total_schedules % 10000 == 0 and (time.perf_counter() - start_time) > 25:
                    f.write(f"\n... Stopped at {total_schedules} due to time limit ...\n")
                    break

        duration = time.perf_counter() - start_time
        print(f"Done! Found {total_schedules} solutions in {duration:.2f}s")
        return total_schedules

    def _solve_component(self, component: List[Course], dates: List[date]) -> Generator[Dict[Course, date], None, None]:
        """
        Standard Backtracking algorithm to find all valid date assignments.
        """

        def backtrack(index, current_assignment):
            # If we reached the end of the list, we found a full valid group solution
            if index == len(component):
                yield current_assignment.copy()
                return

            course = component[index]
            # Try to put the exam on every available date
            for d in dates:
                current_assignment[course] = d
                # Only continue if the current date doesn't break any rules
                if self._is_locally_valid(current_assignment):
                    yield from backtrack(index + 1, current_assignment)

            # Clean up the dictionary before going back up the recursion tree
            if course in current_assignment:
                del current_assignment[course]

        yield from backtrack(0, {})

    def _is_locally_valid(self, assignment: Dict[Course, date]) -> bool:
        """ Checks the current assignment against the academic rule (V1.0). """
        for rule in self.rules:
            if not rule.is_valid(assignment):
                return False
        return True

    def _get_available_dates(self, period: ExamPeriod) -> List[date]:
        """ Collects all dates in the period that are not blocked by Saturdays or holidays. """
        dates = []
        curr = period.start_date
        while curr <= period.end_date:
            if period.is_date_valid(curr):
                dates.append(curr)
            curr += timedelta(days=1)
        return dates

    def _build_components(self, courses: List[Course]) -> List[List[Course]]:
        """
        Groups courses by study year. Since Version 1.0 only cares about
        conflicts within the same year/program, we can solve each year separately.
        """
        from collections import defaultdict
        years = defaultdict(list)
        for course in courses:
            # Assign course to its study year group
            year = course.affiliations[0].year if course.affiliations else 1
            years[year].append(course)

        return list(years.values())

    def _write_schedule(self, file, num, schedule):
        """
        Writes the schedule to the file in a human-readable format.
        Sorted by date as required in the project document.
        """
        file.write(f"Schedule #{num}\n")
        # Sorting exams by date for the final output
        sorted_exams = sorted(schedule.items(), key=lambda x: x[1])
        for course, d in sorted_exams:
            file.write(f"{d.strftime('%d-%m-%Y')} | {course.course_id} | {course.name} | {course.instructor}\n")
        file.write("-" * 40 + "\n")