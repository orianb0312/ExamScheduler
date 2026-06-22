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
