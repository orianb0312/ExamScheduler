import json
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Any, Dict, TextIO

from src.interfaces import ISchedulingRule
from src.output.output_manager import TextOutputManager
from src.models.academic import Course
from src.models.scheduling import ExamPeriod
from src.parser.IParser import IParser
from src.parser.file_parser import FileParser
from src.parser.course_factory import CourseFactory
from src.parser.period_factory import PeriodFactory
from src.process_protocol import BATCH_END_MARKER, LAZY_NEXT_COMMAND, LAZY_STOP_COMMAND
from src.rules.academic_conflict_rule import AcademicConflictRule
from src.rules.advanced_constraints_rule import AdvancedConstraintsRule
from src.rules.exam_spacing_rule import ExamSpacingRule
from src.rules.ai_copilot_rule import AICopilotRule
from src.solver.complete_scheduler import (
    DEFAULT_COMPLETE_SYSTEM_BATCH_SIZE,
    CompleteSystemResult,
    CompleteSystemScheduler,
    ScheduleGenerationTimedOut,
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


@dataclass(frozen=True)
class SchedulerDomainContext:
    """Parsed scheduler inputs reused by workflows and post-run exports."""

    parsed_data: Dict[str, Any]
    courses: List[Course]
    periods: List[ExamPeriod]
    selected_programs: List[int]

    @property
    def sort_priority(self) -> Sequence[str]:
        # Analytics and scheduling both read the exact same normalized priority list.
        return self.parsed_data.get("sorting_node") or []


def _parse_domain_data(
    source_config: Dict[str, Any],
    parser: IParser | None = None,
) -> tuple[dict[str, Any], List[Course], List[ExamPeriod], List[int]]:
    if parser is None:
        parser = FileParser()

    json_data = parser.parse_to_json(source_config)
    parsed_data = json.loads(json_data)
    courses = CourseFactory().build_all(parsed_data, "courses_node")
    periods = PeriodFactory().build_all(parsed_data, "periods_node")
    selected_programs = [int(program) for program in parsed_data.get("user_node", [])]
    return parsed_data, courses, periods, selected_programs


def _build_scheduler_rules(
    constraints: Dict[str, int] | None,
    ai_rules_file: Path,
) -> List[ISchedulingRule]:
    constraints = constraints or {}
    rules: List[ISchedulingRule] = [AcademicConflictRule()]

    if (
        "min_days_between_mandatory" in constraints
        or "min_days_between_any" in constraints
    ):
        rules.append(
            ExamSpacingRule(
                k_days_mandatory=constraints.get("min_days_between_mandatory", 0),
                m_days_any=constraints.get("min_days_between_any", 0),
            )
        )

    if any(
        key in constraints
        for key in (
            "max_elective_conflicts",
            "min_days_before_last_mandatory",
            "max_exams_per_day",
        )
    ):
        rules.append(
            AdvancedConstraintsRule(
                max_elective_conflicts=constraints.get(
                    "max_elective_conflicts",
                    sys.maxsize,
                ),
                min_mandatory_span=constraints.get(
                    "min_days_before_last_mandatory",
                    0,
                ),
                max_daily_exams=constraints.get(
                    "max_exams_per_day",
                    sys.maxsize,
                ),
            )
        )

    rules.append(AICopilotRule(ai_rules_file))

    return rules


def _build_workflow_rules(
    parsed_data: Dict[str, Any],
    output_config: Path,
    kwargs: Dict[str, Any],
) -> List[ISchedulingRule]:
    configured_path = kwargs.get("ai_rules_file")
    if configured_path is None:
        configured_path = (
            Path(output_config).expanduser().resolve().parent
            / "data"
            / "active_ai_rules.json"
        )
    absolute_ai_rules_path = Path(configured_path).expanduser().resolve()
    return _build_scheduler_rules(
        parsed_data.get("constraints_node"),
        absolute_ai_rules_path,
    )


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
    _parsed_data, courses, periods, selected_programs = _parse_domain_data(
        source_config,
        parser=parser,
    )
    return courses, periods, selected_programs


def load_domain_context(
        output_config: Path,
        parser: IParser | None = None,
        **kwargs: Any,
) -> SchedulerDomainContext:
    """Load the same parsed inputs used by a CLI workflow run."""
    source_config = _resolve_source_config(output_config, kwargs)
    parsed_data, courses, periods, selected_programs = _parse_domain_data(
        source_config,
        parser=parser,
    )
    return SchedulerDomainContext(
        parsed_data=parsed_data,
        courses=courses,
        periods=periods,
        selected_programs=selected_programs,
    )


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
        sorting_file = kwargs.get("sorting_file") or file_config.get("sorting_file")
        # Use CLI argument values if provided; otherwise, fall back to the JSON config values
        source_config = {
            "course_file": str(kwargs.get("course_file") or file_config.get("course_file")),
            "dates_file":  str(kwargs.get("dates_file") or file_config.get("dates_file")),
            "user_file":   str(kwargs.get("user_file") or file_config.get("user_file")),
        }
        if constraints_file:
            # Do not invent defaults here; parsing decides whether the file is valid.
            source_config["constraints_file"] = str(constraints_file)
        if sorting_file:
            source_config["sorting_file"] = str(sorting_file)
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
    parsed_data, courses, periods, selected_programs = _parse_domain_data(
        source_config,
        parser=parser,
    )

    if period_indexes is None:
        selected_periods = periods
    else:
        selected_periods = [periods[index] for index in period_indexes]

    output_manager = TextOutputManager(str(output_config))
    scheduler = Scheduler(
        rules=_build_workflow_rules(parsed_data, output_config, kwargs)
    )
    sort_priority = parsed_data.get("sorting_node") or []
    period_results = []

    for index, period in enumerate(selected_periods):
        period_courses = filter_courses_for_period(courses, selected_programs, period)
        schedule_count = scheduler.run_to_output(
            period_courses,
            period,
            output_manager,
            append=index > 0,
            write_header=index == 0,
            sort_priority=sort_priority,
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
    parsed_data, courses, periods, selected_programs = _parse_domain_data(
        source_config,
        parser=parser,
    )

    period_course_sets = build_period_course_sets(
        courses, periods, selected_programs, period_indexes
    )

    return CompleteSystemScheduler(
        rules=_build_workflow_rules(parsed_data, output_config, kwargs)
    ).count_complete_systems(
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
    parsed_data, courses, periods, selected_programs = _parse_domain_data(
        source_config,
        parser=parser,
    )

    period_course_sets = build_period_course_sets(
        courses, periods, selected_programs, period_indexes
    )
    output_manager = TextOutputManager(str(output_config))

    return CompleteSystemScheduler(
        rules=_build_workflow_rules(parsed_data, output_config, kwargs)
    ).write_complete_systems(
        period_course_sets,
        output_manager,
        max_systems=max_systems,
        sort_priority=parsed_data.get("sorting_node") or [],
    )


def run_complete_auto_workflow(
        output_config: Path,
        period_indexes: Optional[Sequence[int]] = None,
        time_limit_seconds: float = 30.0,
        parser: IParser | None = None,
        **kwargs: Any,
) -> CompleteSystemResult:
    source_config = _resolve_source_config(output_config, kwargs)
    parsed_data, courses, periods, selected_programs = _parse_domain_data(
        source_config,
        parser=parser,
    )

    period_course_sets = build_period_course_sets(
        courses, periods, selected_programs, period_indexes
    )
    output_manager = TextOutputManager(str(output_config))

    return CompleteSystemScheduler(
        rules=_build_workflow_rules(parsed_data, output_config, kwargs)
    ).write_complete_systems_auto(
        period_course_sets,
        output_manager,
        time_limit_seconds=time_limit_seconds,
        sort_priority=parsed_data.get("sorting_node") or [],
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
        time_limit_seconds: float | None = None,
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
    parsed_data, courses, periods, selected_programs = _parse_domain_data(
        source_config,
        parser=parser,
    )
    period_course_sets = build_period_course_sets(
        courses, periods, selected_programs, period_indexes
    )
    rules = _build_workflow_rules(parsed_data, output_config, kwargs)
    sort_priority = parsed_data.get("sorting_node") or []

    progress_stream.write("Preparing lazy complete-system stream...\n")
    progress_stream.flush()

    scheduler = CompleteSystemScheduler(rules=rules)
    total_is_exact = time_limit_seconds is None or bool(sort_priority)
    batch_deadline: float | None = None
    exact_count_result: CompleteSystemResult | None = None
    count_thread: threading.Thread | None = None
    output_lock = threading.Lock()

    def current_batch_deadline() -> float | None:
        return batch_deadline

    def write_stdout(text: str) -> None:
        with output_lock:
            output_stream.write(text)
            output_stream.flush()

    def write_exact_count_update(result: CompleteSystemResult) -> None:
        lines = [
            f"Total complete systems: {result.complete_system_count:,}\n",
            "Period schedule counts: "
            + ", ".join(f"{count:,}" for count in result.period_schedule_counts)
            + "\n\n",
        ]
        write_stdout("".join(lines))

    def calculate_exact_count() -> None:
        nonlocal exact_count_result
        try:
            progress_stream.write("Calculating exact complete-system total...\n")
            progress_stream.flush()
            result = CompleteSystemScheduler(rules=rules).count_complete_systems(
                period_course_sets
            )
            exact_count_result = result
            write_exact_count_update(result)
            progress_stream.write(
                f"Exact total ready: {result.complete_system_count:,} complete systems.\n"
            )
            progress_stream.flush()
        except Exception as exc:
            progress_stream.write(f"Exact total calculation failed: {exc}\n")
            progress_stream.flush()

    def start_exact_count_worker() -> None:
        nonlocal count_thread
        if total_is_exact or count_thread is not None:
            return
        count_thread = threading.Thread(
            target=calculate_exact_count,
            name="complete-system-total-counter",
            daemon=True,
        )
        count_thread.start()

    if total_is_exact:
        stream = scheduler.stream_complete_systems(
            period_course_sets,
            max_systems=max_systems,
            sort_priority=sort_priority,
        )
    else:
        stream = scheduler.stream_complete_systems_on_demand(
            period_course_sets,
            max_systems=max_systems,
            deadline=current_batch_deadline,
        )

    timed_out = False
    try:
        _write_stream_summary(
            output_stream,
            stream,
            time_limit_seconds=time_limit_seconds,
            total_is_exact=total_is_exact,
        )

        systems = iter(stream.systems)
        written_count = 0
        exhausted = False

        def write_next_batch() -> None:
            nonlocal batch_deadline, written_count, exhausted, timed_out

            batch = []
            if time_limit_seconds is not None:
                batch_deadline = time.perf_counter() + max(0.0, time_limit_seconds - 0.25)

            try:
                while len(batch) < batch_size:
                    if (
                        batch_deadline is not None
                        and time.perf_counter() >= batch_deadline
                    ):
                        exhausted = True
                        timed_out = True
                        break
                    try:
                        batch.append(next(systems))
                    except StopIteration:
                        exhausted = True
                        break
                    except ScheduleGenerationTimedOut:
                        exhausted = True
                        timed_out = True
                        break
            finally:
                batch_deadline = None

            if not batch:
                write_stdout(f"{BATCH_END_MARKER}\n")
                return

            written_count = batch[-1].number
            write_stdout("".join(system.text for system in batch) + f"{BATCH_END_MARKER}\n")

            progress_stream.write(
                f"Batch ready: {written_count:,}"
                f"{_format_total_suffix(stream, total_is_exact)} "
                "complete systems cached.\n"
            )
            progress_stream.flush()

            if total_is_exact and written_count >= stream.complete_system_count:
                exhausted = True

        write_next_batch()
        start_exact_count_worker()

        while not exhausted:
            command = input_stream.readline()
            if not command:
                break

            command = command.strip().upper()
            if command == LAZY_NEXT_COMMAND:
                write_next_batch()
            elif command == LAZY_STOP_COMMAND:
                break
    finally:
        stream.close()
        if count_thread is not None:
            count_thread.join(timeout=0.05)

    elapsed_seconds = time.perf_counter() - started_at
    complete_system_count = (
        stream.complete_system_count
        if total_is_exact
        else exact_count_result.complete_system_count
        if exact_count_result is not None
        else written_count
    )
    truncated = (
        timed_out
        or (not total_is_exact and not exhausted)
        or (total_is_exact and written_count < stream.complete_system_count)
    )
    progress_stream.write(
        "Lazy stream finished: "
        f"{written_count:,}{_format_total_suffix(stream, total_is_exact)} "
        "complete systems "
        f"in {elapsed_seconds:.2f} seconds.\n"
    )
    if timed_out:
        progress_stream.write("Lazy stream stopped at the auto time limit.\n")
    elif time_limit_seconds is not None and not exhausted:
        progress_stream.write("Lazy stream stopped before all batches were requested.\n")
    progress_stream.flush()

    return CompleteSystemResult(
        output_path=None,
        period_course_counts=stream.period_course_counts,
        period_schedule_counts=stream.period_schedule_counts,
        complete_system_count=complete_system_count,
        written_system_count=written_count,
        elapsed_seconds=elapsed_seconds,
        truncated=truncated,
        auto_limit_seconds=time_limit_seconds,
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
    parsed_data, courses, periods, selected_programs = _parse_domain_data(
        source_config,
        parser=parser,
    )
    period_course_sets = build_period_course_sets(
        courses, periods, selected_programs, period_indexes
    )
    rules = _build_workflow_rules(parsed_data, output_config, kwargs)

    progress_stream.write("Preparing complete systems for streaming...\n")
    progress_stream.flush()

    stream = CompleteSystemScheduler(rules=rules).stream_complete_systems(
        period_course_sets,
        max_systems=max_systems,
        sort_priority=parsed_data.get("sorting_node") or [],
    )
    try:
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
    finally:
        stream.close()

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


def _write_stream_summary(
    stream_output: TextIO,
    stream,
    time_limit_seconds: float | None,
    total_is_exact: bool = True,
) -> None:
    stream_output.write("OFFICIAL UNIVERSITY COMPLETE EXAM SYSTEMS\n")
    stream_output.write("=" * 65 + "\n")
    if total_is_exact:
        stream_output.write(f"Total complete systems: {stream.complete_system_count:,}\n")
    else:
        stream_output.write(
            "Total complete systems: calculating in background\n"
        )
    stream_output.write(
        "Period course counts: "
        + ", ".join(f"{count:,}" for count in stream.period_course_counts)
        + "\n"
    )
    if total_is_exact:
        stream_output.write(
            "Period schedule counts: "
            + ", ".join(f"{count:,}" for count in stream.period_schedule_counts)
            + "\n"
        )
    else:
        stream_output.write(
            "Period schedule counts: generated on demand for the visible batch\n"
        )
    if time_limit_seconds is not None:
        stream_output.write(f"Auto time limit: {time_limit_seconds:.2f} seconds\n")
    stream_output.write("\n")
    stream_output.flush()


def _format_total_suffix(stream, total_is_exact: bool) -> str:
    if not total_is_exact:
        return ""
    return f" of {stream.complete_system_count:,}"
