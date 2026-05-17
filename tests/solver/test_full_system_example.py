from dataclasses import dataclass
from datetime import date, timedelta
from itertools import islice
from pathlib import Path
import json
import re
import time

import pytest

from src.rules.academic_conflict_rule import AcademicConflictRule
from src.validation.schedule_validator import ScheduledCourse, validate_schedule
from src.workflow import (
    filter_courses_for_period,
    load_domain_data,
    run_complete_auto_workflow,
    run_complete_count_workflow,
)


ROOT_DIR = Path(__file__).resolve().parents[2]

DEFAULT_COURSES_PATH = ROOT_DIR / "data" / "V1.0CourseDB.txt"
DEFAULT_EXAM_PERIODS_PATH = ROOT_DIR / "data" / "V1.0 ExamDates.txt"
DEFAULT_PROGRAMS_PATH = ROOT_DIR / "data" / "Programs.txt"

EXAM_LINE_PATTERN = re.compile(r"^.+ \| \d{4}-\d{2}-\d{2} \| .+$")
DATE_TOKEN_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

REQUIRED_OUTPUT_HEADERS = [
    "OFFICIAL UNIVERSITY COMPLETE EXAM SYSTEMS",
    "Total complete systems:",
    "Period course counts:",
    "Period schedule counts:",
    "Complete System #",
    "=== SEMESTER:",
    "[TERM:",
]

AUTO_TEST_TIME_LIMIT_SECONDS = 2.0
MAX_FULL_SYSTEM_SECONDS = 5.0
MAX_INDEPENDENT_VALIDATION_CHECKS = 1000


@dataclass(frozen=True)
class ExampleSystemRun:
    count_result: object
    result: object
    output_path: Path
    elapsed: float
    output_text: str
    courses: list
    exam_periods: list
    selected_programs: list
    relevant_courses: list


