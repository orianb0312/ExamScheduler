import json
from io import StringIO
from pathlib import Path

import src.workflow as workflow_module
import pytest

from src.workflow import (
    load_domain_data,
    run_complete_auto_stream_workflow,
    run_complete_lazy_stream_workflow,
    run_complete_count_workflow,
    run_v1_workflow,
)


class _StaticJsonParser:
    def __init__(self, payload):
        self._payload = payload

    def parse_to_json(self, _source_config):
        return json.dumps(self._payload)


def test_load_domain_data_deserializes_parser_output_once(monkeypatch):
    payload = {
        "courses_node": [
            {
                "name": "Fall Exam",
                "number": "10001",
                "instructor": "Dr. Fall",
                "programs": [
                    {
                        "number": "83101",
                        "year": "1",
                        "semester": "FALL",
                        "requirement": "Obligatory",
                    }
                ],
                "evaluation": "Exam",
            }
        ],
        "periods_node": [
            {
                "semester": "FALL",
                "moed": "Aleph",
                "start_date": "01-01-2026",
                "end_date": "02-01-2026",
                "exclusions": [
                    {
                        "start_date": "02-01-2026",
                        "end_date": None,
                        "comment": "Blocked",
                    }
                ],
            }
        ],
        "user_node": ["83101"],
    }
    real_json_loads = workflow_module.json.loads
    json_load_calls = []

    def count_json_loads(*args, **kwargs):
        json_load_calls.append(args[0])
        return real_json_loads(*args, **kwargs)

    monkeypatch.setattr(workflow_module.json, "loads", count_json_loads)

    courses, periods, selected_programs = load_domain_data(
        source_config={},
        parser=_StaticJsonParser(payload),
    )

    assert len(json_load_calls) == 1
    assert courses[0].name == "Fall Exam"
    assert periods[0].semester.value == "FALL"
    assert selected_programs == [83101]


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


def test_run_v1_workflow_injects_persisted_ai_rule_from_absolute_path(
    tmp_path,
):
    course_file = tmp_path / "courses.txt"
    dates_file = tmp_path / "dates.txt"
    user_file = tmp_path / "programs.txt"
    output_config = tmp_path / "config.json"
    ai_rules_file = (tmp_path / "data" / "active_ai_rules.json").resolve()
    ai_rules_file.parent.mkdir(parents=True)

    course_file.write_text(
        "\n".join(
            [
                "$$$$",
                "Algorithms",
                "10001",
                "Dr. Ada",
                "83101,1,FALL,Obligatory",
                "Exam",
            ]
        ),
        encoding="utf-8",
    )
    dates_file.write_text(
        "\n".join(
            [
                "$$$$",
                "FALL,Aleph",
                "01-01-2026, 03-01-2026",
            ]
        ),
        encoding="utf-8",
    )
    user_file.write_text("83101", encoding="utf-8")
    ai_rules_file.write_text(
        json.dumps(
            [
                {
                    "rule_id": "ai_rule_1",
                    "description": "Fix Algorithms on 2026-01-02",
                    "rule_type": "fix_date",
                    "parameters": {
                        "course": "Algorithms",
                        "date": "2026-01-02",
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
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
                    "base_directory": str(tmp_path / "output"),
                    "master_filename": "ai_rule_schedule",
                },
            }
        ),
        encoding="utf-8",
    )

    result = run_v1_workflow(
        output_config=output_config,
        course_file=course_file,
        dates_file=dates_file,
        user_file=user_file,
        ai_rules_file=ai_rules_file,
    )

    assert result.total_schedules == 1
    assert "Algorithms | 2026-01-02" in result.output_path.read_text(
        encoding="utf-8"
    )


def test_run_complete_auto_stream_workflow_writes_schedule_blocks_to_stdout(tmp_path):
    course_file = tmp_path / "courses.txt"
    dates_file = tmp_path / "dates.txt"
    user_file = tmp_path / "programs.txt"
    output_config = tmp_path / "config.json"

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
                    "base_directory": str(tmp_path / "output"),
                    "master_filename": "workflow_schedule",
                },
            }
        ),
        encoding="utf-8",
    )

    stdout = StringIO()
    stderr = StringIO()
    result = run_complete_auto_stream_workflow(
        output_config=output_config,
        time_limit_seconds=30.0,
        batch_size=1,
        output_stream=stdout,
        progress_stream=stderr,
        course_file=course_file,
        dates_file=dates_file,
        user_file=user_file,
    )

    output = stdout.getvalue()

    assert result.complete_system_count == 1
    assert result.written_system_count == 1
    assert "Complete System #1" in output
    assert "Fall Exam | 2026-01-01 | Dr. Fall" in output
    assert "Spring Exam | 2026-01-03 | Dr. Spring" in output


