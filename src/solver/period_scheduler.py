import time
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import chain
from itertools import product
from typing import Dict, Generator, Iterator, List, Set

from src.output.output_manager import TextOutputManager
from src.interfaces import ISchedulingRule
from src.models.academic import Course
from src.models.scheduling import ExamPeriod
from src.rules.advanced_constraints_rule import AdvancedConstraintsRule
from src.sorting.schedule_priority import (
    SchedulePrioritySorter,
    sortable_exams_from_assignment,
)


DEFAULT_SORTED_PERIOD_SCHEDULE_LIMIT = 1_000_000


@dataclass(frozen=True)
class _CourseKey:
    """
    Identity-preserving adapter used only when calling rule objects.
    Course.__eq__ is based on course_id, so duplicate IDs would otherwise
    collapse inside rule dictionaries.
    """
    index: int
    course: Course

    def __getattr__(self, name):
        return getattr(self.course, name)


class Scheduler:
    """
    Faster exact scheduler for the current exam-conflict model.

    Main improvements over dev_scheduler:
    - Builds a conflict graph once.
    - Splits by connected graph components instead of first affiliation year.
    - Uses MRV ordering while backtracking.
    - Checks only assigned neighbors instead of rescanning every course pair.
    - Stores assignments by course index so duplicate course IDs do not collide.
    """

    def __init__(self, rules: List[ISchedulingRule], validate_full_schedules: bool = False):
        self.rules = rules
        self.validate_full_schedules = validate_full_schedules
        self._course_keys: List[_CourseKey] = []

    def iter_assignments(
        self,
        courses: List[Course],
        period: ExamPeriod,
    ) -> Iterator[Dict[int, date]]:
        self._course_keys = [_CourseKey(index, course) for index, course in enumerate(courses)]

        available_dates = self._get_available_dates(period)
        if not courses or not available_dates:
            return

        conflict_graph = self._build_conflict_graph(courses)
        components = self._get_connected_components(courses, conflict_graph)

        component_solutions = []
        for component in components:
            solutions = list(self._solve_component(component, available_dates, conflict_graph))
            if not solutions:
                return
            component_solutions.append(solutions)

        for combination in product(*component_solutions):
            full_assignment: Dict[int, date] = {}
            for partial_assignment in combination:
                full_assignment.update(partial_assignment)

            # Optional guard for future rules that are not fully captured by pairwise edges.
            if self.validate_full_schedules and not self._rules_accept_assignment(full_assignment):
                continue

            yield full_assignment

    def count_assignments(self, courses: List[Course], period: ExamPeriod) -> int:
        return sum(1 for _ in self.iter_assignments(courses, period))

    def run_to_output(
        self,
        courses: List[Course],
        period: ExamPeriod,
        output_manager: TextOutputManager,
        append: bool = False,
        write_header: bool = True,
        sort_priority: List[str] | tuple[str, ...] = (),
        max_sorted_schedules: int = DEFAULT_SORTED_PERIOD_SCHEDULE_LIMIT,
    ) -> int:
        start_time = time.perf_counter()

        available_dates = self._get_available_dates(period)
        if not courses or not available_dates:
            return self._write_empty_output(output_manager, period, append, write_header)

        assignments = self.iter_assignments(courses, period)
        if sort_priority:
            assignments_to_write = self._sorted_assignments(
                courses,
                self._collect_assignments_for_sorting(
                    assignments,
                    max_sorted_schedules,
                ),
                sort_priority,
            )
            if not assignments_to_write:
                return 0
        else:
            first_assignment = next(assignments, None)
            if first_assignment is None:
                return 0
            assignments_to_write = chain([first_assignment], assignments)

        output_manager._ensure_dir_exists()
        full_path = output_manager.get_full_path()

        total_schedules = 0
        mode = "a" if append else "w"
        with open(full_path, mode, encoding="utf-8") as f:
            if write_header:
                f.write("OFFICIAL UNIVERSITY MASTER EXAM SCHEDULE\n")
                f.write("=" * 65 + "\n\n")

            for assignment in assignments_to_write:
                total_schedules += 1
                self._write_schedule(f, total_schedules, courses, period, assignment)

        duration = time.perf_counter() - start_time
        print(
            f"New scheduler completed in {duration:.2f} seconds. "
            f"Found {total_schedules:,} solutions."
        )
        return total_schedules

    def _collect_assignments_for_sorting(
        self,
        assignments: Iterator[Dict[int, date]],
        max_sorted_schedules: int,
    ) -> List[Dict[int, date]]:
        if max_sorted_schedules <= 0:
            raise ValueError("max_sorted_schedules must be greater than zero.")

        collected: List[Dict[int, date]] = []
        for assignment in assignments:
            if len(collected) >= max_sorted_schedules:
                raise ValueError(
                    "Period sorting would require materializing more than "
                    f"{max_sorted_schedules:,} schedules in memory. "
                    "Narrow the selected period, raise the sorted-period limit, "
                    "or run this period without sorting."
                )
            collected.append(assignment)

        return collected

    def _sorted_assignments(
        self,
        courses: List[Course],
        assignments: List[Dict[int, date]],
        sort_priority: List[str] | tuple[str, ...],
    ) -> List[Dict[int, date]]:
        return SchedulePrioritySorter().sort(
            assignments,
            sort_priority,
            lambda assignment: sortable_exams_from_assignment(
                courses,
                assignment.items(),
            ),
        )

    def _write_empty_output(
        self,
        output_manager: TextOutputManager,
        period: ExamPeriod,
        append: bool,
        write_header: bool,
    ) -> int:
        output_manager._ensure_dir_exists()
        mode = "a" if append else "w"
        with open(output_manager.get_full_path(), mode, encoding="utf-8") as f:
            if write_header:
                f.write("OFFICIAL UNIVERSITY MASTER EXAM SCHEDULE\n")
                f.write("=" * 65 + "\n\n")
            f.write(f"=== SEMESTER: {period.semester.value} ===\n")
            f.write(f"  [TERM: {period.term.value}]\n")
            f.write("  EMPTY SCHEDULE: No exams have been scheduled for this period.\n\n")
        return 0

    def _get_available_dates(self, period: ExamPeriod) -> List[date]:
        available = []
        current = period.start_date

        while current <= period.end_date:
            if period.is_date_valid(current):
                available.append(current)
            current += timedelta(days=1)

        return available

    def _build_conflict_graph(self, courses: List[Course]) -> Dict[int, Set[int]]:
        graph = {index: set() for index in range(len(courses))}
        dummy_date = date(2099, 1, 1)

        for left in range(len(courses)):
            for right in range(left + 1, len(courses)):
                if self._pair_conflicts(left, right, dummy_date):
                    graph[left].add(right)
                    graph[right].add(left)

        return graph

    def _pair_conflicts(self, left: int, right: int, exam_date: date) -> bool:
        state = {
            self._course_keys[left]: exam_date,
            self._course_keys[right]: exam_date,
        }

        for rule in self.rules:
            validator = getattr(rule, "is_partial_valid", rule.is_valid)
            if not validator(state):
                return True
        return False

    def _get_connected_components(
        self,
        courses: List[Course],
        graph: Dict[int, Set[int]],
    ) -> List[List[int]]:
        if self._requires_global_component_search():
            return [list(range(len(courses)))]

        visited = set()
        components = []

        for start in range(len(courses)):
            if start in visited:
                continue

            stack = [start]
            component = []
            visited.add(start)

            while stack:
                current = stack.pop()
                component.append(current)

                for neighbor in graph[current]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        stack.append(neighbor)

            components.append(component)

        return components

    def _requires_global_component_search(self) -> bool:
        return any(isinstance(rule, AdvancedConstraintsRule) for rule in self.rules)

    def _solve_component(
        self,
        component: List[int],
        available_dates: List[date],
        conflict_graph: Dict[int, Set[int]],
    ) -> Generator[Dict[int, date], None, None]:
        current_assignment: Dict[int, date] = {}

        def backtrack():
            if len(current_assignment) == len(component):
                yield current_assignment.copy()
                return

            course_index = self._select_next_course_mrv(
                component,
                available_dates,
                conflict_graph,
                current_assignment,
            )

            for exam_date in available_dates:
                if self._can_assign(course_index, exam_date, conflict_graph, current_assignment):
                    current_assignment[course_index] = exam_date
                    yield from backtrack()
                    del current_assignment[course_index]

        yield from backtrack()

    def _select_next_course_mrv(
        self,
        component: List[int],
        available_dates: List[date],
        conflict_graph: Dict[int, Set[int]],
        current_assignment: Dict[int, date],
    ) -> int:
        unassigned = [course_index for course_index in component if course_index not in current_assignment]

        return min(
            unassigned,
            key=lambda course_index: (
                self._count_valid_dates(
                    course_index,
                    available_dates,
                    conflict_graph,
                    current_assignment,
                ),
                -len(conflict_graph[course_index]),
            ),
        )

    def _count_valid_dates(
        self,
        course_index: int,
        available_dates: List[date],
        conflict_graph: Dict[int, Set[int]],
        current_assignment: Dict[int, date],
    ) -> int:
        return sum(
            1
            for exam_date in available_dates
            if self._can_assign(course_index, exam_date, conflict_graph, current_assignment)
        )

    """def _can_assign(
        self,
        course_index: int,
        exam_date: date,
        conflict_graph: Dict[int, Set[int]],
        current_assignment: Dict[int, date],
    ) -> bool:
        return all(
            current_assignment.get(conflicting_course) != exam_date
            for conflicting_course in conflict_graph[course_index]
        )"""

    def _can_assign(
            self,
            course_index: int,
            exam_date: date,
            conflict_graph: Dict[int, Set[int]],
            current_assignment: Dict[int, date],
    ) -> bool:
        if any(
                current_assignment.get(conflicting_course) == exam_date
                for conflicting_course in conflict_graph[course_index]
        ):
            return False

        attempt = current_assignment.copy()
        attempt[course_index] = exam_date
        return self._rules_accept_assignment(
            attempt,
            is_complete=len(attempt) == len(self._course_keys),
        )

    def _rules_accept_assignment(
        self,
        assignment: Dict[int, date],
        is_complete: bool = True,
    ) -> bool:
        state = {
            self._course_keys[course_index]: exam_date
            for course_index, exam_date in assignment.items()
        }

        for rule in self.rules:
            validator = rule.is_valid if is_complete else getattr(
                rule,
                "is_partial_valid",
                rule.is_valid,
            )
            if not validator(state):
                return False
        return True

    def _write_schedule(
        self,
        file,
        schedule_number: int,
        courses: List[Course],
        period: ExamPeriod,
        assignment: Dict[int, date],
    ) -> None:
        file.write(f"Schedule #{schedule_number}\n")
        file.write(f"=== SEMESTER: {period.semester.value} ===\n")
        file.write(f"  [TERM: {period.term.value}]\n")
        file.write("  " + "-" * 40 + "\n")

        sorted_items = sorted(
            assignment.items(),
            key=lambda item: (item[1], courses[item[0]].name.lower()),
        )

        for course_index, exam_date in sorted_items:
            course = courses[course_index]
            file.write(f"  {course.name} | {exam_date} | {course.instructor}\n")

        file.write("\n" + "*" * 70 + "\n\n")
