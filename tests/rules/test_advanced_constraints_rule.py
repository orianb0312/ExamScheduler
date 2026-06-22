import pytest
from datetime import date
from src.models.academic import Course, ProgramAffiliation, Exam
from src.models.enums import Semester, RequirementType
from src.rules.advanced_constraints_rule import AdvancedConstraintsRule


def create_mock_course(course_id: int, req_type: RequirementType, program_id: int = 1, year: int = 1) -> Course:
    """
    Helper factory to quickly generate isolated Course instances for testing complex constraint logic.
    """
    c = Course(course_id, f"Course {course_id}", "Dr. Test", Exam())
    c.add_affiliation(ProgramAffiliation(program_id, year, Semester.FALL, req_type))
    return c


def test_daily_cap_constraint_exceeded():
    """
    Verifies that scheduling more exams than the allowed max_daily_exams limit triggers a validation failure.
    """
    # Initialize rule with a strict daily cap of 2 exams
    rule = AdvancedConstraintsRule(max_elective_conflicts=10, min_mandatory_span=1, max_daily_exams=2)

    # Attempting to schedule 3 exams on the exact same date (Jan 1st)
    attempt = {
        create_mock_course(1, RequirementType.ELECTIVE): date(2026, 1, 1),
        create_mock_course(2, RequirementType.ELECTIVE): date(2026, 1, 1),
        create_mock_course(3, RequirementType.ELECTIVE): date(2026, 1, 1),
    }
    assert rule.is_valid(attempt) is False


def test_mandatory_span_too_short():
    """
    Verifies that if the timeframe between the first and last mandatory exams for a cohort
    is less than min_mandatory_span, the schedule is rejected.
    """
    # Enforce: Mandatory exams must span at least 5 days from start to finish
    rule = AdvancedConstraintsRule(max_elective_conflicts=10, min_mandatory_span=5, max_daily_exams=10)

    # Attempting a span of only 3 days (Jan 1 to Jan 4)
    attempt = {
        create_mock_course(1, RequirementType.OBLIGATORY): date(2026, 1, 1),
        create_mock_course(2, RequirementType.OBLIGATORY): date(2026, 1, 4),
    }
    assert rule.is_valid(attempt) is False


def test_mandatory_span_valid():
    """
    Verifies that a mandatory exam span equal to or strictly greater than min_mandatory_span is approved.
    """
    # Enforce: Mandatory exams must span at least 5 days
    rule = AdvancedConstraintsRule(max_elective_conflicts=10, min_mandatory_span=5, max_daily_exams=10)

    # 5-day span (Jan 1 to Jan 6) meets the requirement
    attempt = {
        create_mock_course(1, RequirementType.OBLIGATORY): date(2026, 1, 1),
        create_mock_course(2, RequirementType.OBLIGATORY): date(2026, 1, 6),
    }
    assert rule.is_valid(attempt) is True


def test_elective_conflicts_exceeded():
    """
    Verifies that the system correctly calculates combinatorial conflicts and rejects the schedule
    if a program exceeds the max_elective_conflicts threshold.
    """
    # Max 1 elective conflict allowed per program
    rule = AdvancedConstraintsRule(max_elective_conflicts=1, min_mandatory_span=1, max_daily_exams=10)

    c1 = create_mock_course(1, RequirementType.ELECTIVE)
    c2 = create_mock_course(2, RequirementType.ELECTIVE)
    c3 = create_mock_course(3, RequirementType.ELECTIVE)

    # 3 electives on the same day create 3 distinct overlapping pairs (conflicts): (1-2, 2-3, 1-3).
    # Since 3 conflicts > 1 limit, the rule must fail.
    attempt = {c1: date(2026, 1, 1), c2: date(2026, 1, 1), c3: date(2026, 1, 1)}
    assert rule.is_valid(attempt) is False


def test_elective_conflicts_valid():
    """
    Verifies that the schedule is approved when the combinatorial number of elective conflicts
    stays within the allowed limit.
    """
    # Max 1 elective conflict allowed per program
    rule = AdvancedConstraintsRule(max_elective_conflicts=1, min_mandatory_span=1, max_daily_exams=10)

    c1 = create_mock_course(1, RequirementType.ELECTIVE)
    c2 = create_mock_course(2, RequirementType.ELECTIVE)

    # 2 electives on the same day create exactly 1 conflict pair.
    # Since 1 conflict <= 1 limit, the rule passes.
    attempt = {c1: date(2026, 1, 1), c2: date(2026, 1, 1)}
    assert rule.is_valid(attempt) is True