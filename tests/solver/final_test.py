import pytest
import json
import time
from pathlib import Path
from datetime import date

from src.parser.FileParser import FileParser
from src.parser.course_factory import CourseFactory
from src.parser.period_factory import PeriodFactory
from src.solver.dev_scheduler import Scheduler
from src.rules.academic_conflict_rule import AcademicConflictRule
from output_manager import TextOutputManager

# Path Configuration pointing to root folder
ROOT_DIR = Path(__file__).resolve().parents[1]

PROGRAMS_FILE = ROOT_DIR / "data" / "Programs.txt"
EXAM_DATES_FILE = ROOT_DIR / "data" / "V1.0 ExamDates.txt"
COURSES_FILE = ROOT_DIR / "data" / "V1.0CourseDB.txt"

# שמירה בתיקייה הגלויה של הפרויקט כדי שתוכל לראות את הקובץ בסיום הריצה
OUTPUT_DIR = ROOT_DIR / "output"
OUTPUT_FILE = OUTPUT_DIR / "final_schedule.txt"


def test_full_system_integration():
    """
    REAL INTEGRATION TEST: Computes all configurations and saves the
    official master schedule into the project's output/ directory.
    Verifies that all millions of possible valid combinations are recorded.
    """
    assert COURSES_FILE.exists(), f"Missing file at: {COURSES_FILE}"
    assert EXAM_DATES_FILE.exists(), f"Missing file at: {EXAM_DATES_FILE}"
    assert PROGRAMS_FILE.exists(), f"Missing file at: {PROGRAMS_FILE}"

    # STEP 1: PARSE
    config = {
        "course_file": str(COURSES_FILE),
        "dates_file": str(EXAM_DATES_FILE),
        "user_file": str(PROGRAMS_FILE)
    }
    parser = FileParser()
    json_data = parser.parse_to_json(config)

    # STEP 2: FACTORY
    course_factory = CourseFactory()
    period_factory = PeriodFactory()

    all_courses = course_factory.build_all(json_data, "courses_node")
    all_periods = period_factory.build_all(json_data, "periods_node")

    parsed_json = json.loads(json_data)
    user_programs = [int(p) for p in parsed_json["user_node"]]

    # STEP 3: FILTER
    relevant_courses = []
    for course in all_courses:
        if course.evaluation.requires_scheduling():
            match_program = any(aff.program_id in user_programs for aff in course.affiliations)
            if match_program:
                relevant_courses.append(course)

    period = all_periods[0]

    # STEP 4: SOLVER SETUP
    scheduler = Scheduler(rules=[AcademicConflictRule()])

    # Configure TextOutputManager to save into the real output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    test_config_content = {
        "output_settings": {
            "base_directory": str(OUTPUT_DIR),
            "master_filename": "final_schedule"
        }
    }
    config_path = OUTPUT_DIR / "test_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(test_config_content, f)

    output_manager = TextOutputManager(str(config_path))

    # STEP 5: EXECUTION (The actual hard math and file-writing work)
    started_at = time.perf_counter()
    total_found = scheduler.run_to_output(relevant_courses, period, output_manager)
    duration = time.perf_counter() - started_at

    print(f"\n" + "=" * 50)
    print(f"[INFO] Total solutions found: {total_found:,}")
    print(f"[INFO] Calculation duration: {duration:.4f} seconds")
    print(f"[INFO] File saved to: {OUTPUT_FILE}")
    print(f"[INFO] Output file size: {OUTPUT_FILE.stat().st_size / (1024 * 1024):.2f} MB")
    print("=" * 50)

    # STEP 6: ASSERTIONS
    assert total_found > 1000000, f"Expected over a million solutions, got: {total_found:,}"
    assert duration < 30.0, f"Performance SLA violated: {duration:.2f}s"
    assert OUTPUT_FILE.exists(), "Output file was not generated!"

    content = OUTPUT_FILE.read_text(encoding="utf-8")
    assert "OFFICIAL UNIVERSITY MASTER EXAM SCHEDULE" in content
    assert "=== SEMESTER: FALL ===" in content
    assert "Schedule #1" in content