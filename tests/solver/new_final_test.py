import json
import time
from pathlib import Path

from src.workflow import (
    filter_courses_for_period,
    load_domain_data,
    run_complete_auto_workflow,
    run_complete_count_workflow,
)

ROOT_DIR = Path(__file__).resolve().parents[2]

PROGRAMS_FILE = ROOT_DIR / "data" / "Programs.txt"
EXAM_DATES_FILE = ROOT_DIR / "data" / "V1.0 ExamDates.txt"
COURSES_FILE = ROOT_DIR / "data" / "V1.0CourseDB.txt"

AUTO_TEST_TIME_LIMIT_SECONDS = 2.0
MAX_AUTO_TEST_SECONDS = 5.0


def _create_test_output_config(tmp_path: Path) -> Path:
    """
    Generate a dynamic mock JSON config file matching the application's unified structure.
    Injects default local file references into the config block.
    """
    config_path = tmp_path / "complete_output_config.json"
    config_path.write_text(
        json.dumps(
            {
                "source_type": "file",
                "file": {
                    "course_file": str(COURSES_FILE),
                    "dates_file": str(EXAM_DATES_FILE),
                    "user_file": str(PROGRAMS_FILE),
                },
                "output_settings": {
                    "base_directory": str(tmp_path / "output"),
                    "master_filename": "new_final_schedule",
                },
            }
        ),
        encoding="utf-8",
    )
    return config_path


def _product(values: list) -> int:
    total = 1
    for value in values:
        total *= value
    return total


def _expected_period_course_counts(config_path: Path) -> list:
    """
    Load parsing data by properly unpacking target configurations.
    """
    source_config = {
        "course_file": str(COURSES_FILE),
        "dates_file": str(EXAM_DATES_FILE),
        "user_file": str(PROGRAMS_FILE),
    }
    courses, periods, selected_programs = load_domain_data(source_config)
    return [
        len(filter_courses_for_period(courses, selected_programs, period))
        for period in periods
    ]


def _expected_output_course_names(config_path: Path) -> tuple:
    """
    Extract expected matching and missing course entities across tracking indices.
    """
    source_config = {
        "course_file": str(COURSES_FILE),
        "dates_file": str(EXAM_DATES_FILE),
        "user_file": str(PROGRAMS_FILE),
    }
    courses, periods, selected_programs = load_domain_data(source_config)

    scheduled_course_names = set()
    for period in periods:
        scheduled_course_names.update(
            course.name.strip()
            for course in filter_courses_for_period(courses, selected_programs, period)
        )

    non_exam_course_names = {
        course.name.strip()
        for course in courses
        if not course.evaluation.requires_scheduling()
    }

    return scheduled_course_names, non_exam_course_names


def test_complete_count_workflow_matches_current_default_inputs(tmp_path: Path) -> None:
    config_path = _create_test_output_config(tmp_path)

    # Supply the config file path alongside keyword file parameters
    result = run_complete_count_workflow(
        output_config=config_path,
        course_file=COURSES_FILE,
        dates_file=EXAM_DATES_FILE,
        user_file=PROGRAMS_FILE,
    )

    assert result.output_path is None
    assert result.period_course_counts == _expected_period_course_counts(config_path)
    assert result.complete_system_count == _product(result.period_schedule_counts)
    assert result.complete_system_count > 0
    assert result.written_system_count == 0
    assert result.truncated is False


def test_auto_complete_workflow_writes_limited_current_default_results(tmp_path: Path) -> None:
    config_path = _create_test_output_config(tmp_path)

    count_result = run_complete_count_workflow(
        output_config=config_path,
        course_file=COURSES_FILE,
        dates_file=EXAM_DATES_FILE,
        user_file=PROGRAMS_FILE,
    )

    started_at = time.perf_counter()
    result = run_complete_auto_workflow(
        output_config=config_path,
        time_limit_seconds=AUTO_TEST_TIME_LIMIT_SECONDS,
        course_file=COURSES_FILE,
        dates_file=EXAM_DATES_FILE,
        user_file=PROGRAMS_FILE,
    )
    duration = time.perf_counter() - started_at

    assert result.period_course_counts == count_result.period_course_counts
    assert result.period_schedule_counts == count_result.period_schedule_counts
    assert result.complete_system_count == count_result.complete_system_count
    assert 0 <= result.written_system_count <= result.complete_system_count
    assert result.truncated == (result.written_system_count < result.complete_system_count)
    assert duration < MAX_AUTO_TEST_SECONDS

    output = result.output_path.read_text(encoding="utf-8")
    scheduled_course_names, non_exam_course_names = _expected_output_course_names(config_path)

    assert "OFFICIAL UNIVERSITY COMPLETE EXAM SYSTEMS" in output
    assert f"Total complete systems: {result.complete_system_count:,}" in output
    if result.written_system_count:
        assert "Complete System #1" in output
        assert any(course_name in output for course_name in scheduled_course_names)
    for course_name in non_exam_course_names:
        assert course_name not in output