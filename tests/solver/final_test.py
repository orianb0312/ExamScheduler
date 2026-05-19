import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Any, Dict

from src.workflow import (
    filter_courses_for_period,
    load_domain_data,
    run_complete_count_workflow,
    run_v1_workflow,
)

ROOT_DIR = Path(__file__).resolve().parents[2]

PROGRAMS_FILE = ROOT_DIR / "data" / "Programs.txt"
EXAM_DATES_FILE = ROOT_DIR / "data" / "V1.0 ExamDates.txt"
COURSES_FILE = ROOT_DIR / "data" / "V1.0CourseDB.txt"


def _create_test_output_config(tmp_path: Path) -> Path:
    """
    Generate a dynamic mock JSON config file matching the application's unified structure.
    Injects local file paths under the 'file' block as expected by the workflows.
    """
    config_path = tmp_path / "period_output_config.json"
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
                    "master_filename": "final_schedule",
                },
            }
        ),
        encoding="utf-8",
    )
    return config_path


def _expected_period_rows(config_path: Path) -> Tuple[List[Tuple[str, str, int, int]], set, set]:
    """
    Simulate target expectations by extracting the configuration block and feeding it
    safely into factories, ensuring alignment with signature modifications.
    """
    # CLI overrides that will be passed into the count workflow
    cli_overrides = {
        "course_file": COURSES_FILE,
        "dates_file": EXAM_DATES_FILE,
        "user_file": PROGRAMS_FILE,
    }

    # Open the configuration file to extract the matching file block values
    with open(config_path, encoding="utf-8") as fh:
        config_data = json.load(fh)
    file_config = config_data.get("file", {})

    # Resolve the source configuration block identically to _resolve_source_config
    source_config = {
        "course_file": str(cli_overrides["course_file"] or file_config.get("course_file")),
        "dates_file": str(cli_overrides["dates_file"] or file_config.get("dates_file")),
        "user_file": str(cli_overrides["user_file"] or file_config.get("user_file")),
    }

    # Load data using the correct modern single-argument or dictionary setup
    courses, periods, selected_programs = load_domain_data(source_config)
    count_result = run_complete_count_workflow(output_config=config_path, **cli_overrides)

    rows = []
    relevant_course_names = set()
    non_exam_course_names = {
        course.name.strip()
        for course in courses
        if not course.evaluation.requires_scheduling()
    }

    for index, period in enumerate(periods):
        period_courses = filter_courses_for_period(courses, selected_programs, period)
        relevant_course_names.update(course.name.strip() for course in period_courses)

        schedule_count = count_result.period_schedule_counts[index]
        if not period_courses:
            schedule_count = 0

        rows.append(
            (
                period.semester.value,
                period.term.value,
                len(period_courses),
                schedule_count,
            )
        )

    return rows, relevant_course_names, non_exam_course_names


def test_period_workflow_matches_current_default_inputs(tmp_path: Path) -> None:
    assert COURSES_FILE.exists(), f"Missing file at: {COURSES_FILE}"
    assert EXAM_DATES_FILE.exists(), f"Missing file at: {EXAM_DATES_FILE}"
    assert PROGRAMS_FILE.exists(), f"Missing file at: {PROGRAMS_FILE}"

    # Generate the configuration file and pass it down to resolve expected results
    config_path = _create_test_output_config(tmp_path)
    expected_periods, relevant_course_names, non_exam_course_names = _expected_period_rows(config_path)

    # Invoke workflow with the valid parameters structure
    result = run_v1_workflow(
        output_config=config_path,
        course_file=COURSES_FILE,
        dates_file=EXAM_DATES_FILE,
        user_file=PROGRAMS_FILE,
    )

    assert [
               (period.semester, period.term, period.course_count, period.schedule_count)
               for period in result.periods
           ] == expected_periods
    assert result.total_schedules == sum(row[3] for row in expected_periods)

    assert result.output_path.exists()
    output = result.output_path.read_text(encoding="utf-8")

    assert "OFFICIAL UNIVERSITY MASTER EXAM SCHEDULE" in output
    assert "Schedule #1" in output
    assert "=== SEMESTER: FALL ===" in output
    assert "[TERM: Aleph]" in output
    assert "[TERM: Bet]" in output
    assert "EMPTY SCHEDULE: No exams have been scheduled for this period." in output

    for course_name in relevant_course_names:
        assert course_name in output
    for course_name in non_exam_course_names:
        assert course_name not in output