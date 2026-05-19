import json
from pathlib import Path

from src.workflow import run_v1_workflow


def test_run_v1_workflow_processes_all_exam_periods(tmp_path):
    course_file = tmp_path / "courses.txt"
    dates_file = tmp_path / "dates.txt"
    user_file = tmp_path / "programs.txt"
    output_config = tmp_path / "config.json"
    output_dir = tmp_path / "output"

    course_file.write_text(
        "\n".join(
            [
                "$$$$",
                "Fall Exam",
                "10001",
                "Dr. Fall",
                "83101,1,FALL,Obligatory",
                "Exam",
                "$$$$",
                "Spring Exam",
                "10002",
                "Dr. Spring",
                "83101,1,SPRI,Obligatory",
                "Exam",
                "$$$$",
                "Fall Project",
                "10003",
                "Dr. Project",
                "83101,1,FALL,Obligatory",
                "Project",
            ]
        ),
        encoding="utf-8",
    )
    dates_file.write_text(
        "\n".join(
            [
                "$$$$",
                "FALL,Aleph",
                "01-01-2026, 02-01-2026",
                "02-01-2026 Blocked",
                "$$$$",
                "SPRI,Aleph",
                "03-01-2026, 04-01-2026",
                "04-01-2026 Blocked",
            ]
        ),
        encoding="utf-8",
    )
    user_file.write_text("83101", encoding="utf-8")

    # Updated config file structure to include source files under the 'file' configuration block
    output_config.write_text(
        json.dumps(
            {
                "source_type": "file",
                "file": {
                    "course_file": str(course_file),
                    "dates_file": str(dates_file),
                    "user_file": str(user_file),
                },
                "output_settings": {
                    "base_directory": str(output_dir),
                    "master_filename": "workflow_schedule",
                }
            }
        ),
        encoding="utf-8",
    )

    # Call using explicit keyword argument structure to line up with the modern signature
    result = run_v1_workflow(
        output_config=output_config,
        course_file=course_file,
        dates_file=dates_file,
        user_file=user_file,
    )

    assert result.total_schedules == 2
    assert [(period.semester, period.term, period.course_count) for period in result.periods] == [
        ("FALL", "Aleph", 1),
        ("SPRI", "Aleph", 1),
    ]

    content = result.output_path.read_text(encoding="utf-8")
    assert "Fall Exam | 2026-01-01 | Dr. Fall" in content
    assert "Spring Exam | 2026-01-03 | Dr. Spring" in content
    assert "Fall Project" not in content