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
