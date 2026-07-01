"""Complete-system scheduling, lazy streaming, and memory-bounded storage.

This module extends the period scheduler into full yearly systems by combining
period-level schedules through Cartesian products. Stage 3 UI callers use the
streaming APIs so huge result sets can be paged without freezing the desktop.
"""

import struct
import tempfile
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Dict, Generator, Iterable, Iterator, List, Optional, Protocol, Sequence, Set

from src.output.output_manager import TextOutputManager
from src.interfaces import ISchedulingRule
from src.models.academic import Course
from src.models.scheduling import ExamPeriod
from src.rules.advanced_constraints_rule import AdvancedConstraintsRule
from src.sorting.schedule_priority import (
    SchedulePrioritySorter,
    sortable_exams_from_assignment,
)


DEFAULT_COMPLETE_SYSTEM_BATCH_SIZE = 1000
DEFAULT_ASSIGNMENT_STORE_MEMORY_LIMIT_BYTES = 8 * 1024 * 1024
DEFAULT_FORMAT_CACHE_SIZE = 4096
DEFAULT_OUTPUT_BATCH_CHAR_LIMIT = 16 * 1024 * 1024
DEFAULT_OUTPUT_BUFFER_BYTES = 16 * 1024 * 1024

_Deadline = float | None | Callable[[], float | None]


class ScheduleGenerationTimedOut(TimeoutError):
    """Raised when a time-limited stream reaches its generation deadline."""


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


class ScheduleSource(Protocol):
    """Indexable source for period assignments used by complete-system products."""

    def __len__(self) -> int:
        ...

    def __getitem__(self, index: int) -> Dict[int, date]:
        ...


class CountOnlyScheduleSource:
    """Schedule source used by count mode when assignments do not need storage."""

    def __init__(self, count: int) -> None:
        self._count = count

    def __len__(self) -> int:
        return self._count

    def __getitem__(self, index: int) -> Dict[int, date]:
        raise RuntimeError("Count-only schedule source cannot return assignments.")


class DiskAssignmentStore:
    """Fixed-width, spooled binary storage for component assignments."""

    def __init__(
        self,
        course_indices: Sequence[int],
        date_to_id: Dict[date, int],
        id_to_date: Sequence[date],
        memory_limit_bytes: int = DEFAULT_ASSIGNMENT_STORE_MEMORY_LIMIT_BYTES,
    ) -> None:
        self._count = 0
        self._course_indices = tuple(course_indices)
        self._date_to_id = date_to_id
        self._id_to_date = list(id_to_date)
        self._memory_limit_bytes = memory_limit_bytes
        self._num_courses = len(self._course_indices)
        self._buffer = bytearray()
        self._file = None

        self._record_format = ""
        self._record_size = 0
        self._single_byte_record = False
        if self._num_courses:
            date_id_format = self._date_id_format(len(self._id_to_date))
            self._record_format = f"<{self._num_courses}{date_id_format}"
            self._record_size = struct.calcsize(self._record_format)
            self._single_byte_record = (
                self._num_courses == 1
                and date_id_format == "B"
            )

    @property
    def course_indices(self) -> tuple[int, ...]:
        return self._course_indices

    def append(self, assignment: Dict[int, date]) -> None:
        if not self._num_courses:
            self._count += 1
            return

        date_ids = (
            self._date_to_id[assignment[course_index]]
            for course_index in self._course_indices
        )
        self._append_record(struct.pack(self._record_format, *date_ids))
        self._count += 1

    def __len__(self) -> int:
        return self._count

    def __getitem__(self, index: int) -> Dict[int, date]:
        if index < 0:
            index += self._count
        if index < 0 or index >= self._count:
            raise IndexError("Store index out of range")
        if not self._num_courses:
            return {}

        date_ids = self._read_date_ids(index)
        return {
            course_index: self._id_to_date[date_ids[position]]
            for position, course_index in enumerate(self._course_indices)
        }

    def items_at(self, index: int) -> tuple[tuple[int, date], ...]:
        if index < 0:
            index += self._count
        if index < 0 or index >= self._count:
            raise IndexError("Store index out of range")
        if not self._num_courses:
            return ()
        if self._single_byte_record:
            return ((
                self._course_indices[0],
                self._id_to_date[self._read_single_date_id(index)],
            ),)

        date_ids = self._read_date_ids(index)
        return tuple(
            (course_index, self._id_to_date[date_ids[position]])
            for position, course_index in enumerate(self._course_indices)
        )

    def append_items_at(self, index: int, target: List[tuple[int, date]]) -> None:
        if index < 0:
            index += self._count
        if index < 0 or index >= self._count:
            raise IndexError("Store index out of range")
        if not self._num_courses:
            return
        if self._single_byte_record:
            target.append(
                (
                    self._course_indices[0],
                    self._id_to_date[self._read_single_date_id(index)],
                )
            )
            return

        date_ids = self._read_date_ids(index)
        for position, course_index in enumerate(self._course_indices):
            target.append((course_index, self._id_to_date[date_ids[position]]))

    def __iter__(self) -> Iterator[Dict[int, date]]:
        if not self._num_courses:
            for _ in range(self._count):
                yield {}
            return

        for _ in range(self._count):
            date_ids = self._read_date_ids(_)
            yield {
                course_index: self._id_to_date[date_ids[position]]
                for position, course_index in enumerate(self._course_indices)
            }

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
        self._buffer.clear()

    def _append_record(self, record: bytes) -> None:
        if (
            self._file is None
            and len(self._buffer) + len(record) <= self._memory_limit_bytes
        ):
            self._buffer.extend(record)
            return

        if self._file is None:
            self._file = tempfile.TemporaryFile(mode="w+b")
            self._file.write(self._buffer)
            self._buffer.clear()

        self._file.seek(0, 2)
        self._file.write(record)

    def _read_date_ids(self, index: int) -> tuple[int, ...]:
        start = index * self._record_size
        if self._file is None:
            return struct.unpack_from(self._record_format, self._buffer, start)

        self._file.seek(start)
        raw_bytes = self._file.read(self._record_size)
        if len(raw_bytes) != self._record_size:
            raise IndexError("Store index could not be read")
        return struct.unpack(self._record_format, raw_bytes)

    def _read_single_date_id(self, index: int) -> int:
        if self._file is None:
            return self._buffer[index]

        self._file.seek(index)
        raw_byte = self._file.read(1)
        if len(raw_byte) != 1:
            raise IndexError("Store index could not be read")
        return raw_byte[0]

    @staticmethod
    def _date_id_format(date_count: int) -> str:
        max_id = max(0, date_count - 1)
        if max_id <= 0xFF:
            return "B"
        if max_id <= 0xFFFF:
            return "H"
        if max_id <= 0xFFFFFFFF:
            return "I"
        return "Q"


