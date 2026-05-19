import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Any, Dict

from src.output.output_manager import TextOutputManager
from src.models.academic import Course
from src.models.scheduling import ExamPeriod
from src.parser.IParser import IParser
from src.parser.file_parser import FileParser
from src.parser.course_factory import CourseFactory
from src.parser.period_factory import PeriodFactory
from src.rules.academic_conflict_rule import AcademicConflictRule
from src.solver.complete_scheduler import CompleteSystemResult, CompleteSystemScheduler
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
        # Use CLI argument values if provided; otherwise, fall back to the JSON config values
        return {
            "course_file": str(kwargs.get("course_file") or file_config.get("course_file")),
            "dates_file":  str(kwargs.get("dates_file") or file_config.get("dates_file")),
            "user_file":   str(kwargs.get("user_file") or file_config.get("user_file")),
        }

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