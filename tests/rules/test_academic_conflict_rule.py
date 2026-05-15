import pytest
from datetime import date
from src.models.academic import Course, ProgramAffiliation, Exam
from src.models.enums import Semester, RequirementType
from src.rules.academic_conflict_rule_m import AcademicConflictRule

@pytest.fixture
def conflict_rule():
    return AcademicConflictRule()

def test_critical_conflict_same_year_program(conflict_rule):
    """מוודא פסילה: שני קורסי חובה, אותה תוכנית, אותה שנה, אותו תאריך"""
    eval_method = Exam()
    affil1 = ProgramAffiliation(program_id=83108, year=2, semester=Semester.FALL, requirement_type=RequirementType.OBLIGATORY)
    course1 = Course(course_id=11111, name="Math", instructor="Dr. A", evaluation=eval_method)
    course1.add_affiliation(affil1)

    affil2 = ProgramAffiliation(program_id=83108, year=2, semester=Semester.FALL, requirement_type=RequirementType.OBLIGATORY)
    course2 = Course(course_id=22222, name="Physics", instructor="Dr. B", evaluation=eval_method)
    course2.add_affiliation(affil2)

    attempt_state = {
        course1: date(2026, 1, 15),
        course2: date(2026, 1, 15)
    }

    assert conflict_rule.is_valid(attempt_state) is False

def test_elective_exception_allowed(conflict_rule):
    """מוודא אישור: שני קורסי בחירה, אותה תוכנית, אותה שנה, אותו תאריך"""
    eval_method = Exam()
    affil1 = ProgramAffiliation(program_id=83108, year=2, semester=Semester.FALL, requirement_type=RequirementType.ELECTIVE)
    course1 = Course(course_id=33333, name="AI", instructor="Dr. C", evaluation=eval_method)
    course1.add_affiliation(affil1)

    affil2 = ProgramAffiliation(program_id=83108, year=2, semester=Semester.FALL, requirement_type=RequirementType.ELECTIVE)
    course2 = Course(course_id=44444, name="ML", instructor="Dr. D", evaluation=eval_method)
    course2.add_affiliation(affil2)

    attempt_state = {
        course1: date(2026, 1, 15),
        course2: date(2026, 1, 15)
    }

    assert conflict_rule.is_valid(attempt_state) is True

def test_different_year_exception_allowed(conflict_rule):
    """מוודא אישור: אותה תוכנית, אותו תאריך, אבל שנות לימוד שונות (שנה א' לעומת שנה ב')"""
    eval_method = Exam()
    affil1 = ProgramAffiliation(program_id=83108, year=1, semester=Semester.FALL, requirement_type=RequirementType.OBLIGATORY)
    course1 = Course(course_id=55555, name="Intro CS", instructor="Dr. E", evaluation=eval_method)
    course1.add_affiliation(affil1)

    affil2 = ProgramAffiliation(program_id=83108, year=2, semester=Semester.FALL, requirement_type=RequirementType.OBLIGATORY)
    course2 = Course(course_id=66666, name="Advanced CS", instructor="Dr. F", evaluation=eval_method)
    course2.add_affiliation(affil2)

    attempt_state = {
        course1: date(2026, 1, 15),
        course2: date(2026, 1, 15)
    }

    assert conflict_rule.is_valid(attempt_state) is True

def test_mixed_obligatory_and_elective_same_program_year_is_conflict(conflict_rule):
    eval_method = Exam()
    affil1 = ProgramAffiliation(
        program_id=83108, year=2, semester=Semester.FALL,
        requirement_type=RequirementType.OBLIGATORY
    )
    course1 = Course(course_id=77771, name="Algorithms", instructor="Dr. G", evaluation=eval_method)
    course1.add_affiliation(affil1)
    affil2 = ProgramAffiliation(
        program_id=83108, year=2, semester=Semester.FALL,
        requirement_type=RequirementType.ELECTIVE
    )
    course2 = Course(course_id=77772, name="Robotics", instructor="Dr. H", evaluation=eval_method)
    course2.add_affiliation(affil2)
    attempt_state = {
        course1: date(2026, 1, 15),
        course2: date(2026, 1, 15),
    }
    assert conflict_rule.is_valid(attempt_state) is False

