import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from src.output.output_manager import TextOutputManager
from src.models.academic import Course
from src.models.scheduling import ExamPeriod
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
    course_file: Path,
    dates_file: Path,
    user_file: Path,
) -> tuple[List[Course], List[ExamPeriod], List[int]]:
    json_data = FileParser().parse_to_json(
        {
            "course_file": str(course_file),
            "dates_file": str(dates_file),
            "user_file": str(user_file),
        }
    )

    courses = CourseFactory().build_all(json_data, "courses_node")
    periods = PeriodFactory().build_all(json_data, "periods_node")
    selected_programs = [int(program) for program in json.loads(json_data)["user_node"]]

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
) -> List[tuple[ExamPeriod, List[Course]]]:
    if period_indexes is None:
        selected_periods = periods
    else:
        selected_periods = [periods[index] for index in period_indexes]

    return [
        (period, filter_courses_for_period(courses, selected_programs, period))
        for period in selected_periods
    ]


def run_v1_workflow(
    course_file: Path,
    dates_file: Path,
    user_file: Path,
    output_config: Path,
    period_indexes: Optional[Sequence[int]] = None,
) -> SchedulerRunResult:
    courses, periods, selected_programs = load_domain_data(course_file, dates_file, user_file)

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
    course_file: Path,
    dates_file: Path,
    user_file: Path,
    period_indexes: Optional[Sequence[int]] = None,
) -> CompleteSystemResult:
    courses, periods, selected_programs = load_domain_data(course_file, dates_file, user_file)
    period_course_sets = build_period_course_sets(courses, periods, selected_programs, period_indexes)

    return CompleteSystemScheduler(rules=[AcademicConflictRule()]).count_complete_systems(period_course_sets)


def run_complete_write_workflow(
    course_file: Path,
    dates_file: Path,
    user_file: Path,
    output_config: Path,
    period_indexes: Optional[Sequence[int]] = None,
    max_systems: Optional[int] = None,
) -> CompleteSystemResult:
    courses, periods, selected_programs = load_domain_data(course_file, dates_file, user_file)
    period_course_sets = build_period_course_sets(courses, periods, selected_programs, period_indexes)
    output_manager = TextOutputManager(str(output_config))

    return CompleteSystemScheduler(rules=[AcademicConflictRule()]).write_complete_systems(
        period_course_sets,
        output_manager,
        max_systems=max_systems,
    )


def run_complete_auto_workflow(
    course_file: Path,
    dates_file: Path,
    user_file: Path,
    output_config: Path,
    period_indexes: Optional[Sequence[int]] = None,
    time_limit_seconds: float = 30.0,
) -> CompleteSystemResult:
    courses, periods, selected_programs = load_domain_data(course_file, dates_file, user_file)
    period_course_sets = build_period_course_sets(courses, periods, selected_programs, period_indexes)
    output_manager = TextOutputManager(str(output_config))

    return CompleteSystemScheduler(rules=[AcademicConflictRule()]).write_complete_systems_auto(
        period_course_sets,
        output_manager,
        time_limit_seconds=time_limit_seconds,
    )
