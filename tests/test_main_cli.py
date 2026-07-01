import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_SCRIPT = PROJECT_ROOT / "main.py"


def test_cli_reports_bad_input_without_traceback(tmp_path):
    missing_config = tmp_path / "missing_config.json"

    result = subprocess.run(
        [
            sys.executable,
            str(MAIN_SCRIPT),
            "--output-config",
            str(missing_config),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Error:" in result.stderr
    assert str(missing_config) in result.stderr
    assert "Traceback" not in combined_output


def test_cli_reports_invalid_json_without_traceback(tmp_path):
    config_path = tmp_path / "invalid_config.json"
    config_path.write_text("{not-json", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(MAIN_SCRIPT),
            "--output-config",
            str(config_path),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "Error: Invalid JSON configuration" in result.stderr
    assert "Traceback" not in combined_output


def test_cli_modes_still_complete_successfully(tmp_path):
    config_path = _write_minimal_scheduler_input(tmp_path)

    mode_arguments = {
        "period": [],
        "complete-count": [],
        "complete-write": ["--max-systems", "1"],
        "auto": ["--time-limit", "5"],
    }

    for mode, extra_args in mode_arguments.items():
        result = subprocess.run(
            [
                sys.executable,
                str(MAIN_SCRIPT),
                "--mode",
                mode,
                "--output-config",
                str(config_path),
                *extra_args,
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert "Traceback" not in result.stderr


def test_cli_auto_lazy_forwards_time_limit(tmp_path):
    config_path = _write_minimal_scheduler_input(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(MAIN_SCRIPT),
            "--mode",
            "auto",
            "--output-config",
            str(config_path),
            "--time-limit",
            "5",
            "--lazy-schedules",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Auto time limit: 5.00 seconds" in result.stdout
    assert "Complete System #1" in result.stdout
    assert "Traceback" not in result.stderr


def test_cli_complete_write_exports_deterministic_analytics(tmp_path):
    config_path = _write_minimal_scheduler_input(tmp_path)
    sorting_file = tmp_path / "sorting.txt"
    analytics_dir = tmp_path / "analytics"
    sorting_file.write_text("$$$$\nsorting_priority\nmax_daily_exams\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(MAIN_SCRIPT),
            "--mode",
            "complete-write",
            "--max-systems",
            "1",
            "--output-config",
            str(config_path),
            "--sorting-file",
            str(sorting_file),
            "--analytics-format",
            "json,txt,csv",
            "--analytics-output-dir",
            str(analytics_dir),
            "--analytics-base-filename",
            "cli_diagnostics",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Analytics file:" in result.stdout

    json_path = analytics_dir / "cli_diagnostics.json"
    text_path = analytics_dir / "cli_diagnostics.txt"
    csv_path = analytics_dir / "cli_diagnostics.csv"
    assert json_path.exists()
    assert text_path.exists()
    assert csv_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    report = payload["reports"][0]
    assert report["calculation_mode"] == "deterministic_rules"
    assert report["metric_values"][0]["key"] == "max_daily_exams"
    assert report["scheduled_exams"][0]["course_name"] == "Fall Exam"
    assert "Functional justification" in text_path.read_text(encoding="utf-8")
    assert "scheduled_exam" in csv_path.read_text(encoding="utf-8")


def test_cli_rejects_bad_analytics_format_before_scheduling():
    result = subprocess.run(
        [
            sys.executable,
            str(MAIN_SCRIPT),
            "--mode",
            "complete-write",
            "--max-systems",
            "1",
            "--analytics-format",
            "fake",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Unsupported analytics format 'fake'" in result.stderr
    assert "Output file:" not in result.stdout
    assert "Complete systems:" not in result.stdout


def _write_minimal_scheduler_input(tmp_path: Path) -> Path:
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
                "01-01-2026, 02-01-2026",
                "02-01-2026 Blocked",
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
                    "master_filename": "cli_schedule",
                },
            }
        ),
        encoding="utf-8",
    )

    return output_config