def test_different_program_same_year_same_date_is_allowed(conflict_rule):
    eval_method = Exam()

    affil1 = ProgramAffiliation(
        program_id=83108, year=2, semester=Semester.FALL,
        requirement_type=RequirementType.OBLIGATORY
    )
    course1 = Course(course_id=77773, name="Signals", instructor="Dr. I", evaluation=eval_method)
    course1.add_affiliation(affil1)

    affil2 = ProgramAffiliation(
        program_id=99999, year=2, semester=Semester.FALL,
        requirement_type=RequirementType.OBLIGATORY
    )
    course2 = Course(course_id=77774, name="Circuits", instructor="Dr. J", evaluation=eval_method)
    course2.add_affiliation(affil2)

    attempt_state = {
        course1: date(2026, 1, 15),
        course2: date(2026, 1, 15),
    }

    assert conflict_rule.is_valid(attempt_state) is True

def test_same_program_year_different_dates_is_allowed(conflict_rule):
    eval_method = Exam()

    affil1 = ProgramAffiliation(
        program_id=83108, year=2, semester=Semester.FALL,
        requirement_type=RequirementType.OBLIGATORY
    )
    course1 = Course(course_id=77775, name="Databases", instructor="Dr. K", evaluation=eval_method)
    course1.add_affiliation(affil1)

    affil2 = ProgramAffiliation(
        program_id=83108, year=2, semester=Semester.FALL,
        requirement_type=RequirementType.OBLIGATORY
    )
    course2 = Course(course_id=77776, name="OS", instructor="Dr. L", evaluation=eval_method)
    course2.add_affiliation(affil2)

    attempt_state = {
        course1: date(2026, 1, 15),
        course2: date(2026, 1, 16),
    }

    assert conflict_rule.is_valid(attempt_state) is True

def test_multi_affiliation_conflict_detected_on_any_shared_program_year(conflict_rule):
    eval_method = Exam()

    course1 = Course(course_id=77777, name="Shared A", instructor="Dr. M", evaluation=eval_method)
    course1.add_affiliation(ProgramAffiliation(
        program_id=83108, year=2, semester=Semester.FALL,
        requirement_type=RequirementType.OBLIGATORY
    ))
    course1.add_affiliation(ProgramAffiliation(
        program_id=12345, year=1, semester=Semester.FALL,
        requirement_type=RequirementType.ELECTIVE
    ))

    course2 = Course(course_id=77778, name="Shared B", instructor="Dr. N", evaluation=eval_method)
    course2.add_affiliation(ProgramAffiliation(
        program_id=83108, year=2, semester=Semester.FALL,
        requirement_type=RequirementType.OBLIGATORY
    ))

    attempt_state = {
        course1: date(2026, 1, 15),
        course2: date(2026, 1, 15),
    }

    assert conflict_rule.is_valid(attempt_state) is False

def test_is_valid_empty_attempt_state(conflict_rule):
    assert conflict_rule.is_valid({}) is True

def test_is_valid_single_course(conflict_rule):
    eval_method = Exam()
    affil = ProgramAffiliation(83108, 2, Semester.FALL, RequirementType.OBLIGATORY)
    course = Course(30001, "Single", "Dr. A", eval_method)
    course.add_affiliation(affil)

    assert conflict_rule.is_valid({course: date(2026, 1, 15)}) is True

def test_same_date_without_shared_program_year_is_valid(conflict_rule):
    eval_method = Exam()

    c1 = Course(30002, "C1", "Dr. B", eval_method)
    c1.add_affiliation(ProgramAffiliation(83108, 1, Semester.FALL, RequirementType.OBLIGATORY))

    c2 = Course(30003, "C2", "Dr. C", eval_method)
    c2.add_affiliation(ProgramAffiliation(83108, 2, Semester.FALL, RequirementType.OBLIGATORY))

    attempt_state = {c1: date(2026, 1, 15), c2: date(2026, 1, 15)}
    assert conflict_rule.is_valid(attempt_state) is True