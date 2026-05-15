import pytest
import time
from datetime import date, timedelta
from src.models.enums import Semester, Term, RequirementType
from src.models.academic import Course, ProgramAffiliation, Exam
from src.models.scheduling import ExamPeriod, DateExclusion
from src.solver.scheduler import Scheduler
from src.rules.academic_conflict_rule_m import AcademicConflictRule


def test_production_level_semester_simulation():
    """
    PRODUCTION LEVEL STRESS TEST:
    - Period: Full Semester duration (approx. 90 days).
    - Exclusions: Every Saturday within the range and a holiday break.
    - Courses: 15 Mandatory courses.
    - Constraint Logic: High-density constraints created by cross-listing courses
      between 3 major programs (e.g., CS, EE, and Math).
    - Performance Requirement: Must find all valid permutations in < 30 seconds.
    """

    # 1. Setup a 90-day exam period (3 months)
    start_dt = date(2026, 7, 1)
    end_dt = date(2026, 9, 28)
    period = ExamPeriod(Semester.SPRING, Term.ALEPH, start_dt, end_dt)

    # 2. Add realistic exclusions: All Saturdays in the range
    curr = start_dt
    while curr <= end_dt:
        if curr.weekday() == 5:  # 5 represents Saturday in Python's datetime
            period.add_exclusion(DateExclusion(curr))
        curr += timedelta(days=1)

    # 3. Add a holiday exclusion period (e.g., Summer Break simulation)
    period.add_exclusion(DateExclusion(date(2026, 8, 15), date(2026, 8, 17)))

    # 4. Create 15 Courses with heavy SHARED program affiliations
    # In a real system, shared courses create complex constraints.
    courses = []
    programs = [83100, 83200, 83300]  # CS, EE, Math

    for i in range(15):
        c = Course(70000 + i, f"Global_Core_{i}", "Senior Faculty", Exam())

        # Primary Program Affiliation (Obligatory)
        c.add_affiliation(ProgramAffiliation(
            programs[i % 3], 1, Semester.SPRING, RequirementType.OBLIGATORY
        ))

        # Secondary Program Affiliation (Cross-listed / Shared)
        c.add_affiliation(ProgramAffiliation(
            programs[(i + 1) % 3], 1, Semester.SPRING, RequirementType.OBLIGATORY
        ))
        courses.append(c)

    # 5. Initialize Scheduler with the academic conflict rule
    scheduler = Scheduler(rules=[AcademicConflictRule()])

    # 6. Execution and Benchmarking
    start_time = time.time()
    results = scheduler.run(courses, period)
    duration = time.time() - start_time

    # 7. Production Assertions
    # Performance SLA Check: Must complete in under 30 seconds
    assert duration < 30, f"Production simulation failed SLA! Took {duration:.2f} seconds."

    # Integrity Check: Ensure valid solutions were generated
    assert len(results) > 0, "No valid schedules found for the production scenario."

    # Consistency Check: Verify rule enforcement on a sample result
    sample_schedule = results[0]
    assigned_dates = list(sample_schedule.values())

    # Check for minimum distribution across unique dates
    assert len(set(assigned_dates)) >= 5, "Logical error: Too many collisions in result."

    print(f"\n[PROD TEST] Simulation finished in {duration:.4f}s. Systems found: {len(results)}")