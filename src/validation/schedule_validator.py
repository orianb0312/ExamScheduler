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