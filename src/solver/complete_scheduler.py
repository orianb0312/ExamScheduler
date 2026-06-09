import time
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import product
from pathlib import Path
from typing import Dict, Generator, Iterable, Iterator, List, Optional, Sequence, Set

from src.output.output_manager import TextOutputManager
from src.output.schedule_text_formatter import (
    PlainTextScheduleFormatter,
    ScheduleTextFormatter,
)
from src.interfaces import ISchedulingRule
from src.models.academic import Course
from src.models.scheduling import ExamPeriod


DEFAULT_COMPLETE_SYSTEM_BATCH_SIZE = 1000


@dataclass(frozen=True)
class _CourseKey:
    index: int
    course: Course

    def __getattr__(self, name):
        return getattr(self.course, name)


@dataclass(frozen=True)
class PeriodScheduleSet:
    period: ExamPeriod
    courses: List[Course]
    schedules: List[Dict[int, date]]

    @property
    def count(self) -> int:
        return len(self.schedules)


@dataclass(frozen=True)
class CompleteSystemResult:
    output_path: Optional[Path]
    period_course_counts: List[int]
    period_schedule_counts: List[int]
    complete_system_count: int
    written_system_count: int
    elapsed_seconds: float
    truncated: bool
    auto_limit_seconds: Optional[float] = None


@dataclass(frozen=True)
class GeneratedCompleteSystem:
    number: int
    text: str


@dataclass(frozen=True)
class CompleteSystemStream:
    period_course_counts: List[int]
    period_schedule_counts: List[int]
    complete_system_count: int
    systems: Iterator[GeneratedCompleteSystem]

    def iter_batches(
        self,
        batch_size: int = DEFAULT_COMPLETE_SYSTEM_BATCH_SIZE,
    ) -> Iterator[List[GeneratedCompleteSystem]]:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")

        batch: List[GeneratedCompleteSystem] = []
        for system in self.systems:
            batch.append(system)
            if len(batch) >= batch_size:
                yield batch
                batch = []

        if batch:
            yield batch


