import json
from datetime import date, timedelta
from itertools import product

import pytest

from src.output.output_manager import TextOutputManager
from src.models.academic import Course, Exam, ProgramAffiliation, Project
from src.models.enums import RequirementType, Semester, Term
from src.models.scheduling import DateExclusion, ExamPeriod
from src.rules.academic_conflict_rule import AcademicConflictRule
from src.solver.period_scheduler import Scheduler
from src.validation.schedule_validator import ScheduledCourse, validate_schedule
from src.rules.exam_spacing_rule import ExamSpacingRule
from src.sorting.schedule_priority import MANDATORY_MIN_GAP


def _affiliation(
    program_id=83101,
    year=1,
    semester=Semester.FALL,
    requirement_type=RequirementType.OBLIGATORY,
):
    return ProgramAffiliation(
        program_id=program_id,
        year=year,
        semester=semester,
        requirement_type=requirement_type,
    )


def _course(course_id, name, affiliations, evaluation=None):
    return Course(
        course_id=course_id,
        name=name,
        instructor=f"Dr. {name}",
        evaluation=evaluation or Exam(),
        affiliations=affiliations,
    )


def _period():
    return ExamPeriod(
        semester=Semester.FALL,
        term=Term.ALEPH,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 3),
        exclusions=[DateExclusion(date(2026, 1, 2))],
    )


def _available_dates(period):
    current = period.start_date
    dates = []

    while current <= period.end_date:
        if period.is_date_valid(current):
            dates.append(current)
        current += timedelta(days=1)

    return dates


def _canonical(assignments):
    return tuple(
        sorted(
            (assignment.course.course_id, assignment.exam_date)
            for assignment in assignments
        )
    )


def _brute_force_schedules(courses, period):
    valid_schedules = set()
    dates = _available_dates(period)

    for date_combination in product(dates, repeat=len(courses)):
        assignments = [
            ScheduledCourse(course, exam_date)
            for course, exam_date in zip(courses, date_combination)
        ]
        if not validate_schedule(assignments, courses, period):
            valid_schedules.add(_canonical(assignments))

    return valid_schedules


"""def _run_scheduler(tmp_path, courses, period):
    output_dir = tmp_path / "output"
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "output_settings": {
                    "base_directory": str(output_dir),
                    "master_filename": "correctness_schedule",
                }
            }
        ),
        encoding="utf-8",
    )"""


def _run_scheduler(tmp_path, courses, period, rules=None):
    """
    Executes the period scheduler. Allows injecting custom rules (like spacing)
    to override or complement the default V1.0 academic rules.
    """
    if rules is None:
        rules = [AcademicConflictRule()]

    output_dir = tmp_path / "output"
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "output_settings": {
                    "base_directory": str(output_dir),
                    "master_filename": "correctness_schedule",
                }
            }
        ),
        encoding="utf-8",
    )

    output_manager = TextOutputManager(str(config_path))
    # Pass the customized rules list into the Scheduler instance
    count = Scheduler(rules).run_to_output(courses, period, output_manager)
    parsed_schedules = _parse_output(output_manager.get_full_path(), courses)

    assert count == len(parsed_schedules)
    return parsed_schedules


def _parse_output(output_path, courses):
    course_by_name = {course.name: course for course in courses}
    schedules = []
    current = []

    for raw_line in output_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if line.startswith("Schedule #"):
            if current:
                schedules.append(current)
            current = []
            continue

        if " | " not in line:
            continue

        course_name, date_text, _instructor = [part.strip() for part in line.split("|", maxsplit=2)]
        current.append(ScheduledCourse(course_by_name[course_name], date.fromisoformat(date_text)))

    if current:
        schedules.append(current)

    return schedules


def test_sorted_period_output_rejects_unbounded_materialization(tmp_path):
    courses = [
        _course(10001, "Algorithms", [_affiliation()]),
        _course(10002, "Databases", [_affiliation()]),
    ]
    output_dir = tmp_path / "output"
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "output_settings": {
                    "base_directory": str(output_dir),
                    "master_filename": "guarded_period_schedule",
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="more than 1 schedules"):
        Scheduler([AcademicConflictRule()]).run_to_output(
            courses,
            _period(),
            TextOutputManager(str(config_path)),
            sort_priority=[MANDATORY_MIN_GAP],
            max_sorted_schedules=1,
        )


