import json
from pathlib import Path

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

def _output_config(tmp_path):
    config_path = tmp_path / "period_output_config.json"
    config_path.write_text(
        json.dumps(
            {
                "output_settings": {
                    "base_directory": str(tmp_path / "output"),
                    "master_filename": "final_schedule",
                }
            }
        ),
        encoding="utf-8",
    )
    return config_path


def _expected_period_rows():
    courses, periods, selected_programs = load_domain_data(
        COURSES_FILE,
        EXAM_DATES_FILE,
        PROGRAMS_FILE,
    )
    count_result = run_complete_count_workflow(
        COURSES_FILE,
        EXAM_DATES_FILE,
        PROGRAMS_FILE,
    )

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


def test_period_workflow_matches_current_default_inputs(tmp_path):
    assert COURSES_FILE.exists(), f"Missing file at: {COURSES_FILE}"
    assert EXAM_DATES_FILE.exists(), f"Missing file at: {EXAM_DATES_FILE}"
    assert PROGRAMS_FILE.exists(), f"Missing file at: {PROGRAMS_FILE}"

    expected_periods, relevant_course_names, non_exam_course_names = _expected_period_rows()

    result = run_v1_workflow(
        COURSES_FILE,
        EXAM_DATES_FILE,
        PROGRAMS_FILE,
        _output_config(tmp_path),
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
