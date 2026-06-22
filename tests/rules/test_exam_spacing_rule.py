import pytest
from datetime import date
from src.models.academic import Course, ProgramAffiliation, Exam
from src.models.enums import Semester, RequirementType
from src.rules.exam_spacing_rule import ExamSpacingRule


def create_mock_course(course_id: int, req_type: RequirementType, program_id: int = 1, year: int = 1) -> Course:
    """
    Helper factory to quickly generate isolated course instances for testing spacing logic.
    """
    c = Course(course_id, f"Course {course_id}", "Dr. Test", Exam())
    c.add_affiliation(ProgramAffiliation(program_id, year, Semester.FALL, req_type))
    return c


def test_mandatory_spacing_invalid_too_close():
    """
    Verifies that scheduling two mandatory courses with fewer than 'k' days
    between them triggers a validation failure.
    """
    # Enforce: Mandatory courses must be at least 3 days apart
    rule = ExamSpacingRule(k_days_mandatory=3, m_days_any=1)

    c1 = create_mock_course(101, RequirementType.OBLIGATORY)
    c2 = create_mock_course(102, RequirementType.OBLIGATORY)

    # 2 days absolute difference (Jan 1 to Jan 3) - should be rejected
    attempt = {c1: date(2026, 1, 1), c2: date(2026, 1, 3)}
    assert rule.is_valid(attempt) is False


def test_mandatory_spacing_valid_sufficient_gap():
    """
    Verifies that mandatory courses scheduled exactly at or beyond the 'k' days
    minimum are successfully approved by the rule.
    """
    # Enforce: Mandatory courses must be at least 3 days apart
    rule = ExamSpacingRule(k_days_mandatory=3, m_days_any=1)

    c1 = create_mock_course(101, RequirementType.OBLIGATORY)
    c2 = create_mock_course(102, RequirementType.OBLIGATORY)

    # 3 days absolute difference (Jan 1 to Jan 4) - should be allowed
    attempt = {c1: date(2026, 1, 1), c2: date(2026, 1, 4)}
    assert rule.is_valid(attempt) is True


def test_general_spacing_invalid_too_close():
    """
    Verifies that any pair of courses (even if one is elective) failing to meet
    the base 'm' days gap are strictly rejected.
    """
    # Enforce: ANY courses must be at least 2 days apart
    rule = ExamSpacingRule(k_days_mandatory=4, m_days_any=2)

    c1 = create_mock_course(201, RequirementType.ELECTIVE)
    c2 = create_mock_course(202, RequirementType.OBLIGATORY)

    # 1 day absolute difference (Jan 1 to Jan 2) - should be rejected by m=2 constraint
    attempt = {c1: date(2026, 1, 1), c2: date(2026, 1, 2)}
    assert rule.is_valid(attempt) is False


def test_general_spacing_valid_sufficient_gap():
    """
    Verifies that a mixed pair (elective + mandatory) is approved if it respects
    the general 'm' days gap, bypassing the stricter 'k' gap which only applies to two mandatory exams.
    """
    # Enforce: ANY courses must be at least 2 days apart, mandatory pair requires 4 days
    rule = ExamSpacingRule(k_days_mandatory=4, m_days_any=2)

    c1 = create_mock_course(201, RequirementType.ELECTIVE)
    c2 = create_mock_course(202, RequirementType.OBLIGATORY)

    # 2 days absolute difference (Jan 1 to Jan 3) - should be allowed since one is elective and m=2 is met
    attempt = {c1: date(2026, 1, 1), c2: date(2026, 1, 3)}
    assert rule.is_valid(attempt) is True


def test_different_programs_ignore_spacing():
    """
    Verifies that the spacing logic completely ignores exams belonging to
    different programs or different academic years, allowing them to be scheduled freely.
    """
    # Enforce: Strictly high gaps (5 for mandatory, 3 for any)
    rule = ExamSpacingRule(k_days_mandatory=5, m_days_any=3)

    # Initialize courses under completely different program IDs (Program 1 vs Program 2)
    c1 = create_mock_course(301, RequirementType.OBLIGATORY, program_id=1)
    c2 = create_mock_course(302, RequirementType.OBLIGATORY, program_id=2)

    # 0 days difference (Same day placement) - should be approved because cohorts don't overlap
    attempt = {c1: date(2026, 1, 1), c2: date(2026, 1, 1)}
    assert rule.is_valid(attempt) is True