def test_run_complete_lazy_stream_workflow_waits_for_next_command(tmp_path):
    course_file = tmp_path / "courses.txt"
    dates_file = tmp_path / "dates.txt"
    user_file = tmp_path / "programs.txt"
    output_config = tmp_path / "config.json"

    course_file.write_text(
        "\n".join(
            [
                "$$$$",
                "Fall Exam",
                "10001",
                "Dr. Fall",
                "83101,1,FALL,Obligatory",
                "Exam",
            ]
        ),
        encoding="utf-8",
    )
    dates_file.write_text(
        "\n".join(
            [
                "$$$$",
                "FALL,Aleph",
                "01-01-2026, 03-01-2026",
                "03-01-2026 Blocked",
            ]
        ),
        encoding="utf-8",
    )
    user_file.write_text("83101", encoding="utf-8")
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
                    "base_directory": str(tmp_path / "output"),
                    "master_filename": "workflow_schedule",
                },
            }
        ),
        encoding="utf-8",
    )

    first_page_stdout = StringIO()
    first_page_result = run_complete_lazy_stream_workflow(
        output_config=output_config,
        batch_size=1,
        input_stream=StringIO(""),
        output_stream=first_page_stdout,
        progress_stream=StringIO(),
        course_file=course_file,
        dates_file=dates_file,
        user_file=user_file,
    )

    assert first_page_result.written_system_count == 1
    assert "Complete System #1" in first_page_stdout.getvalue()
    assert "Complete System #2" not in first_page_stdout.getvalue()

    second_page_stdout = StringIO()
    second_page_result = run_complete_lazy_stream_workflow(
        output_config=output_config,
        batch_size=1,
        input_stream=StringIO("NEXT\n"),
        output_stream=second_page_stdout,
        progress_stream=StringIO(),
        course_file=course_file,
        dates_file=dates_file,
        user_file=user_file,
    )

    assert second_page_result.written_system_count == 2
    assert "Complete System #1" in second_page_stdout.getvalue()
    assert "Complete System #2" in second_page_stdout.getvalue()

    auto_stdout = StringIO()
    auto_stderr = StringIO()
    auto_result = run_complete_lazy_stream_workflow(
        output_config=output_config,
        batch_size=1,
        time_limit_seconds=30.0,
        input_stream=StringIO(""),
        output_stream=auto_stdout,
        progress_stream=auto_stderr,
        course_file=course_file,
        dates_file=dates_file,
        user_file=user_file,
    )
    auto_output = auto_stdout.getvalue()

    assert auto_result.auto_limit_seconds == 30.0
    assert auto_result.written_system_count == 1
    assert auto_result.truncated is True
    assert "Auto time limit: 30.00 seconds" in auto_output
    assert "Complete System #1" in auto_output
    assert "Complete System #2" not in auto_output
    assert "before all batches were requested" in auto_stderr.getvalue()

    auto_next_stdout = StringIO()
    auto_next_result = run_complete_lazy_stream_workflow(
        output_config=output_config,
        batch_size=1,
        time_limit_seconds=30.0,
        input_stream=StringIO("NEXT\n"),
        output_stream=auto_next_stdout,
        progress_stream=StringIO(),
        course_file=course_file,
        dates_file=dates_file,
        user_file=user_file,
    )
    auto_next_output = auto_next_stdout.getvalue()

    assert auto_next_result.auto_limit_seconds == 30.0
    assert auto_next_result.written_system_count == 2
    assert "Complete System #1" in auto_next_output
    assert "Complete System #2" in auto_next_output