class ComponentBackedScheduleSource:
    """Period schedule source backed by component stores and index products."""

    def __init__(self, component_stores: Sequence[DiskAssignmentStore]) -> None:
        self._component_stores = list(component_stores)
        self._component_counts = [
            len(component_store) for component_store in self._component_stores
        ]
        self._count = _product_counts(self._component_counts)

    def __len__(self) -> int:
        return self._count

    def __getitem__(self, index: int) -> Dict[int, date]:
        if index < 0:
            index += self._count
        if index < 0 or index >= self._count:
            raise IndexError("Schedule index out of range")
        if not self._component_stores:
            return {}

        component_indexes = _flat_index_to_product_indexes(
            index,
            self._component_counts,
        )
        return self._merge_component_assignments(component_indexes)

    def items_at(self, index: int) -> List[tuple[int, date]]:
        if index < 0:
            index += self._count
        if index < 0 or index >= self._count:
            raise IndexError("Schedule index out of range")
        if not self._component_stores:
            return []

        component_indexes = _flat_index_to_product_indexes(
            index,
            self._component_counts,
        )
        items: List[tuple[int, date]] = []
        for component_store, component_index in zip(
            self._component_stores,
            component_indexes,
        ):
            component_store.append_items_at(component_index, items)
        return items

    def __iter__(self) -> Iterator[Dict[int, date]]:
        for component_indexes in _iter_index_product_counts(self._component_counts):
            yield self._merge_component_assignments(component_indexes)

    def close(self) -> None:
        for component_store in self._component_stores:
            component_store.close()

    def _merge_component_assignments(
        self,
        component_indexes: Sequence[int],
    ) -> Dict[int, date]:
        full_assignment: Dict[int, date] = {}
        for component_store, component_index in zip(
            self._component_stores,
            component_indexes,
        ):
            full_assignment.update(component_store[component_index])
        return full_assignment


class BoundedFormatCache:
    """Small LRU cache for formatted period schedule blocks."""

    def __init__(self, max_items: int = DEFAULT_FORMAT_CACHE_SIZE) -> None:
        self._max_items = max(0, max_items)
        self._items: OrderedDict[int, str] = OrderedDict()

    def get(self, index: int) -> Optional[str]:
        try:
            value = self._items.pop(index)
        except KeyError:
            return None
        self._items[index] = value
        return value

    def set(self, index: int, value: str) -> None:
        if self._max_items == 0:
            return
        self._items[index] = value
        self._items.move_to_end(index)
        if len(self._items) > self._max_items:
            self._items.popitem(last=False)


