import pytest
from datetime import date
from src.models.enums import Semester, Term, RequirementType
from src.models.academic import Course, ProgramAffiliation, Exam
from src.models.scheduling import ExamPeriod, DateExclusion
from src.solver.scheduler import Scheduler
from src.rules.academic_conflict_rule import AcademicConflictRule


@pytest.fixture
def basic_period():
    """
    Creates a basic 1-week exam period for testing.
    Includes one exclusion (Saturday).
    """
    period = ExamPeriod(
        semester=Semester.FALL,
        term=Term.ALEPH,
        start_date=date(2026, 1, 25),
        end_date=date(2026, 1, 31)
    )
    # Exclude Saturday as per faculty requirements
    period.add_exclusion(DateExclusion(start_date=date(2026, 1, 31)))
    return period


@pytest.fixture
def conflict_rule():
    """Provides the AcademicConflictRule instance."""
    return AcademicConflictRule()


@pytest.fixture
def scheduler(conflict_rule):
    """Provides a Scheduler instance configured with the academic conflict rule."""
    return Scheduler(rules=[conflict_rule])


def test_no_critical_conflict_allowed(scheduler, basic_period):
    """
    TEST: Ensure two Obligatory courses from the same program/year
    are NEVER scheduled on the same day.
    """
    affil = ProgramAffiliation(83101, 1, Semester.FALL, RequirementType.OBLIGATORY)

    c1 = Course(10001, "Calculus", "Prof. X", Exam())
    c1.add_affiliation(affil)

    c2 = Course(10002, "Physics", "Prof. Y", Exam())
    c2.add_affiliation(affil)

    results = scheduler.run([c1, c2], basic_period)

    for system in results:
        # Assert that the dates assigned to c1 and c2 are different
        assert system[c1] != system[c2]


def test_elective_conflict_allowed(scheduler, basic_period):
    """
    TEST: Ensure two Elective courses from the same program/year
    CAN be scheduled on the same day (The allowed exception in V1.0).
    """
    affil = ProgramAffiliation(83101, 1, Semester.FALL, RequirementType.ELECTIVE)

    c1 = Course(10003, "Elective A", "Dr. A", Exam())
    c1.add_affiliation(affil)

    c2 = Course(10004, "Elective B", "Dr. B", Exam())
    c2.add_affiliation(affil)

    results = scheduler.run([c1, c2], basic_period)

    # Check if there is at least one valid system where they share the same date
    same_day_found = any(system[c1] == system[c2] for system in results)
    assert same_day_found is True


def test_excluded_dates_honored(scheduler, basic_period):
    """
    TEST: Ensure exams are never scheduled on excluded dates (e.g., Saturdays/Holidays).
    """
    c1 = Course(10001, "Calculus", "Prof. X", Exam())
    c1.add_affiliation(ProgramAffiliation(83101, 1, Semester.FALL, RequirementType.OBLIGATORY))

    results = scheduler.run([c1], basic_period)

    excluded_date = date(2026, 1, 31)  # The Saturday we excluded in the fixture
    for system in results:
        assert system[c1] != excluded_date


def test_performance_limit(scheduler, basic_period):
    """
    TEST: Ensure the scheduler finds solutions within the 30-second time limit (EXS-32).
    """
    import time

    # Mocking a small set of courses to test basic performance
    courses = []
    for i in range(4):
        c = Course(20000 + i, f"Course {i}", "Staff", Exam())
        c.add_affiliation(ProgramAffiliation(83101, i + 1, Semester.FALL, RequirementType.OBLIGATORY))
        courses.append(c)

    start_time = time.time()
    scheduler.run(courses, basic_period)
    duration = time.time() - start_time

    # Performance requirement from section 5.1
    assert duration < 30