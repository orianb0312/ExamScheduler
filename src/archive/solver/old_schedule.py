import time
from datetime import date, timedelta
from itertools import product
from typing import List, Dict, Set

from src.models.academic import Course
from src.models.scheduling import ExamPeriod
from src.interfaces import ISchedulingRule


class Scheduler:
    """
    Optimized scheduler:
    - Builds a conflict graph between courses.
    - Splits independent connected components.
    - Solves each component separately.
    - Combines component schedules using Cartesian product.
    - Returns ALL valid schedules.
    """

    def __init__(self, rules: List[ISchedulingRule]):
        self.rules = rules
        self.all_valid_schedules: List[Dict[Course, date]] = []

    def run(self, courses: List[Course], period: ExamPeriod) -> List[Dict[Course, date]]:
        start_time = time.perf_counter()

        self.all_valid_schedules = []
        available_dates = self._get_available_dates(period)

        if not courses:
            return []

        conflict_graph = self._build_conflict_graph(courses)
        components = self._get_connected_components(courses, conflict_graph)

        component_solutions = []

        for component in components:
            solutions = []
            ordered_courses = sorted(
                component,
                key=lambda c: len(conflict_graph[c]),
                reverse=True
            )

            self._solve_component(
                ordered_courses,
                available_dates,
                conflict_graph,
                {},
                solutions
            )

            component_solutions.append(solutions)

        self.all_valid_schedules = self._combine_component_solutions(component_solutions)

        duration = time.perf_counter() - start_time

        print("\n" + "=" * 40)
        print(" PERFORMANCE REPORT")
        print(f" - Execution Time: {duration:.4f} seconds")
        print(f" - Courses Scheduled: {len(courses)}")
        print(f" - Available Dates: {len(available_dates)}")
        print(f" - Components Found: {len(components)}")
        print(f" - Solutions Found: {len(self.all_valid_schedules)}")
        print(f" - Status: {'PASSED' if duration < 30 else 'FAILED'}")
        print("=" * 40 + "\n")

        return self.all_valid_schedules

    def _get_available_dates(self, period: ExamPeriod) -> List[date]:
        available = []
        current = period.start_date

        while current <= period.end_date:
            if period.is_date_valid(current):
                available.append(current)

            current += timedelta(days=1)

        return available

    def _build_conflict_graph(self, courses: List[Course]) -> Dict[Course, Set[Course]]:
        graph = {course: set() for course in courses}
        dummy_date = date(2099, 1, 1)

        for i in range(len(courses)):
            for j in range(i + 1, len(courses)):
                course1 = courses[i]
                course2 = courses[j]

                if self._pair_conflicts(course1, course2, dummy_date):
                    graph[course1].add(course2)
                    graph[course2].add(course1)

        return graph

    def _pair_conflicts(self, course1: Course, course2: Course, exam_date: date) -> bool:
        state = {
            course1: exam_date,
            course2: exam_date,
        }

        for rule in self.rules:
            if not rule.is_valid(state):
                return True

        return False

    def _get_connected_components(
        self,
        courses: List[Course],
        graph: Dict[Course, Set[Course]]
    ) -> List[List[Course]]:
        visited = set()
        components = []

        for course in courses:
            if course in visited:
                continue

            stack = [course]
            component = []
            visited.add(course)

            while stack:
                current = stack.pop()
                component.append(current)

                for neighbor in graph[current]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        stack.append(neighbor)

            components.append(component)

        return components

    def _solve_component(
        self,
        courses: List[Course],
        available_dates: List[date],
        conflict_graph: Dict[Course, Set[Course]],
        current_state: Dict[Course, date],
        solutions: List[Dict[Course, date]]
    ) -> None:
        if len(current_state) == len(courses):
            solutions.append(current_state.copy())
            return

        course = self._select_next_course_mrv(
            courses,
            available_dates,
            conflict_graph,
            current_state
        )

        for exam_date in available_dates:
            if self._can_assign(course, exam_date, conflict_graph, current_state):
                current_state[course] = exam_date
                self._solve_component(
                    courses,
                    available_dates,
                    conflict_graph,
                    current_state,
                    solutions
                )
                del current_state[course]

    def _select_next_course_mrv(
        self,
        courses: List[Course],
        available_dates: List[date],
        conflict_graph: Dict[Course, Set[Course]],
        current_state: Dict[Course, date]
    ) -> Course:
        unassigned = [course for course in courses if course not in current_state]

        return min(
            unassigned,
            key=lambda course: (
                self._count_valid_dates(
                    course,
                    available_dates,
                    conflict_graph,
                    current_state
                ),
                -len(conflict_graph[course])
            )
        )

    def _count_valid_dates(
        self,
        course: Course,
        available_dates: List[date],
        conflict_graph: Dict[Course, Set[Course]],
        current_state: Dict[Course, date]
    ) -> int:
        count = 0

        for exam_date in available_dates:
            if self._can_assign(course, exam_date, conflict_graph, current_state):
                count += 1

        return count

    def _can_assign(
        self,
        course: Course,
        exam_date: date,
        conflict_graph: Dict[Course, Set[Course]],
        current_state: Dict[Course, date]
    ) -> bool:
        for conflicting_course in conflict_graph[course]:
            if current_state.get(conflicting_course) == exam_date:
                return False

        return True

    def _combine_component_solutions(
        self,
        component_solutions: List[List[Dict[Course, date]]]
    ) -> List[Dict[Course, date]]:
        if not component_solutions:
            return []

        all_schedules = []

        for combination in product(*component_solutions):
            merged = {}

            for partial_schedule in combination:
                merged.update(partial_schedule)

            all_schedules.append(merged)

        return all_schedules