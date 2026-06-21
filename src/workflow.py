import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Any, Dict, TextIO

from src.output.output_manager import TextOutputManager
from src.models.academic import Course
from src.models.scheduling import ExamPeriod
from src.parser.IParser import IParser
from src.parser.file_parser import FileParser
from src.parser.course_factory import CourseFactory
from src.parser.period_factory import PeriodFactory
from src.process_protocol import BATCH_END_MARKER, LAZY_NEXT_COMMAND, LAZY_STOP_COMMAND
from src.rules.academic_conflict_rule import AcademicConflictRule
from src.solver.complete_scheduler import (
    DEFAULT_COMPLETE_SYSTEM_BATCH_SIZE,
    CompleteSystemResult,
    CompleteSystemScheduler,
)
from src.solver.period_scheduler import Scheduler


@dataclass(frozen=True)
class PeriodRunResult:
    semester: str
    term: str
    course_count: int
    schedule_count: int


@dataclass(frozen=True)
class SchedulerRunResult:
    output_path: Path
    periods: List[PeriodRunResult]

    @property
    def total_schedules(self) -> int:
        return sum(period.schedule_count for period in self.periods)


def load_domain_data(
    source_config: Dict[str, Any],
    parser: IParser | None = None,
) -> Tuple[List[Course], List[ExamPeriod], List[int]]:
    """
    Load and parse all domain data using the given IParser implementation.

    Parameters
    ----------
    source_config : Dict[str, Any]
        The configuration dictionary for the parser (can contain file paths, DB creds, API URLs, etc.).
    parser : IParser | None
        The parser to use. Defaults to FileParser() if not provided.
    """
    if parser is None:
        parser = FileParser()

    # The parser receives its matching configuration block directly
    json_data = parser.parse_to_json(source_config)

    courses = CourseFactory().build_all(json_data, "courses_node")
    periods = PeriodFactory().build_all(json_data, "periods_node")

    # Safe extraction of the user_node configuration
    parsed_json = json.loads(json_data)
    selected_programs = [int(program) for program in parsed_json.get("user_node", [])]

    return courses, periods, selected_programs


def filter_courses_for_period(
        courses: List[Course],
        selected_programs: List[int],
        period: ExamPeriod,
) -> List[Course]:
    relevant_courses = []

    for course in courses:
        if not course.evaluation.requires_scheduling():
            continue

        for affiliation in course.affiliations:
            if (
                    affiliation.program_id in selected_programs
                    and affiliation.semester == period.semester
            ):
                relevant_courses.append(course)
                break

    return relevant_courses


def build_period_course_sets(
        courses: List[Course],
        periods: List[ExamPeriod],
        selected_programs: List[int],
        period_indexes: Optional[Sequence[int]] = None,
) -> List[Tuple[ExamPeriod, List[Course]]]:
    if period_indexes is None:
        selected_periods = periods
    else:
        selected_periods = [periods[index] for index in period_indexes]

    return [
        (period, filter_courses_for_period(courses, selected_programs, period))
        for period in selected_periods
    ]