def _product_counts(counts: Iterable[int]) -> int:
    total = 1
    for count in counts:
        total *= count
    return total


def _flat_index_to_product_indexes(index: int, counts: Sequence[int]) -> List[int]:
    indexes = [0] * len(counts)
    for position in range(len(counts) - 1, -1, -1):
        count = counts[position]
        indexes[position] = index % count
        index //= count
    return indexes


def _iter_index_product_counts(counts: Sequence[int]) -> Iterator[List[int]]:
    if not counts:
        yield []
        return
    if any(count == 0 for count in counts):
        return

    indexes = [0] * len(counts)
    while True:
        yield list(indexes)

        for position in range(len(indexes) - 1, -1, -1):
            indexes[position] += 1
            if indexes[position] < counts[position]:
                break
            indexes[position] = 0
        else:
            return


@dataclass(frozen=True)
class PeriodScheduleSet:
    """One exam period plus its generated schedules and cached formatting parts."""

    period: ExamPeriod
    courses: List[Course]
    schedules: ScheduleSource
    header: str = field(init=False)
    course_sort_keys: tuple[str, ...] = field(init=False)
    course_line_prefixes: tuple[str, ...] = field(init=False)
    course_line_suffixes: tuple[str, ...] = field(init=False)
    course_line_caches: tuple[dict[date, str], ...] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "header",
            (
                f"=== SEMESTER: {self.period.semester.value} ===\n"
                f"  [TERM: {self.period.term.value}]\n"
                "  " + "-" * 40 + "\n"
            ),
        )
        object.__setattr__(
            self,
            "course_sort_keys",
            tuple(course.name.lower() for course in self.courses),
        )
        object.__setattr__(
            self,
            "course_line_prefixes",
            tuple(f"  {course.name} | " for course in self.courses),
        )
        object.__setattr__(
            self,
            "course_line_suffixes",
            tuple(f" | {course.instructor}\n" for course in self.courses),
        )
        object.__setattr__(
            self,
            "course_line_caches",
            tuple({} for _course in self.courses),
        )

    @property
    def count(self) -> int:
        return len(self.schedules)


@dataclass(frozen=True)
class CompleteSystemResult:
    """Summary returned by count, write, and auto-write complete-system modes."""

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
    """One formatted complete-system item emitted by a lazy stream."""

    number: int
    text: str