def test_time_limited_lazy_stream_honors_sorting_file(tmp_path):
    course_file = tmp_path / "courses.txt"
    dates_file = tmp_path / "dates.txt"
    user_file = tmp_path / "programs.txt"
    sorting_file = tmp_path / "sorting.txt"
    output_config = tmp_path / "config.json"

    course_file.write_text(
        "\n".join(
            [
                "$$$$",
                "Alpha",
                "10001",
                "Dr. A",
                "83101,1,FALL,Obligatory",
                "Exam",
                "$$$$",
                "Beta",
                "10002",
                "Dr. B",
                "83101,1,FALL,Obligatory",
                "Exam",
            ]
        ),
        encoding="utf-8",
    )
    dates_file.write_text(
        "\n".join(
            [
                "$$$$",
                "FALL,Aleph",
                "01-01-2026, 04-01-2026",
                "04-01-2026 Blocked",
            ]
        ),
        encoding="utf-8",
    )
    user_file.write_text("83101", encoding="utf-8")
    sorting_file.write_text("$$$$\nsorting_priority\n3.1\n", encoding="utf-8")
    output_config.write_text(
        json.dumps(
            {
                "source_type": "file",
                "file": {
                    "course_file": str(course_file),
                    "dates_file": str(dates_file),
                    "user_file": str(user_file),
                    "sorting_file": str(sorting_file),
                },
                "output_settings": {
                    "base_directory": str(tmp_path / "output"),
                    "master_filename": "workflow_schedule",
                },
            }
        ),
        encoding="utf-8",
    )

    stdout = StringIO()
    result = run_complete_lazy_stream_workflow(
        output_config=output_config,
        batch_size=1,
        time_limit_seconds=30.0,
        input_stream=StringIO(""),
        output_stream=stdout,
        progress_stream=StringIO(),
        course_file=course_file,
        dates_file=dates_file,
        user_file=user_file,
        sorting_file=sorting_file,
    )

    first_system = stdout.getvalue().split("Complete System #1", 1)[1].split(
        "*" * 70,
        1,
    )[0]

    assert result.complete_system_count == 6
    assert result.written_system_count == 1
    assert "2026-01-01" in first_system
    assert "2026-01-03" in first_system
    assert "2026-01-02" not in first_system


def test_workflow_rejects_invalid_constraints_file_override(tmp_path):
    course_file = tmp_path / "courses.txt"
    dates_file = tmp_path / "dates.txt"
    user_file = tmp_path / "programs.txt"
    constraints_file = tmp_path / "constraints.txt"
    output_config = tmp_path / "config.json"

    course_file.write_text(
        "\n".join(
            [
                "$$$$",
                "Fall Exam",
                "10001",
                "Dr. Fall",
                "83101,1,FALL,Obligatory",
                "Exam",
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
            ]
        ),
        encoding="utf-8",
    )
    user_file.write_text("83101", encoding="utf-8")
    constraints_file.write_text(
        "\n".join(
            [
                "$$$$",
                "min_days_between_mandatory",
                "-",
                "$$$$",
                "min_days_between_any",
                "-",
                "$$$$",
                "max_elective_conflicts",
                "0",
                "$$$$",
                "min_days_before_last_mandatory",
                "-",
                "$$$$",
                "max_exams_per_day",
                "0",
            ]
        ),
        encoding="utf-8",
    )
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
                    "base_directory": str(tmp_path / "output"),
                    "master_filename": "workflow_schedule",
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="max_exams_per_day"):
        run_complete_count_workflow(
            output_config=output_config,
            course_file=course_file,
            dates_file=dates_file,
            user_file=user_file,
            constraints_file=constraints_file,
        )


def test_run_v1_workflow_applies_spacing_constraints_from_constraints_file(tmp_path):
    course_file = tmp_path / "courses.txt"
    dates_file = tmp_path / "dates.txt"
    user_file = tmp_path / "programs.txt"
    constraints_file = tmp_path / "constraints.txt"
    output_config = tmp_path / "config.json"

    course_file.write_text(
        "\n".join(
            [
                "$$$$",
                "Math",
                "10001",
                "Dr. Math",
                "83101,1,FALL,Obligatory",
                "Exam",
                "$$$$",
                "Physics",
                "10002",
                "Dr. Physics",
                "83101,1,FALL,Obligatory",
                "Exam",
            ]
        ),
        encoding="utf-8",
    )
    dates_file.write_text(
        "\n".join(
            [
                "$$$$",
                "FALL,Aleph",
                "01-01-2026, 06-01-2026",
                "06-01-2026 Blocked",
            ]
        ),
        encoding="utf-8",
    )
    user_file.write_text("83101", encoding="utf-8")
    constraints_file.write_text(
        "\n".join(
            [
                "$$$$",
                "min_days_between_mandatory",
                "3",
                "$$$$",
                "min_days_between_any",
                "1",
                "$$$$",
                "max_elective_conflicts",
                "-",
                "$$$$",
                "min_days_before_last_mandatory",
                "-",
                "$$$$",
                "max_exams_per_day",
                "-",
            ]
        ),
        encoding="utf-8",
    )
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
                    "base_directory": str(tmp_path / "output"),
                    "master_filename": "workflow_schedule",
                },
            }
        ),
        encoding="utf-8",
    )

    result = run_v1_workflow(
        output_config=output_config,
        course_file=course_file,
        dates_file=dates_file,
        user_file=user_file,
        constraints_file=constraints_file,
    )

    assert result.total_schedules == 6
    assert result.periods[0].schedule_count == 6


