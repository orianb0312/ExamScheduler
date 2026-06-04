from pathlib import Path

import pytest

from src.services.cli_run_service import CliRunConfig, build_cli_arguments


def test_build_cli_arguments_constructs_unbuffered_main_command():
    root = Path("C:/repo/ExamScheduler")
    config = CliRunConfig(
        project_root=root,
        python_executable="python",
        mode="complete-write",
        output_config=root / "config.json",
        period_indexes=(0, 2),
        max_systems=1000,
        course_file=root / "data" / "courses.txt",
        dates_file=root / "data" / "dates.txt",
        user_file=root / "data" / "programs.txt",
    )

    program, args = build_cli_arguments(config)

    assert program == "python"
    assert args[:5] == [
        "-u",
        str(root / "main.py"),
        "--mode",
        "complete-write",
        "--output-config",
    ]
    assert str(root / "config.json") in args
    assert args.count("--period-index") == 2
    assert "--max-systems" in args
    assert "1000" in args
    assert "--course-file" in args
    assert "--dates-file" in args
    assert "--user-file" in args


def test_build_cli_arguments_adds_auto_time_limit_only_for_auto_mode():
    root = Path("C:/repo/ExamScheduler")
    config = CliRunConfig(
        project_root=root,
        python_executable="python",
        mode="auto",
        time_limit_seconds=45.0,
    )

    _program, args = build_cli_arguments(config)

    assert "--time-limit" in args
    assert "45.0" in args


def test_build_cli_arguments_rejects_unknown_modes():
    with pytest.raises(ValueError):
        build_cli_arguments(CliRunConfig(project_root=Path("."), mode="server"))
