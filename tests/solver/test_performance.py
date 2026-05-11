import pytest
from datetime import date
from src.models.enums import Semester, Term, RequirementType
from src.models.academic import Course, ProgramAffiliation, Exam
from src.models.scheduling import ExamPeriod, DateExclusion
from src.solver.scheduler import Scheduler
from src.rules.academic_conflict_rule import AcademicConflictRule


def test_full_academic_scenario():
    """
    Comprehensive test covering all rules of Version 1.0:
    - Multiple Programs
    - Multiple Years
    - Date Exclusions (Weekends/Holidays)
    - Performance SLA (< 30s for ALL results)
    """
    # 1. Setup Period (21 days) with weekends excluded
    period = ExamPeriod(Semester.FALL, Term.ALEPH, date(2026, 1, 25), date(2026, 2, 14))
    period.add_exclusion(DateExclusion(date(2026, 1, 30), date(2026, 1, 31)))  # Weekend 1
    period.add_exclusion(DateExclusion(date(2026, 2, 6), date(2026, 2, 7)))  # Weekend 2

    # 2. Setup 15 Courses across 3 different Programs
    courses = []
    for prog_id in [83101, 83102, 83200]:
        for year in [1, 2]:
            c = Course(prog_id + year, f"Course {prog_id}-{year}", "Staff", Exam())
            c.add_affiliation(ProgramAffiliation(prog_id, year, Semester.FALL, RequirementType.OBLIGATORY))
            courses.append(c)

    scheduler = Scheduler(rules=[AcademicConflictRule()])

    # 3. Execution
    import time
    start = time.time()
    results = scheduler.run(courses, period)
    duration = time.time() - start

    # 4. Assertions
    assert duration < 30, f"System failed SLA! Took {duration:.2f}s to find all solutions."
    assert len(results) > 0, "No valid schedules found for a valid scenario."

    # Verify no exam is on a weekend
    excluded = [date(2026, 1, 30), date(2026, 1, 31), date(2026, 2, 6), date(2026, 2, 7)]
    for schedule in results:
        for exam_date in schedule.values():
            assert exam_date not in excluded