def test_run_v1_workflow_orders_text_output_from_sorting_file(tmp_path):
    course_file = tmp_path / "courses.txt"
    dates_file = tmp_path / "dates.txt"
    user_file = tmp_path / "programs.txt"
    sorting_file = tmp_path / "sorting.txt"
    output_config = tmp_path / "config.json"

    course_file.write_text(
        "\n".join(
            [
                "$$$$",
                "Math",
                "10001",
                "Dr. Math",
                "83101,1,FALL,Obligatory",
                "Exam",
                "$$$$",
                "Physics",
                "10002",
                "Dr. Physics",
                "83101,1,FALL,Obligatory",
                "Exam",
            ]
        ),
        encoding="utf-8",
    )
    dates_file.write_text(
        "\n".join(
            [
                "$$$$",
                "FALL,Aleph",
                "01-01-2026, 05-01-2026",
                "05-01-2026 Blocked",
            ]
        ),
        encoding="utf-8",
    )
    user_file.write_text("83101", encoding="utf-8")
    sorting_file.write_text(
        "$$$$\nsorting_priority\nmandatory_min_gap\n",
        encoding="utf-8",
    )
    output_config.write_text(
        json.dumps(
            {
                "source_type": "file",
                "file": {
                    "course_file": str(course_file),
                    "dates_file": str(dates_file),
                    "user_file": str(user_file),
                    "sorting_file": str(sorting_file),
                },
                "output_settings": {
                    "base_directory": str(tmp_path / "output"),
                    "master_filename": "workflow_schedule",
                },
            }
        ),
        encoding="utf-8",
    )

    result = run_v1_workflow(
        output_config=output_config,
        course_file=course_file,
        dates_file=dates_file,
        user_file=user_file,
    )

    first_schedule = result.output_path.read_text(encoding="utf-8").split("Schedule #2")[0]

    assert result.total_schedules == 12
    assert "2026-01-01" in first_schedule
    assert "2026-01-04" in first_schedule


def test_complete_count_workflow_applies_global_constraints_from_constraints_file(tmp_path):
    course_file = tmp_path / "courses.txt"
    dates_file = tmp_path / "dates.txt"
    user_file = tmp_path / "programs.txt"
    constraints_file = tmp_path / "constraints.txt"
    output_config = tmp_path / "config.json"

    course_file.write_text(
        "\n".join(
            [
                "$$$$",
                "Program A",
                "10001",
                "Dr. A",
                "83101,1,FALL,Obligatory",
                "Exam",
                "$$$$",
                "Program B",
                "10002",
                "Dr. B",
                "83102,1,FALL,Obligatory",
                "Exam",
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
            ]
        ),
        encoding="utf-8",
    )
    user_file.write_text("83101, 83102", encoding="utf-8")
    constraints_file.write_text(
        "\n".join(
            [
                "$$$$",
                "min_days_between_mandatory",
                "-",
                "$$$$",
                "min_days_between_any",
                "-",
                "$$$$",
                "max_elective_conflicts",
                "-",
                "$$$$",
                "min_days_before_last_mandatory",
                "-",
                "$$$$",
                "max_exams_per_day",
                "1",
            ]
        ),
        encoding="utf-8",
    )
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
                    "base_directory": str(tmp_path / "output"),
                    "master_filename": "workflow_schedule",
                },
            }
        ),
        encoding="utf-8",
    )

    result = run_complete_count_workflow(
        output_config=output_config,
        course_file=course_file,
        dates_file=dates_file,
        user_file=user_file,
        constraints_file=constraints_file,
    )

    assert result.period_course_counts == [2]
    assert result.period_schedule_counts == [0]
    assert result.complete_system_count == 0