def _canonical_output_schedules(parsed_schedules):
    return {_canonical(schedule) for schedule in parsed_schedules}


def test_validator_rejects_invalid_schedule_reasons():
    period = _period()
    algorithms = _course(10001, "Algorithms", [_affiliation()])
    databases = _course(10002, "Databases", [_affiliation()])
    project = _course(10003, "Project", [_affiliation()], Project())

    issues = validate_schedule(
        [
            ScheduledCourse(algorithms, date(2026, 1, 2)),
            ScheduledCourse(databases, date(2026, 1, 2)),
            ScheduledCourse(project, date(2026, 1, 1)),
        ],
        [algorithms, databases],
        period,
    )

    issue_codes = {issue.code for issue in issues}
    assert "INVALID_DATE" in issue_codes
    assert "CRITICAL_CONFLICT" in issue_codes
    assert "NON_EXAM_COURSE" in issue_codes
    assert "UNEXPECTED_COURSE" in issue_codes


def test_new_scheduler_matches_brute_force_for_required_conflicts(tmp_path):
    period = _period()
    courses = [
        _course(10001, "Algorithms", [_affiliation()]),
        _course(10002, "Databases", [_affiliation()]),
        _course(10003, "Physics", [_affiliation(year=2)]),
    ]

    brute_force = _brute_force_schedules(courses, period)
    optimized = _canonical_output_schedules(_run_scheduler(tmp_path, courses, period))

    assert optimized == brute_force
    assert len(optimized) == 4


def test_new_scheduler_matches_brute_force_for_multi_affiliation_conflicts(tmp_path):
    period = _period()
    cross_listed = _course(
        10001,
        "Cross Listed",
        [
            _affiliation(program_id=83101, year=1),
            _affiliation(program_id=83102, year=2),
        ],
    )
    year_two = _course(10002, "Year Two", [_affiliation(program_id=83102, year=2)])
    independent = _course(10003, "Independent", [_affiliation(program_id=83103, year=2)])
    courses = [cross_listed, year_two, independent]

    brute_force = _brute_force_schedules(courses, period)
    optimized = _canonical_output_schedules(_run_scheduler(tmp_path, courses, period))

    assert optimized == brute_force
    assert len(optimized) == 4


def test_new_scheduler_matches_brute_force_for_elective_exception(tmp_path):
    period = _period()
    courses = [
        _course(10001, "Robotics", [_affiliation(requirement_type=RequirementType.ELECTIVE)]),
        _course(10002, "Vision", [_affiliation(requirement_type=RequirementType.ELECTIVE)]),
    ]

    brute_force = _brute_force_schedules(courses, period)
    optimized = _canonical_output_schedules(_run_scheduler(tmp_path, courses, period))

    assert optimized == brute_force
    assert len(optimized) == 4


def test_every_emitted_schedule_passes_independent_validator(tmp_path):
    period = _period()
    courses = [
        _course(10001, "Algorithms", [_affiliation()]),
        _course(10002, "Databases", [_affiliation()]),
        _course(10003, "Physics", [_affiliation(year=2)]),
    ]

    parsed_schedules = _run_scheduler(tmp_path, courses, period)

    for schedule in parsed_schedules:
        assert validate_schedule(schedule, courses, period) == []

def test_new_scheduler_enforces_spacing_rules(tmp_path):
    """
    Integration Test: Proves that the backtracking algorithm actively uses ExamSpacingRule
    to prune invalid schedule combinations during generation.
    """
    # 5 days total available dates
    period = ExamPeriod(
        semester=Semester.FALL,
        term=Term.ALEPH,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 5),
        exclusions=[],
    )

    # Two obligatory courses in the same program
    courses = [
        _course(10001, "Math", [_affiliation()]),
        _course(10002, "Physics", [_affiliation()]),
    ]

    # Enforce a strict minimum 3-day gap between mandatory exams
    rules = [AcademicConflictRule(), ExamSpacingRule(k_days_mandatory=3, m_days_any=1)]

    parsed_schedules = _run_scheduler(tmp_path, courses, period, rules=rules)

    # Mathematical proof: With 5 available dates and a 3-day required distance,
    # the only valid index pairs are: (1,4), (1,5), (2,5) and their permutations (4,1), (5,1), (5,2).
    # Thus, exactly 6 valid schedules should be generated.
    assert len(parsed_schedules) == 6