class CompleteSystemScheduler:
    """
    Generates complete exam systems across multiple exam periods.

    A complete system is the Cartesian product of period-level schedules.
    For example, if FALL Aleph has 1,080,288 valid schedules and FALL Bet has
    4,536 valid schedules, the complete system count is:

        1,080,288 * 4,536 = 4,900,186,368

    This class can count those complete systems exactly and can stream them to
    a file. For very large products, pass max_systems when writing a sample.
    """

    def __init__(
        self,
        rules: List[ISchedulingRule],
        schedule_formatter: ScheduleTextFormatter | None = None,
    ):
        self.rules = rules
        # The scheduler emits systems; the formatter decides how those systems
        # look in text files or stdout.
        self._formatter = schedule_formatter or PlainTextScheduleFormatter()
        self._course_keys: List[_CourseKey] = []
        self._write_batch_size = 2048

    def count_complete_systems(
        self,
        period_course_sets: Sequence[tuple[ExamPeriod, List[Course]]],
    ) -> CompleteSystemResult:
        started_at = time.perf_counter()
        schedule_sets = self._build_period_schedule_sets(period_course_sets)
        complete_count = self._product_count(schedule_sets)

        return CompleteSystemResult(
            output_path=None,
            period_course_counts=[len(schedule_set.courses) for schedule_set in schedule_sets],
            period_schedule_counts=[schedule_set.count for schedule_set in schedule_sets],
            complete_system_count=complete_count,
            written_system_count=0,
            elapsed_seconds=time.perf_counter() - started_at,
            truncated=False,
        )

    def stream_complete_systems(
        self,
        period_course_sets: Sequence[tuple[ExamPeriod, List[Course]]],
        max_systems: Optional[int] = None,
    ) -> CompleteSystemStream:
        schedule_sets = self._build_period_schedule_sets(period_course_sets)
        complete_count = self._product_count(schedule_sets)
        formatted_caches = self._build_formatted_schedule_caches(schedule_sets)

        systems = self._iter_generated_complete_systems(
            schedule_sets,
            formatted_caches,
            max_systems=max_systems,
        )

        return CompleteSystemStream(
            period_course_counts=[len(schedule_set.courses) for schedule_set in schedule_sets],
            period_schedule_counts=[schedule_set.count for schedule_set in schedule_sets],
            complete_system_count=complete_count,
            systems=systems,
        )

    def write_complete_systems(
        self,
        period_course_sets: Sequence[tuple[ExamPeriod, List[Course]]],
        output_manager: TextOutputManager,
        max_systems: Optional[int] = None,
    ) -> CompleteSystemResult:
        started_at = time.perf_counter()
        stream = self.stream_complete_systems(
            period_course_sets,
            max_systems=max_systems,
        )

        output_manager._ensure_dir_exists()
        output_path = output_manager.get_full_path()

        written_count = 0
        with open(output_path, "w", encoding="utf-8") as file:
            # Header text stays in the output layer, even though this method
            # still owns the file-writing flow for backwards compatibility.
            file.write(
                self._formatter.format_complete_header(
                    stream.complete_system_count,
                    stream.period_schedule_counts,
                )
            )

            output_batch = []
            for system in stream.systems:
                written_count = system.number
                output_batch.append(system.text)

                if len(output_batch) >= self._write_batch_size:
                    file.write("".join(output_batch))
                    output_batch.clear()

            if output_batch:
                file.write("".join(output_batch))

            truncated = max_systems is not None and written_count < stream.complete_system_count
            if truncated:
                # The wording is part of the output contract, not the counting logic.
                file.write(
                    self._formatter.format_complete_truncation(
                        written_count,
                        stream.complete_system_count,
                    )
                )

        return CompleteSystemResult(
            output_path=output_path,
            period_course_counts=stream.period_course_counts,
            period_schedule_counts=stream.period_schedule_counts,
            complete_system_count=stream.complete_system_count,
            written_system_count=written_count,
            elapsed_seconds=time.perf_counter() - started_at,
            truncated=truncated,
        )

    def write_complete_systems_auto(
        self,
        period_course_sets: Sequence[tuple[ExamPeriod, List[Course]]],
        output_manager: TextOutputManager,
        time_limit_seconds: float = 30.0,
        safety_margin_seconds: float = 0.25,
    ) -> CompleteSystemResult:
        """
        Writes the largest prefix of complete systems that fits inside the time budget.

        The exact number that can be written depends mostly on disk and formatting speed,
        so the safest way to choose the limit is to stream until the budget is nearly
        exhausted. The full count is still reported in the file header.
        """
        started_at = time.perf_counter()
        stream = self.stream_complete_systems(period_course_sets)

        output_manager._ensure_dir_exists()
        output_path = output_manager.get_full_path()

        deadline = started_at + max(0.0, time_limit_seconds - safety_margin_seconds)
        written_count = 0

        with open(output_path, "w", encoding="utf-8") as file:
            # Auto mode has a richer header, but the solver should not know how
            # that header is phrased.
            file.write(
                self._formatter.format_complete_header(
                    stream.complete_system_count,
                    stream.period_schedule_counts,
                    period_course_counts=stream.period_course_counts,
                    auto_limit_seconds=time_limit_seconds,
                )
            )

            output_batch = []
            systems = iter(stream.systems)
            while True:
                if time.perf_counter() >= deadline:
                    break

                try:
                    system = next(systems)
                except StopIteration:
                    break

                written_count = system.number
                output_batch.append(system.text)

                if len(output_batch) >= self._write_batch_size:
                    file.write("".join(output_batch))
                    output_batch.clear()

            if output_batch:
                file.write("".join(output_batch))

            truncated = written_count < stream.complete_system_count
            if truncated:
                # Keep the user-facing time-limit message in the formatter.
                file.write(
                    self._formatter.format_auto_truncation(
                        written_count,
                        stream.complete_system_count,
                        time_limit_seconds,
                    )
                )

        return CompleteSystemResult(
            output_path=output_path,
            period_course_counts=stream.period_course_counts,
            period_schedule_counts=stream.period_schedule_counts,
            complete_system_count=stream.complete_system_count,
            written_system_count=written_count,
            elapsed_seconds=time.perf_counter() - started_at,
            truncated=truncated,
            auto_limit_seconds=time_limit_seconds,
        )

    def _build_period_schedule_sets(
        self,
        period_course_sets: Sequence[tuple[ExamPeriod, List[Course]]],
    ) -> List[PeriodScheduleSet]:
        return [
            PeriodScheduleSet(
                period=period,
                courses=courses,
                schedules=self._solve_period(courses, period),
            )
            for period, courses in period_course_sets
        ]

    def _solve_period(self, courses: List[Course], period: ExamPeriod) -> List[Dict[int, date]]:
        if not courses:
            return [{}]

        self._course_keys = [_CourseKey(index, course) for index, course in enumerate(courses)]
        available_dates = self._get_available_dates(period)
        if not available_dates:
            return []

        conflict_graph = self._build_conflict_graph(courses)
        components = self._get_connected_components(courses, conflict_graph)

        component_solutions = []
        for component in components:
            solutions = list(self._solve_component(component, available_dates, conflict_graph))
            if not solutions:
                return []
            component_solutions.append(solutions)

        period_schedules = []
        for combination in product(*component_solutions):
            full_assignment = {}
            for partial_assignment in combination:
                full_assignment.update(partial_assignment)
            period_schedules.append(full_assignment)

        return period_schedules

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
            if not rule.is_valid(state):
                return True
        return False

    def _get_connected_components(
        self,
        courses: List[Course],
        graph: Dict[int, Set[int]],
    ) -> List[List[int]]:
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

    def _can_assign(
        self,
        course_index: int,
        exam_date: date,
        conflict_graph: Dict[int, Set[int]],
        current_assignment: Dict[int, date],
    ) -> bool:
        return all(
            current_assignment.get(conflicting_course) != exam_date
            for conflicting_course in conflict_graph[course_index]
        )

    def _iter_complete_systems(
        self,
        schedule_sets: List[PeriodScheduleSet],
    ) -> Iterable[List[tuple[PeriodScheduleSet, Dict[int, date]]]]:
        for combination in product(*(schedule_set.schedules for schedule_set in schedule_sets)):
            yield [
                (schedule_set, period_schedule)
                for schedule_set, period_schedule in zip(schedule_sets, combination)
            ]

    def _build_formatted_schedule_caches(
        self,
        schedule_sets: List[PeriodScheduleSet],
    ) -> List[List[Optional[str]]]:
        return [[None] * schedule_set.count for schedule_set in schedule_sets]

    def _iter_formatted_complete_systems(
        self,
        schedule_sets: List[PeriodScheduleSet],
        formatted_caches: List[List[Optional[str]]],
    ) -> Iterable[List[str]]:
        schedule_index_ranges = [range(schedule_set.count) for schedule_set in schedule_sets]

        for schedule_indexes in product(*schedule_index_ranges):
            yield [
                self._get_formatted_period_schedule(
                    schedule_sets[period_index],
                    formatted_caches[period_index],
                    schedule_index,
                )
                for period_index, schedule_index in enumerate(schedule_indexes)
            ]

    def _iter_generated_complete_systems(
        self,
        schedule_sets: List[PeriodScheduleSet],
        formatted_caches: List[List[Optional[str]]],
        max_systems: Optional[int] = None,
    ) -> Iterator[GeneratedCompleteSystem]:
        if max_systems is not None and max_systems <= 0:
            return

        for system_number, complete_system_blocks in enumerate(
            self._iter_formatted_complete_systems(schedule_sets, formatted_caches),
            start=1,
        ):
            if max_systems is not None and system_number > max_systems:
                break

            yield GeneratedCompleteSystem(
                number=system_number,
                text=self._formatter.format_complete_system(
                    system_number,
                    complete_system_blocks,
                ),
            )

    def _get_formatted_period_schedule(
        self,
        schedule_set: PeriodScheduleSet,
        formatted_cache: List[Optional[str]],
        schedule_index: int,
    ) -> str:
        formatted = formatted_cache[schedule_index]
        if formatted is None:
            # Period schedules repeat across many complete systems, so cache the
            # formatted block once after the solver has found the assignment.
            formatted = self._formatter.format_period_schedule_block(
                schedule_set.period,
                schedule_set.courses,
                schedule_set.schedules[schedule_index],
            )
            formatted_cache[schedule_index] = formatted

        return formatted

    def _product_count(self, schedule_sets: List[PeriodScheduleSet]) -> int:
        total = 1
        for schedule_set in schedule_sets:
            total *= schedule_set.count
        return total

    def _write_complete_system(
        self,
        file,
        system_number: int,
        complete_system: List[tuple[PeriodScheduleSet, Dict[int, date]]],
    ) -> None:
        # Older callers still use this helper, so route it through the same
        # formatter instead of keeping a second copy of the text layout.
        period_blocks = [
            self._formatter.format_period_schedule_block(
                schedule_set.period,
                schedule_set.courses,
                assignment,
            )
            for schedule_set, assignment in complete_system
        ]
        file.write(self._formatter.format_complete_system(system_number, period_blocks))