@dataclass(frozen=True)
class CompleteSystemStream:
    """Owns the generated-system iterator and closes backing stores on exit."""

    period_course_counts: List[int]
    period_schedule_counts: List[int]
    complete_system_count: int
    systems: Iterator[GeneratedCompleteSystem]
    _schedule_sets: Sequence[PeriodScheduleSet] = ()

    def iter_batches(
        self,
        batch_size: int = DEFAULT_COMPLETE_SYSTEM_BATCH_SIZE,
    ) -> Iterator[List[GeneratedCompleteSystem]]:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")

        batch: List[GeneratedCompleteSystem] = []
        try:
            for system in self.systems:
                batch.append(system)
                if len(batch) >= batch_size:
                    yield batch
                    batch = []

            if batch:
                yield batch
        finally:
            self.close()

    def close(self) -> None:
        close_systems = getattr(self.systems, "close", None)
        if close_systems is not None:
            close_systems()

        for schedule_set in self._schedule_sets:
            close_schedules = getattr(schedule_set.schedules, "close", None)
            if close_schedules is not None:
                close_schedules()


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

    def __init__(self, rules: List[ISchedulingRule]):
        self.rules = rules
        self._course_keys: List[_CourseKey] = []
        self._write_batch_size = 8192
        self._format_cache_size = DEFAULT_FORMAT_CACHE_SIZE
        self._output_batch_char_limit = DEFAULT_OUTPUT_BATCH_CHAR_LIMIT
        self._output_buffer_bytes = DEFAULT_OUTPUT_BUFFER_BYTES

    def count_complete_systems(
        self,
        period_course_sets: Sequence[tuple[ExamPeriod, List[Course]]],
    ) -> CompleteSystemResult:
        """Count the Cartesian product without materializing all schedules."""
        started_at = time.perf_counter()
        schedule_sets = self._build_period_schedule_sets(
            period_course_sets,
            materialize_schedules=False,
        )
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
        sort_priority: Sequence[str] = (),
    ) -> CompleteSystemStream:
        """Return a lazy stream used by the CLI and PyQt paging protocol."""
        schedule_sets = self._build_period_schedule_sets(period_course_sets)
        complete_count = self._product_count(schedule_sets)
        formatted_caches = self._build_formatted_schedule_caches(schedule_sets)

        systems = self._iter_generated_complete_systems(
            schedule_sets,
            formatted_caches,
            max_systems=max_systems,
            sort_priority=sort_priority,
        )

        return CompleteSystemStream(
            period_course_counts=[len(schedule_set.courses) for schedule_set in schedule_sets],
            period_schedule_counts=[schedule_set.count for schedule_set in schedule_sets],
            complete_system_count=complete_count,
            systems=systems,
            _schedule_sets=schedule_sets,
        )

    def stream_complete_systems_on_demand(
        self,
        period_course_sets: Sequence[tuple[ExamPeriod, List[Course]]],
        max_systems: Optional[int] = None,
        deadline: _Deadline = None,
    ) -> CompleteSystemStream:
        """
        Return a first-ready stream without materializing every period schedule.

        Time-limited desktop auto runs use this path so the first UI batch can
        be emitted as soon as enough valid systems are found. Exact totals are
        calculated by the workflow separately, after the first batch has been
        released to the UI.
        """
        schedule_sets = [
            PeriodScheduleSet(period=period, courses=courses, schedules=[])
            for period, courses in period_course_sets
        ]
        systems = self._iter_generated_complete_systems_on_demand(
            schedule_sets,
            max_systems=max_systems,
            deadline=deadline,
        )
        return CompleteSystemStream(
            period_course_counts=[
                len(schedule_set.courses) for schedule_set in schedule_sets
            ],
            period_schedule_counts=[0 for _schedule_set in schedule_sets],
            complete_system_count=0,
            systems=systems,
            _schedule_sets=(),
        )

    def write_complete_systems(
        self,
        period_course_sets: Sequence[tuple[ExamPeriod, List[Course]]],
        output_manager: TextOutputManager,
        max_systems: Optional[int] = None,
        sort_priority: Sequence[str] = (),
    ) -> CompleteSystemResult:
        started_at = time.perf_counter()
        stream = self.stream_complete_systems(
            period_course_sets,
            max_systems=max_systems,
            sort_priority=sort_priority,
        )

        output_manager._ensure_dir_exists()
        output_path = output_manager.get_full_path()

        written_count = 0
        try:
            with open(
                output_path,
                "w",
                encoding="utf-8",
                buffering=self._output_buffer_bytes,
            ) as file:
                file.write("OFFICIAL UNIVERSITY COMPLETE EXAM SYSTEMS\n")
                file.write("=" * 65 + "\n")
                file.write(f"Total complete systems: {stream.complete_system_count:,}\n")
                file.write(
                    "Period schedule counts: "
                    + ", ".join(f"{count:,}" for count in stream.period_schedule_counts)
                    + "\n\n"
                )

                output_batch = []
                output_batch_chars = 0
                for system in stream.systems:
                    written_count = system.number
                    output_batch.append(system.text)
                    output_batch_chars += len(system.text)

                    if (
                        len(output_batch) >= self._write_batch_size
                        or output_batch_chars >= self._output_batch_char_limit
                    ):
                        file.write("".join(output_batch))
                        output_batch.clear()
                        output_batch_chars = 0

                if output_batch:
                    file.write("".join(output_batch))

                truncated = max_systems is not None and written_count < stream.complete_system_count
                if truncated:
                    file.write(
                        f"\n... Stopped after writing {written_count:,} of "
                        f"{stream.complete_system_count:,} complete systems ...\n"
                    )
        finally:
            stream.close()

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
        sort_priority: Sequence[str] = (),
    ) -> CompleteSystemResult:
        """
        Writes the largest prefix of complete systems that fits inside the time budget.

        The exact number that can be written depends mostly on disk and formatting speed,
        so the safest way to choose the limit is to stream until the budget is nearly
        exhausted. The full count is still reported in the file header.
        """
        started_at = time.perf_counter()
        stream = self.stream_complete_systems(
            period_course_sets,
            sort_priority=sort_priority,
        )

        output_manager._ensure_dir_exists()
        output_path = output_manager.get_full_path()

        deadline = started_at + max(0.0, time_limit_seconds - safety_margin_seconds)
        written_count = 0

        try:
            with open(
                output_path,
                "w",
                encoding="utf-8",
                buffering=self._output_buffer_bytes,
            ) as file:
                file.write("OFFICIAL UNIVERSITY COMPLETE EXAM SYSTEMS\n")
                file.write("=" * 65 + "\n")
                file.write(f"Total complete systems: {stream.complete_system_count:,}\n")
                file.write(
                    "Period course counts: "
                    + ", ".join(f"{count:,}" for count in stream.period_course_counts)
                    + "\n"
                )
                file.write(
                    "Period schedule counts: "
                    + ", ".join(f"{count:,}" for count in stream.period_schedule_counts)
                    + "\n"
                )
                file.write(f"Auto time limit: {time_limit_seconds:.2f} seconds\n\n")

                output_batch = []
                output_batch_chars = 0
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
                    output_batch_chars += len(system.text)

                    if (
                        len(output_batch) >= self._write_batch_size
                        or output_batch_chars >= self._output_batch_char_limit
                    ):
                        file.write("".join(output_batch))
                        output_batch.clear()
                        output_batch_chars = 0

                if output_batch:
                    file.write("".join(output_batch))

                truncated = written_count < stream.complete_system_count
                if truncated:
                    file.write(
                        f"\n... Auto limit wrote {written_count:,} of "
                        f"{stream.complete_system_count:,} complete systems within "
                        f"{time_limit_seconds:.2f} seconds ...\n"
                    )
        finally:
            stream.close()

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
        materialize_schedules: bool = True,
    ) -> List[PeriodScheduleSet]:
        return [
            PeriodScheduleSet(
                period=period,
                courses=courses,
                schedules=self._solve_period(
                    courses,
                    period,
                    materialize_schedules=materialize_schedules,
                ),
            )
            for period, courses in period_course_sets
        ]

    def _solve_period(
        self,
        courses: List[Course],
        period: ExamPeriod,
        materialize_schedules: bool = True,
    ) -> ScheduleSource:
        if not courses:
            if materialize_schedules:
                return [{}]
            return CountOnlyScheduleSource(1)

        self._course_keys = [_CourseKey(index, course) for index, course in enumerate(courses)]
        available_dates = self._get_available_dates(period)
        if not available_dates:
            if materialize_schedules:
                return []
            return CountOnlyScheduleSource(0)

        conflict_graph = self._build_conflict_graph(courses)
        components = self._get_connected_components(courses, conflict_graph)

        if not materialize_schedules:
            return CountOnlyScheduleSource(
                self._count_period_schedules(
                    components,
                    available_dates,
                    conflict_graph,
                )
            )

        date_to_id = {exam_date: index for index, exam_date in enumerate(available_dates)}
        component_stores: List[DiskAssignmentStore] = []

        for component in components:
            component_store = DiskAssignmentStore(
                component,
                date_to_id,
                available_dates,
            )

            try:
                for solution in self._solve_component(
                    component,
                    available_dates,
                    conflict_graph,
                ):
                    component_store.append(solution)

                if len(component_store) == 0:
                    component_store.close()
                    self._close_schedule_sources(component_stores)
                    return []

                component_stores.append(component_store)
            except Exception:
                component_store.close()
                self._close_schedule_sources(component_stores)
                raise

        return ComponentBackedScheduleSource(component_stores)

    def _count_period_schedules(
        self,
        components: Sequence[List[int]],
        available_dates: List[date],
        conflict_graph: Dict[int, Set[int]],
    ) -> int:
        total = 1
        for component in components:
            component_count = sum(
                1
                for _solution in self._solve_component(
                    component,
                    available_dates,
                    conflict_graph,
                )
            )
            if component_count == 0:
                return 0
            total *= component_count
        return total

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

    def _iter_complete_systems(
        self,
        schedule_sets: List[PeriodScheduleSet],
    ) -> Iterable[List[tuple[PeriodScheduleSet, Dict[int, date]]]]:
        schedule_counts = [schedule_set.count for schedule_set in schedule_sets]

        for schedule_indexes in _iter_index_product_counts(schedule_counts):
            yield [
                (schedule_set, schedule_set.schedules[schedule_index])
                for schedule_set, schedule_index in zip(schedule_sets, schedule_indexes)
            ]

    def _build_formatted_schedule_caches(
        self,
        schedule_sets: List[PeriodScheduleSet],
    ) -> List[BoundedFormatCache]:
        last_schedule_index = len(schedule_sets) - 1
        return [
            BoundedFormatCache(
                0
                if (
                    index == last_schedule_index
                    and schedule_set.count > self._format_cache_size
                )
                else min(self._format_cache_size, schedule_set.count)
            )
            for index, schedule_set in enumerate(schedule_sets)
        ]

    def _iter_formatted_complete_systems(
        self,
        schedule_sets: List[PeriodScheduleSet],
        formatted_caches: List[BoundedFormatCache],
    ) -> Iterable[List[str]]:
        schedule_counts = [schedule_set.count for schedule_set in schedule_sets]

        for schedule_indexes in _iter_index_product_counts(schedule_counts):
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
        formatted_caches: List[BoundedFormatCache],
        max_systems: Optional[int] = None,
        sort_priority: Sequence[str] = (),
    ) -> Iterator[GeneratedCompleteSystem]:
        try:
            if max_systems is not None and max_systems <= 0:
                return

            for system_number, schedule_indexes in self._iter_ordered_complete_system_indexes(
                schedule_sets,
                sort_priority,
            ):
                complete_system_blocks = [
                    self._get_formatted_period_schedule(
                        schedule_sets[period_index],
                        formatted_caches[period_index],
                        schedule_index,
                    )
                    for period_index, schedule_index in enumerate(schedule_indexes)
                ]
                yield GeneratedCompleteSystem(
                    number=system_number,
                    text=self._format_complete_system(system_number, complete_system_blocks),
                )

                if max_systems is not None and system_number >= max_systems:
                    break
        finally:
            self._close_schedule_sets(schedule_sets)

    def _iter_generated_complete_systems_on_demand(
        self,
        schedule_sets: Sequence[PeriodScheduleSet],
        max_systems: Optional[int] = None,
        deadline: _Deadline = None,
    ) -> Iterator[GeneratedCompleteSystem]:
        if max_systems is not None and max_systems <= 0:
            return

        period_blocks: List[str] = []
        system_number = 0

        def recurse(period_index: int) -> Iterator[GeneratedCompleteSystem]:
            nonlocal system_number
            self._raise_if_deadline_expired(deadline)

            if period_index >= len(schedule_sets):
                system_number += 1
                yield GeneratedCompleteSystem(
                    number=system_number,
                    text=self._format_complete_system(system_number, period_blocks),
                )
                return

            schedule_set = schedule_sets[period_index]
            for assignment in self._iter_period_assignments_on_demand(
                schedule_set,
                deadline=deadline,
            ):
                period_blocks.append(
                    self._format_period_schedule(schedule_set, assignment)
                )
                yield from recurse(period_index + 1)
                period_blocks.pop()

                if max_systems is not None and system_number >= max_systems:
                    return

        yield from recurse(0)

    def _iter_period_assignments_on_demand(
        self,
        schedule_set: PeriodScheduleSet,
        deadline: _Deadline = None,
    ) -> Iterator[Dict[int, date]]:
        courses = schedule_set.courses
        if not courses:
            self._raise_if_deadline_expired(deadline)
            yield {}
            return

        course_keys = [
            _CourseKey(index, course) for index, course in enumerate(courses)
        ]
        available_dates = self._get_available_dates(schedule_set.period)
        if not available_dates:
            return

        conflict_graph = self._build_conflict_graph_for_keys(courses, course_keys)
        components = self._get_connected_components(courses, conflict_graph)
        yield from self._iter_component_products_on_demand(
            components,
            available_dates,
            conflict_graph,
            course_keys,
            deadline,
        )

    def _iter_component_products_on_demand(
        self,
        components: Sequence[List[int]],
        available_dates: List[date],
        conflict_graph: Dict[int, Set[int]],
        course_keys: Sequence[_CourseKey],
        deadline: _Deadline,
    ) -> Iterator[Dict[int, date]]:
        assignment: Dict[int, date] = {}

        def recurse(component_index: int) -> Iterator[Dict[int, date]]:
            self._raise_if_deadline_expired(deadline)
            if component_index >= len(components):
                yield assignment.copy()
                return

            component = components[component_index]
            for solution in self._solve_component_on_demand(
                component,
                available_dates,
                conflict_graph,
                course_keys,
                deadline,
            ):
                assignment.update(solution)
                yield from recurse(component_index + 1)
                for course_index in solution:
                    assignment.pop(course_index, None)

        yield from recurse(0)

    def _solve_component_on_demand(
        self,
        component: List[int],
        available_dates: List[date],
        conflict_graph: Dict[int, Set[int]],
        course_keys: Sequence[_CourseKey],
        deadline: _Deadline,
    ) -> Iterator[Dict[int, date]]:
        current_assignment: Dict[int, date] = {}

        def backtrack() -> Iterator[Dict[int, date]]:
            self._raise_if_deadline_expired(deadline)
            if len(current_assignment) == len(component):
                yield current_assignment.copy()
                return

            course_index = self._select_next_course_mrv_on_demand(
                component,
                available_dates,
                conflict_graph,
                current_assignment,
                course_keys,
                deadline,
            )

            for exam_date in available_dates:
                self._raise_if_deadline_expired(deadline)
                if self._can_assign_on_demand(
                    course_index,
                    exam_date,
                    conflict_graph,
                    current_assignment,
                    course_keys,
                ):
                    current_assignment[course_index] = exam_date
                    yield from backtrack()
                    del current_assignment[course_index]

        yield from backtrack()

    def _select_next_course_mrv_on_demand(
        self,
        component: List[int],
        available_dates: List[date],
        conflict_graph: Dict[int, Set[int]],
        current_assignment: Dict[int, date],
        course_keys: Sequence[_CourseKey],
        deadline: _Deadline,
    ) -> int:
        unassigned = [
            course_index
            for course_index in component
            if course_index not in current_assignment
        ]
        return min(
            unassigned,
            key=lambda course_index: (
                self._count_valid_dates_on_demand(
                    course_index,
                    available_dates,
                    conflict_graph,
                    current_assignment,
                    course_keys,
                    deadline,
                ),
                -len(conflict_graph[course_index]),
            ),
        )

    def _count_valid_dates_on_demand(
        self,
        course_index: int,
        available_dates: List[date],
        conflict_graph: Dict[int, Set[int]],
        current_assignment: Dict[int, date],
        course_keys: Sequence[_CourseKey],
        deadline: _Deadline,
    ) -> int:
        count = 0
        for exam_date in available_dates:
            self._raise_if_deadline_expired(deadline)
            if self._can_assign_on_demand(
                course_index,
                exam_date,
                conflict_graph,
                current_assignment,
                course_keys,
            ):
                count += 1
        return count

    def _can_assign_on_demand(
        self,
        course_index: int,
        exam_date: date,
        conflict_graph: Dict[int, Set[int]],
        current_assignment: Dict[int, date],
        course_keys: Sequence[_CourseKey],
    ) -> bool:
        if any(
            current_assignment.get(conflicting_course) == exam_date
            for conflicting_course in conflict_graph[course_index]
        ):
            return False

        attempt = current_assignment.copy()
        attempt[course_index] = exam_date
        return self._rules_accept_assignment_for_keys(
            attempt,
            course_keys,
            is_complete=len(attempt) == len(course_keys),
        )

    def _build_conflict_graph_for_keys(
        self,
        courses: List[Course],
        course_keys: Sequence[_CourseKey],
    ) -> Dict[int, Set[int]]:
        graph = {index: set() for index in range(len(courses))}
        dummy_date = date(2099, 1, 1)

        for left in range(len(courses)):
            for right in range(left + 1, len(courses)):
                state = {
                    course_keys[left]: dummy_date,
                    course_keys[right]: dummy_date,
                }
                if any(
                    not getattr(rule, "is_partial_valid", rule.is_valid)(state)
                    for rule in self.rules
                ):
                    graph[left].add(right)
                    graph[right].add(left)

        return graph

    def _rules_accept_assignment_for_keys(
        self,
        assignment: Dict[int, date],
        course_keys: Sequence[_CourseKey],
        is_complete: bool = True,
    ) -> bool:
        state = {
            course_keys[course_index]: exam_date
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

    @staticmethod
    def _raise_if_deadline_expired(deadline: _Deadline) -> None:
        deadline_value = deadline() if callable(deadline) else deadline
        if deadline_value is not None and time.perf_counter() >= deadline_value:
            raise ScheduleGenerationTimedOut

    def _iter_ordered_complete_system_indexes(
        self,
        schedule_sets: List[PeriodScheduleSet],
        sort_priority: Sequence[str],
    ) -> Iterator[tuple[int, tuple[int, ...]]]:
        schedule_counts = [schedule_set.count for schedule_set in schedule_sets]
        index_sets = (
            tuple(schedule_indexes)
            for schedule_indexes in _iter_index_product_counts(schedule_counts)
        )

        if not sort_priority:
            for system_number, schedule_indexes in enumerate(index_sets, start=1):
                yield system_number, schedule_indexes
            return

        sorted_index_sets = SchedulePrioritySorter().sort(
            index_sets,
            sort_priority,
            lambda schedule_indexes: self._sortable_exams_for_complete_indexes(
                schedule_sets,
                schedule_indexes,
            ),
        )
        for system_number, schedule_indexes in enumerate(sorted_index_sets, start=1):
            yield system_number, schedule_indexes

    def _sortable_exams_for_complete_indexes(
        self,
        schedule_sets: Sequence[PeriodScheduleSet],
        schedule_indexes: Sequence[int],
    ):
        exams = []
        for schedule_set, schedule_index in zip(schedule_sets, schedule_indexes):
            exams.extend(
                sortable_exams_from_assignment(
                    schedule_set.courses,
                    self._schedule_items_at(schedule_set, schedule_index),
                )
            )
        return tuple(exams)

    def _schedule_items_at(
        self,
        schedule_set: PeriodScheduleSet,
        schedule_index: int,
    ) -> Iterable[tuple[int, date]]:
        items_at = getattr(schedule_set.schedules, "items_at", None)
        if items_at is not None:
            return items_at(schedule_index)
        return schedule_set.schedules[schedule_index].items()

    def _get_formatted_period_schedule(
        self,
        schedule_set: PeriodScheduleSet,
        formatted_cache: BoundedFormatCache,
        schedule_index: int,
    ) -> str:
        formatted = formatted_cache.get(schedule_index)
        if formatted is None:
            items_at = getattr(schedule_set.schedules, "items_at", None)
            if items_at is None:
                formatted = self._format_period_schedule(
                    schedule_set,
                    schedule_set.schedules[schedule_index],
                )
            else:
                formatted = self._format_period_schedule_items(
                    schedule_set,
                    items_at(schedule_index),
                )
            formatted_cache.set(schedule_index, formatted)

        return formatted

    def _product_count(self, schedule_sets: List[PeriodScheduleSet]) -> int:
        total = 1
        for schedule_set in schedule_sets:
            total *= schedule_set.count
        return total

    def _close_schedule_sets(self, schedule_sets: Sequence[PeriodScheduleSet]) -> None:
        self._close_schedule_sources(
            schedule_set.schedules for schedule_set in schedule_sets
        )

    def _close_schedule_sources(self, schedule_sources: Iterable[object]) -> None:
        for schedule_source in schedule_sources:
            close = getattr(schedule_source, "close", None)
            if close is not None:
                close()

    def _format_complete_system(
        self,
        system_number: int,
        period_blocks: Sequence[str],
    ) -> str:
        return (
            f"Complete System #{system_number}\n"
            + "".join(period_blocks)
            + "\n"
            + "*" * 70
            + "\n\n"
        )

    def _format_period_schedule(
        self,
        schedule_set: PeriodScheduleSet,
        assignment: Dict[int, date],
    ) -> str:
        return self._format_period_schedule_items(schedule_set, assignment.items())

    def _format_period_schedule_items(
        self,
        schedule_set: PeriodScheduleSet,
        assignment_items: Iterable[tuple[int, date]],
    ) -> str:
        items = list(assignment_items)
        lines = [schedule_set.header]

        if not items:
            lines.append("  EMPTY PERIOD: No exams scheduled for this period.\n")
            return "".join(lines)

        sorted_items = sorted(
            items,
            key=lambda item: (item[1], schedule_set.course_sort_keys[item[0]]),
        )

        for course_index, exam_date in sorted_items:
            line_cache = schedule_set.course_line_caches[course_index]
            line = line_cache.get(exam_date)
            if line is None:
                line = (
                    f"{schedule_set.course_line_prefixes[course_index]}"
                    f"{exam_date}"
                    f"{schedule_set.course_line_suffixes[course_index]}"
                )
                line_cache[exam_date] = line
            lines.append(line)

        return "".join(lines)

    def _write_complete_system(
        self,
        file,
        system_number: int,
        complete_system: List[tuple[PeriodScheduleSet, Dict[int, date]]],
    ) -> None:
        file.write(f"Complete System #{system_number}\n")

        for schedule_set, assignment in complete_system:
            file.write(f"=== SEMESTER: {schedule_set.period.semester.value} ===\n")
            file.write(f"  [TERM: {schedule_set.period.term.value}]\n")
            file.write("  " + "-" * 40 + "\n")

            if not assignment:
                file.write("  EMPTY PERIOD: No exams scheduled for this period.\n")
                continue

            sorted_items = sorted(
                assignment.items(),
                key=lambda item: (item[1], schedule_set.courses[item[0]].name.lower()),
            )

            for course_index, exam_date in sorted_items:
                course = schedule_set.courses[course_index]
                file.write(f"  {course.name} | {exam_date} | {course.instructor}\n")

        file.write("\n" + "*" * 70 + "\n\n")
