from dataclasses import dataclass
from datetime import date
from typing import Iterable, List

from src.models.academic import Course
from src.models.enums import RequirementType
from src.models.scheduling import ExamPeriod


@dataclass(frozen=True)
class ScheduledCourse:
    course: Course
    exam_date: date


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str


def validate_schedule(
    assignments: Iterable[ScheduledCourse],
    required_courses: Iterable[Course],
    period: ExamPeriod,
    k_days_mandatory: int = 0,
    m_days_any: int = 0,
) -> List[ValidationIssue]:
    """
    Independently validates one complete exam schedule.

    This validator does not use the scheduler's conflict graph or search logic.
    It checks the V1.0 requirements directly:
    - each required exam course appears exactly once
    - unscheduled evaluation types are not included
    - every date is valid for the exam period
    - critical same-day conflicts are rejected
    """
    assignment_list = list(assignments)
    required_list = list(required_courses)
    issues: List[ValidationIssue] = []

    _check_required_course_coverage(assignment_list, required_list, issues)
    _check_dates_and_evaluations(assignment_list, period, issues)
    _check_critical_conflicts(assignment_list, issues)
    #Spacing validations (Only executes if spacing constraints are defined)
    if k_days_mandatory > 0 or m_days_any > 0:
        _check_spacing_conflicts(assignment_list, issues, k_days_mandatory, m_days_any)

    return issues


def is_schedule_valid(
    assignments: Iterable[ScheduledCourse],
    required_courses: Iterable[Course],
    period: ExamPeriod,
) -> bool:
    return not validate_schedule(assignments, required_courses, period)


def _check_required_course_coverage(
    assignments: List[ScheduledCourse],
    required_courses: List[Course],
    issues: List[ValidationIssue],
) -> None:
    assigned_counts = {}
    for assignment in assignments:
        assigned_counts[assignment.course.course_id] = assigned_counts.get(assignment.course.course_id, 0) + 1

    required_ids = {course.course_id for course in required_courses}

    for course in required_courses:
        count = assigned_counts.get(course.course_id, 0)
        if count == 0:
            issues.append(
                ValidationIssue(
                    "MISSING_COURSE",
                    f"Required exam course {course.course_id} {course.name} is missing.",
                )
            )
        elif count > 1:
            issues.append(
                ValidationIssue(
                    "DUPLICATE_COURSE",
                    f"Required exam course {course.course_id} {course.name} appears {count} times.",
                )
            )

    for assignment in assignments:
        if assignment.course.course_id not in required_ids:
            issues.append(
                ValidationIssue(
                    "UNEXPECTED_COURSE",
                    f"Course {assignment.course.course_id} {assignment.course.name} is not required in this schedule.",
                )
            )


def _check_dates_and_evaluations(
    assignments: List[ScheduledCourse],
    period: ExamPeriod,
    issues: List[ValidationIssue],
) -> None:
    for assignment in assignments:
        if not assignment.course.evaluation.requires_scheduling():
            issues.append(
                ValidationIssue(
                    "NON_EXAM_COURSE",
                    f"Course {assignment.course.course_id} {assignment.course.name} does not require an exam slot.",
                )
            )

        if not period.is_date_valid(assignment.exam_date):
            issues.append(
                ValidationIssue(
                    "INVALID_DATE",
                    f"Course {assignment.course.course_id} {assignment.course.name} is scheduled on invalid date {assignment.exam_date}.",
                )
            )


def _check_critical_conflicts(
    assignments: List[ScheduledCourse],
    issues: List[ValidationIssue],
) -> None:
    for left_index in range(len(assignments)):
        left = assignments[left_index]
        for right in assignments[left_index + 1:]:
            if left.exam_date != right.exam_date:
                continue

            if _has_critical_conflict(left.course, right.course):
                issues.append(
                    ValidationIssue(
                        "CRITICAL_CONFLICT",
                        (
                            f"Courses {left.course.course_id} {left.course.name} and "
                            f"{right.course.course_id} {right.course.name} conflict on {left.exam_date}."
                        ),
                    )
                )


def _has_critical_conflict(left: Course, right: Course) -> bool:
    for left_affiliation in left.affiliations:
        for right_affiliation in right.affiliations:
            same_cohort = (
                left_affiliation.program_id == right_affiliation.program_id
                and left_affiliation.year == right_affiliation.year
            )
            if not same_cohort:
                continue

            both_elective = (
                left_affiliation.requirement_type == RequirementType.ELECTIVE
                and right_affiliation.requirement_type == RequirementType.ELECTIVE
            )
            if not both_elective:
                return True

    return False