def _resolve_source_config(output_config: Path, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Helper function to parse output_config and extract the relevant source block.
    Supports overrides passed dynamically from main (e.g., explicit file paths).
    """
    with open(output_config, encoding="utf-8") as fh:
        config_data = json.load(fh)

    source_type = config_data.get("source_type", "file")

    if source_type == "file":
        file_config = config_data.get("file", {})
        # Constraints may come from config.json or from the explicit CLI flag.
        constraints_file = kwargs.get("constraints_file") or file_config.get("constraints_file")
        # Use CLI argument values if provided; otherwise, fall back to the JSON config values
        source_config = {
            "course_file": str(kwargs.get("course_file") or file_config.get("course_file")),
            "dates_file":  str(kwargs.get("dates_file") or file_config.get("dates_file")),
            "user_file":   str(kwargs.get("user_file") or file_config.get("user_file")),
        }
        if constraints_file:
            # Do not invent defaults here; parsing decides whether the file is valid.
            source_config["constraints_file"] = str(constraints_file)
        return source_config

    # For other data source types (e.g., DB, API), return the corresponding configuration block directly
    return config_data.get(source_type, {})



def run_v1_workflow(
        output_config: Path,
        period_indexes: Optional[Sequence[int]] = None,
        parser: IParser | None = None,
        **kwargs: Any,
) -> SchedulerRunResult:
    source_config = _resolve_source_config(output_config, kwargs)
    courses, periods, selected_programs = load_domain_data(source_config, parser=parser)

    if period_indexes is None:
        selected_periods = periods
    else:
        selected_periods = [periods[index] for index in period_indexes]

    output_manager = TextOutputManager(str(output_config))
    scheduler = Scheduler(rules=[AcademicConflictRule()])
    period_results = []

    for index, period in enumerate(selected_periods):
        period_courses = filter_courses_for_period(courses, selected_programs, period)
        schedule_count = scheduler.run_to_output(
            period_courses,
            period,
            output_manager,
            append=index > 0,
            write_header=index == 0,
        )

        period_results.append(
            PeriodRunResult(
                semester=period.semester.value,
                term=period.term.value,
                course_count=len(period_courses),
                schedule_count=schedule_count,
            )
        )

    return SchedulerRunResult(
        output_path=output_manager.get_full_path(),
        periods=period_results,
    )


def run_complete_count_workflow(
        output_config: Path,
        period_indexes: Optional[Sequence[int]] = None,
        parser: IParser | None = None,
        **kwargs: Any,
) -> CompleteSystemResult:
    source_config = _resolve_source_config(output_config, kwargs)
    courses, periods, selected_programs = load_domain_data(source_config, parser=parser)

    period_course_sets = build_period_course_sets(
        courses, periods, selected_programs, period_indexes
    )

    return CompleteSystemScheduler(rules=[AcademicConflictRule()]).count_complete_systems(
        period_course_sets
    )


def run_complete_write_workflow(
        output_config: Path,
        period_indexes: Optional[Sequence[int]] = None,
        max_systems: Optional[int] = None,
        parser: IParser | None = None,
        **kwargs: Any,
) -> CompleteSystemResult:
    source_config = _resolve_source_config(output_config, kwargs)
    courses, periods, selected_programs = load_domain_data(source_config, parser=parser)

    period_course_sets = build_period_course_sets(
        courses, periods, selected_programs, period_indexes
    )
    output_manager = TextOutputManager(str(output_config))

    return CompleteSystemScheduler(rules=[AcademicConflictRule()]).write_complete_systems(
        period_course_sets,
        output_manager,
        max_systems=max_systems,
    )


def run_complete_auto_workflow(
        output_config: Path,
        period_indexes: Optional[Sequence[int]] = None,
        time_limit_seconds: float = 30.0,
        parser: IParser | None = None,
        **kwargs: Any,
) -> CompleteSystemResult:
    source_config = _resolve_source_config(output_config, kwargs)
    courses, periods, selected_programs = load_domain_data(source_config, parser=parser)

    period_course_sets = build_period_course_sets(
        courses, periods, selected_programs, period_indexes
    )
    output_manager = TextOutputManager(str(output_config))

    return CompleteSystemScheduler(rules=[AcademicConflictRule()]).write_complete_systems_auto(
        period_course_sets,
        output_manager,
        time_limit_seconds=time_limit_seconds,
    )


def run_complete_auto_stream_workflow(
        output_config: Path,
        period_indexes: Optional[Sequence[int]] = None,
        time_limit_seconds: float = 30.0,
        batch_size: int = DEFAULT_COMPLETE_SYSTEM_BATCH_SIZE,
        output_stream: TextIO | None = None,
        progress_stream: TextIO | None = None,
        parser: IParser | None = None,
        **kwargs: Any,
) -> CompleteSystemResult:
    """Stream auto-mode complete systems for the desktop UI without blocking the UI."""
    return _run_complete_stream_workflow(
        output_config=output_config,
        period_indexes=period_indexes,
        max_systems=None,
        time_limit_seconds=time_limit_seconds,
        batch_size=batch_size,
        output_stream=output_stream,
        progress_stream=progress_stream,
        parser=parser,
        **kwargs,
    )


def run_complete_write_stream_workflow(
        output_config: Path,
        period_indexes: Optional[Sequence[int]] = None,
        max_systems: Optional[int] = None,
        batch_size: int = DEFAULT_COMPLETE_SYSTEM_BATCH_SIZE,
        output_stream: TextIO | None = None,
        progress_stream: TextIO | None = None,
        parser: IParser | None = None,
        **kwargs: Any,
) -> CompleteSystemResult:
    """Stream explicit complete-write output for callers that page results live."""
    return _run_complete_stream_workflow(
        output_config=output_config,
        period_indexes=period_indexes,
        max_systems=max_systems,
        time_limit_seconds=None,
        batch_size=batch_size,
        output_stream=output_stream,
        progress_stream=progress_stream,
        parser=parser,
        **kwargs,
    )


def run_complete_lazy_stream_workflow(
        output_config: Path,
        period_indexes: Optional[Sequence[int]] = None,
        max_systems: Optional[int] = None,
        batch_size: int = DEFAULT_COMPLETE_SYSTEM_BATCH_SIZE,
        input_stream: TextIO | None = None,
        output_stream: TextIO | None = None,
        progress_stream: TextIO | None = None,
        parser: IParser | None = None,
        **kwargs: Any,
) -> CompleteSystemResult:
    """
    Keep the complete-system generator alive and send one UI page at a time.

    The first batch is produced immediately. Later batches are produced only
    after the UI sends NEXT through stdin.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero.")

    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout
    progress_stream = progress_stream or sys.stderr
    started_at = time.perf_counter()

    source_config = _resolve_source_config(output_config, kwargs)
    courses, periods, selected_programs = load_domain_data(source_config, parser=parser)
    period_course_sets = build_period_course_sets(
        courses, periods, selected_programs, period_indexes
    )

    progress_stream.write("Preparing lazy complete-system stream...\n")
    progress_stream.flush()

    stream = CompleteSystemScheduler(rules=[AcademicConflictRule()]).stream_complete_systems(
        period_course_sets,
        max_systems=max_systems,
    )
    _write_stream_summary(output_stream, stream, time_limit_seconds=None)

    batches = stream.iter_batches(batch_size=batch_size)
    written_count = 0
    exhausted = False

    def write_next_batch() -> None:
        nonlocal written_count, exhausted

        try:
            batch = next(batches)
        except StopIteration:
            exhausted = True
            output_stream.write(f"{BATCH_END_MARKER}\n")
            output_stream.flush()
            return

        written_count = batch[-1].number
        output_stream.write("".join(system.text for system in batch))
        output_stream.write(f"{BATCH_END_MARKER}\n")
        output_stream.flush()

        progress_stream.write(
            f"Batch ready: {written_count:,} of "
            f"{stream.complete_system_count:,} complete systems cached.\n"
        )
        progress_stream.flush()

        if written_count >= stream.complete_system_count:
            exhausted = True

    write_next_batch()

    while not exhausted:
        command = input_stream.readline()
        if not command:
            break

        command = command.strip().upper()
        if command == LAZY_NEXT_COMMAND:
            write_next_batch()
        elif command == LAZY_STOP_COMMAND:
            break

    elapsed_seconds = time.perf_counter() - started_at
    truncated = written_count < stream.complete_system_count
    progress_stream.write(
        "Lazy stream finished: "
        f"{written_count:,} of {stream.complete_system_count:,} complete systems "
        f"in {elapsed_seconds:.2f} seconds.\n"
    )
    progress_stream.flush()

    return CompleteSystemResult(
        output_path=None,
        period_course_counts=stream.period_course_counts,
        period_schedule_counts=stream.period_schedule_counts,
        complete_system_count=stream.complete_system_count,
        written_system_count=written_count,
        elapsed_seconds=elapsed_seconds,
        truncated=truncated,
        auto_limit_seconds=None,
    )


def _run_complete_stream_workflow(
        output_config: Path,
        period_indexes: Optional[Sequence[int]],
        max_systems: Optional[int],
        time_limit_seconds: Optional[float],
        batch_size: int,
        output_stream: TextIO | None,
        progress_stream: TextIO | None,
        parser: IParser | None,
        **kwargs: Any,
) -> CompleteSystemResult:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero.")

    output_stream = output_stream or sys.stdout
    progress_stream = progress_stream or sys.stderr
    started_at = time.perf_counter()

    source_config = _resolve_source_config(output_config, kwargs)
    courses, periods, selected_programs = load_domain_data(source_config, parser=parser)
    period_course_sets = build_period_course_sets(
        courses, periods, selected_programs, period_indexes
    )

    progress_stream.write("Preparing complete systems for streaming...\n")
    progress_stream.flush()

    stream = CompleteSystemScheduler(rules=[AcademicConflictRule()]).stream_complete_systems(
        period_course_sets,
        max_systems=max_systems,
    )
    _write_stream_summary(output_stream, stream, time_limit_seconds)

    deadline = None
    if time_limit_seconds is not None:
        # Leave a small buffer so auto mode keeps the same careful time-limit behavior.
        deadline = started_at + max(0.0, time_limit_seconds - 0.25)

    written_count = 0
    batch: list[str] = []

    for system in stream.systems:
        if deadline is not None and time.perf_counter() >= deadline:
            break

        written_count = system.number
        batch.append(system.text)

        if len(batch) >= batch_size:
            output_stream.write("".join(batch))
            output_stream.flush()
            batch.clear()

    if batch:
        output_stream.write("".join(batch))
        output_stream.flush()

    truncated = written_count < stream.complete_system_count
    elapsed_seconds = time.perf_counter() - started_at

    progress_stream.write(
        "Stream finished: "
        f"{written_count:,} of {stream.complete_system_count:,} complete systems "
        f"in {elapsed_seconds:.2f} seconds.\n"
    )
    if truncated:
        progress_stream.write("Stream was truncated before all complete systems were generated.\n")
    progress_stream.flush()

    return CompleteSystemResult(
        output_path=None,
        period_course_counts=stream.period_course_counts,
        period_schedule_counts=stream.period_schedule_counts,
        complete_system_count=stream.complete_system_count,
        written_system_count=written_count,
        elapsed_seconds=elapsed_seconds,
        truncated=truncated,
        auto_limit_seconds=time_limit_seconds,
    )


def _write_stream_summary(stream_output: TextIO, stream, time_limit_seconds: float | None) -> None:
    stream_output.write("OFFICIAL UNIVERSITY COMPLETE EXAM SYSTEMS\n")
    stream_output.write("=" * 65 + "\n")
    stream_output.write(f"Total complete systems: {stream.complete_system_count:,}\n")
    stream_output.write(
        "Period course counts: "
        + ", ".join(f"{count:,}" for count in stream.period_course_counts)
        + "\n"
    )
    stream_output.write(
        "Period schedule counts: "
        + ", ".join(f"{count:,}" for count in stream.period_schedule_counts)
        + "\n"
    )
    if time_limit_seconds is not None:
        stream_output.write(f"Auto time limit: {time_limit_seconds:.2f} seconds\n")
    stream_output.write("\n")
    stream_output.flush()