@pytest.fixture(scope="module")
def example_system(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("full_system_example")
    output_dir = tmp_path / "output"
    output_config = tmp_path / "output_config.json"
    output_config.write_text(
        json.dumps(
            {
                "output_settings": {
                    "base_directory": str(output_dir),
                    "master_filename": "exam_schedules",
                }
            }
        ),
        encoding="utf-8",
    )

    courses, exam_periods, selected_programs = load_domain_data(
        DEFAULT_COURSES_PATH,
        DEFAULT_EXAM_PERIODS_PATH,
        DEFAULT_PROGRAMS_PATH,
    )

    relevant_courses = []
    for period in exam_periods:
        for course in filter_courses_for_period(courses, selected_programs, period):
            if course not in relevant_courses:
                relevant_courses.append(course)

    count_result = run_complete_count_workflow(
        DEFAULT_COURSES_PATH,
        DEFAULT_EXAM_PERIODS_PATH,
        DEFAULT_PROGRAMS_PATH,
    )

    started_at = time.perf_counter()
    result = run_complete_auto_workflow(
        DEFAULT_COURSES_PATH,
        DEFAULT_EXAM_PERIODS_PATH,
        DEFAULT_PROGRAMS_PATH,
        output_config,
        time_limit_seconds=AUTO_TEST_TIME_LIMIT_SECONDS,
    )
    elapsed = time.perf_counter() - started_at

    return ExampleSystemRun(
        count_result=count_result,
        result=result,
        output_path=result.output_path,
        elapsed=elapsed,
        output_text=result.output_path.read_text(encoding="utf-8"),
        courses=courses,
        exam_periods=exam_periods,
        selected_programs=selected_programs,
        relevant_courses=relevant_courses,
    )


def output_exam_lines(output_text):
    return [
        line.strip()
        for line in output_text.splitlines()
        if EXAM_LINE_PATTERN.match(line.strip())
    ]


def _course_name(line):
    return line.split(" | ")[0].strip()


def _exam_date(line):
    return line.split(" | ")[1].strip()


def _expanded_excluded_dates(exam_periods):
    excluded_dates = set()

    for period in exam_periods:
        for exclusion in period.exclusions:
            current = exclusion.start_date
            end = exclusion.end_date or exclusion.start_date

            while current <= end:
                excluded_dates.add(current.isoformat())
                current += timedelta(days=1)

    return excluded_dates


def _iter_output_period_schedules(output_text, course_by_name):
    current_schedule = []
    current_semester = None
    current_term = None

    for raw_line in output_text.splitlines():
        line = raw_line.strip()

        if line.startswith("Complete System #"):
            if current_schedule:
                yield (current_semester, current_term), current_schedule
            current_schedule = []
            current_semester = None
            current_term = None
            continue

        if line.startswith("=== SEMESTER:"):
            if current_schedule:
                yield (current_semester, current_term), current_schedule
            current_schedule = []
            current_semester = line.removeprefix("=== SEMESTER:").removesuffix("===").strip()
            current_term = None
            continue

        if line.startswith("[TERM:"):
            if current_schedule:
                yield (current_semester, current_term), current_schedule
            current_schedule = []
            current_term = line.removeprefix("[TERM:").removesuffix("]").strip()
            continue

        if not EXAM_LINE_PATTERN.match(line):
            continue

        course_name, date_text, _instructor = [part.strip() for part in line.split(" | ", maxsplit=2)]
        current_schedule.append(
            ScheduledCourse(
                course=course_by_name[course_name],
                exam_date=date.fromisoformat(date_text),
            )
        )

    if current_schedule:
        yield (current_semester, current_term), current_schedule


def test_full_system_run_with_example_files_creates_non_empty_output_file(example_system):
    assert example_system.output_path.exists()
    assert example_system.output_path.is_file()
    assert example_system.output_path.stat().st_size > 0

    assert example_system.result.output_path == example_system.output_path
    assert len(example_system.selected_programs) > 0
    assert len(example_system.courses) > 0
    assert len(example_system.relevant_courses) > 0
    assert len(example_system.exam_periods) > 0
    assert example_system.result.complete_system_count > 0
    assert example_system.result.written_system_count > 0


def test_full_system_counts_match_current_example_files(example_system):
    assert example_system.count_result.complete_system_count > 0

    assert example_system.result.period_course_counts == example_system.count_result.period_course_counts
    assert example_system.result.period_schedule_counts == example_system.count_result.period_schedule_counts
    assert example_system.result.complete_system_count == example_system.count_result.complete_system_count
    assert 0 <= example_system.result.written_system_count <= example_system.result.complete_system_count
    assert example_system.result.truncated == (
        example_system.result.written_system_count
        < example_system.result.complete_system_count
    )


def test_full_system_output_schedules_only_exam_courses_from_selected_programs(example_system):
    allowed_exam_course_names = {course.name.strip() for course in example_system.relevant_courses}

    scheduled_course_names = {
        _course_name(line)
        for line in output_exam_lines(example_system.output_text)
    }

    if example_system.result.written_system_count:
        assert scheduled_course_names
    assert scheduled_course_names <= allowed_exam_course_names


def test_full_system_output_format_is_readable_and_valid(example_system):
    output = example_system.output_text
    lines = output.splitlines()
    exam_lines = output_exam_lines(output)

    assert output.endswith("\n")
    assert lines[0] == "OFFICIAL UNIVERSITY COMPLETE EXAM SYSTEMS"

    for required_header in REQUIRED_OUTPUT_HEADERS:
        assert required_header in output

    assert output.count("Complete System #") == example_system.result.written_system_count
    assert len(exam_lines) == (
        example_system.result.written_system_count
        * sum(example_system.result.period_course_counts)
    )

    for line in exam_lines:
        parts = [part.strip() for part in line.split(" | ")]

        assert len(parts) == 3
        assert parts[0]
        assert DATE_TOKEN_PATTERN.match(parts[1])
        assert parts[2]


def test_full_system_does_not_use_excluded_dates_from_example_periods(example_system):
    excluded_dates = _expanded_excluded_dates(example_system.exam_periods)

    used_dates = {
        _exam_date(line)
        for line in output_exam_lines(example_system.output_text)
    }

    if example_system.result.written_system_count:
        assert used_dates
    assert used_dates.isdisjoint(excluded_dates)


def test_full_system_generated_period_schedules_have_no_conflicts(example_system):
    course_by_name = {course.name.strip(): course for course in example_system.relevant_courses}
    rule = AcademicConflictRule()

    checked_count = 0
    for _period_key, schedule in _iter_output_period_schedules(example_system.output_text, course_by_name):
        checked_count += 1
        attempt_state = {
            scheduled_course.course: scheduled_course.exam_date
            for scheduled_course in schedule
        }
        assert rule.is_valid(attempt_state)

    non_empty_period_count = sum(1 for count in example_system.result.period_course_counts if count > 0)
    assert checked_count == example_system.result.written_system_count * non_empty_period_count


def test_full_system_generated_schedules_pass_independent_validator(example_system):
    course_by_name = {course.name.strip(): course for course in example_system.relevant_courses}
    required_by_period = {
        (period.semester.value, period.term.value): filter_courses_for_period(
            example_system.courses,
            example_system.selected_programs,
            period,
        )
        for period in example_system.exam_periods
    }
    period_by_key = {
        (period.semester.value, period.term.value): period
        for period in example_system.exam_periods
    }

    period_schedules = _iter_output_period_schedules(example_system.output_text, course_by_name)
    non_empty_period_count = sum(1 for count in example_system.result.period_course_counts if count > 0)
    expected_checks = min(
        MAX_INDEPENDENT_VALIDATION_CHECKS,
        example_system.result.written_system_count * non_empty_period_count,
    )

    checked_count = 0
    for period_key, schedule in islice(period_schedules, expected_checks):
        checked_count += 1
        issues = validate_schedule(
            schedule,
            required_by_period[period_key],
            period_by_key[period_key],
        )
        assert issues == []

    assert checked_count == expected_checks


def test_full_system_run_finishes_within_required_time_limit(example_system):
    assert example_system.elapsed < MAX_FULL_SYSTEM_SECONDS