def _check_spacing_conflicts(
        assignments: List[ScheduledCourse],
        issues: List[ValidationIssue],
        k_days_mandatory: int,
        m_days_any: int
) -> None:
    """
    Validates the generated matrix against the defined V2.0 spacing constraints.
    Appends a ValidationIssue if any two exams are scheduled too close together.
    """
    for left_index in range(len(assignments)):
        left = assignments[left_index]
        for right in assignments[left_index + 1:]:
            # Absolute calendar difference between the two exam dates
            delta_days = abs((left.exam_date - right.exam_date).days)

            for l_aff in left.course.affiliations:
                for r_aff in right.course.affiliations:
                    # Spacing constraints apply only when courses share a study program and year
                    if l_aff.program_id == r_aff.program_id and l_aff.year == r_aff.year:

                        # Constraint 2.2: Check minimal spacing defined for ANY two courses
                        if delta_days < m_days_any:
                            issues.append(
                                ValidationIssue(
                                    "GENERAL_SPACING_CONFLICT",
                                    f"Courses {left.course.course_id} and {right.course.course_id} "
                                    f"are {delta_days} days apart (minimum {m_days_any} required)."
                                )
                            )
                            # Break inner loop to prevent logging duplicate issues for the same pair
                            break

                        # Constraint 2.1: Check minimal spacing defined for MANDATORY courses
                        both_obligatory = (
                                l_aff.requirement_type == RequirementType.OBLIGATORY
                                and r_aff.requirement_type == RequirementType.OBLIGATORY
                        )
                        if both_obligatory and delta_days < k_days_mandatory:
                            issues.append(
                                ValidationIssue(
                                    "MANDATORY_SPACING_CONFLICT",
                                    f"Mandatory courses {left.course.course_id} and {right.course.course_id} "
                                    f"are {delta_days} days apart (minimum {k_days_mandatory} required)."
                                )
                            )
                            break

def _check_advanced_constraints(
        assignments: List[ScheduledCourse],
        issues: List[ValidationIssue],
        max_elective_conflicts: int,
        min_mandatory_span: int,
        max_daily_exams: int
) -> None:
    """
    Independently validates the final generated matrix against advanced capacity and span constraints.
    Appends descriptive ValidationIssues if any threshold rules are violated.
    """
    # 1. Evaluate Daily Exam Cap Constraint
    date_counts = {}
    for a in assignments:
        date_counts[a.exam_date] = date_counts.get(a.exam_date, 0) + 1
        if date_counts[a.exam_date] > max_daily_exams:
            issues.append(
                ValidationIssue(
                    "DAILY_CAP_EXCEEDED",
                    f"Date {a.exam_date} has {date_counts[a.exam_date]} exams (max allowed: {max_daily_exams})."
                )
            )

    # Prepare data structures for Span and Conflict evaluation
    cohort_mandatory_dates = {}
    program_elective_dates = {}

    for a in assignments:
        for aff in a.course.affiliations:
            # Group dates for the Mandatory Span constraint
            if aff.requirement_type == RequirementType.OBLIGATORY:
                cohort_key = (aff.program_id, aff.year)
                if cohort_key not in cohort_mandatory_dates:
                    cohort_mandatory_dates[cohort_key] = []
                cohort_mandatory_dates[cohort_key].append(a.exam_date)

            # Group dates for the Elective Conflicts constraint
            elif aff.requirement_type == RequirementType.ELECTIVE:
                prog_date_key = (aff.program_id, a.exam_date)
                program_elective_dates[prog_date_key] = program_elective_dates.get(prog_date_key, 0) + 1

    # 2. Evaluate Mandatory Span Constraint
    for (prog_id, year), dates in cohort_mandatory_dates.items():
        if len(dates) > 1:
            span = abs((max(dates) - min(dates)).days)
            if span < min_mandatory_span:
                issues.append(
                    ValidationIssue(
                        "MANDATORY_SPAN_TOO_SHORT",
                        f"Program {prog_id} Year {year} has a mandatory exam span of {span} days (min required: {min_mandatory_span})."
                    )
                )

    # 3. Evaluate Elective Conflicts Constraint
    program_conflicts = {}
    for (prog_id, date_val), count in program_elective_dates.items():
        if count > 1:
            # Combinatorics formula to find total number of unique overlapping pairs
            conflicts = (count * (count - 1)) // 2
            program_conflicts[prog_id] = program_conflicts.get(prog_id, 0) + conflicts

    for prog_id, total_conflicts in program_conflicts.items():
        if total_conflicts > max_elective_conflicts:
            issues.append(
                ValidationIssue(
                    "ELECTIVE_CONFLICTS_EXCEEDED",
                    f"Program {prog_id} has {total_conflicts} elective conflicts (max allowed: {max_elective_conflicts})."
                )
            )