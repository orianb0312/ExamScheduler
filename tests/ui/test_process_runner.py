import sys
from pathlib import Path

import pytest

from src.services.cli_run_service import (
    CliCommandBuilder,
    CliRunConfig,
    build_cli_arguments,
    resolve_cli_output_file,
)
from src.ui.process_runner import ProcessRunner, format_process_error


class _StaticCommandBuilder:
    """Small fake command builder so tests can run tiny local Python commands."""

    def __init__(self, arguments: list[str], program: str | None = None) -> None:
        self._program = program or sys.executable
        self._arguments = arguments

    def build_command(self, _config: CliRunConfig) -> tuple[str, list[str]]:
        return self._program, list(self._arguments)


@pytest.fixture
def process_runner_factory(qtbot):
    runners: list[ProcessRunner] = []

    def create(
        arguments: list[str],
        program: str | None = None,
        command_builder: CliCommandBuilder | None = None,
    ) -> ProcessRunner:
        runner = ProcessRunner(
            command_builder=command_builder or _StaticCommandBuilder(arguments, program)
        )
        runners.append(runner)
        return runner

    yield create

    for runner in runners:
        if runner.is_running():
            runner.cancel()
            qtbot.waitUntil(lambda runner=runner: not runner.is_running(), timeout=3000)


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
        constraints_file=root / "data" / "constraints.txt",
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
    assert "--constraints-file" in args
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


def test_build_cli_arguments_adds_stream_flag_for_streaming_runs():
    root = Path("C:/repo/ExamScheduler")
    config = CliRunConfig(
        project_root=root,
        python_executable="python",
        mode="auto",
        stream_schedules=True,
    )

    _program, args = build_cli_arguments(config)

    assert "--stream-schedules" in args


def test_build_cli_arguments_prefers_lazy_flag_for_lazy_runs():
    root = Path("C:/repo/ExamScheduler")
    config = CliRunConfig(
        project_root=root,
        python_executable="python",
        mode="auto",
        stream_schedules=True,
        lazy_schedules=True,
    )

    _program, args = build_cli_arguments(config)

    assert "--lazy-schedules" in args
    assert "--stream-schedules" not in args


def test_build_cli_arguments_rejects_unknown_modes():
    with pytest.raises(ValueError):
        build_cli_arguments(CliRunConfig(project_root=Path("."), mode="server"))


def test_process_error_messages_are_readable():
    assert "could not start" in format_process_error("FailedToStart")
    assert format_process_error("SomeNewError") == "Scheduler process error: SomeNewError"


def test_resolve_cli_output_file_uses_output_settings(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        """
{
  "output_settings": {
    "base_directory": "custom_outputs",
    "master_filename": "faculty_schedule"
  }
}
""",
        encoding="utf-8",
    )

    output_path = resolve_cli_output_file(
        CliRunConfig(project_root=tmp_path, output_config=config_path)
    )

    assert output_path == tmp_path / "custom_outputs" / "faculty_schedule.txt"


def test_process_runner_starts_external_process_without_blocking_ui(
    tmp_path,
    qtbot,
    process_runner_factory,
):
    runner = process_runner_factory([
        "-c",
        "import time; time.sleep(2)",
    ])

    with qtbot.waitSignal(runner.process_started, timeout=1000):
        runner.start(CliRunConfig(project_root=tmp_path))

    assert runner.is_running()

    runner.cancel()
    qtbot.waitUntil(lambda: not runner.is_running(), timeout=3000)


def test_process_runner_captures_stdout_result(
    tmp_path,
    qtbot,
    process_runner_factory,
):
    output_chunks: list[str] = []
    runner = process_runner_factory(["-c", "print('SUCCESS')"])
    runner.stdout_received.connect(output_chunks.append)

    with qtbot.waitSignal(runner.process_finished, timeout=3000) as blocker:
        runner.start(CliRunConfig(project_root=tmp_path))

    exit_code, _status = blocker.args
    assert exit_code == 0
    assert "SUCCESS" in "".join(output_chunks)


def test_process_runner_creates_performance_log_for_each_run(
    tmp_path,
    qtbot,
    process_runner_factory,
):
    created_paths: list[str] = []
    runner = process_runner_factory(["-c", "print('Complete System #1')"])
    runner.performance_log_created.connect(created_paths.append)

    with qtbot.waitSignal(runner.process_finished, timeout=3000):
        runner.start(CliRunConfig(project_root=tmp_path))

    assert created_paths == [str(runner.performance_log_path)]
    assert runner.performance_log_path.exists()
    log_text = runner.performance_log_path.read_text(encoding="utf-8")
    assert "child_rss_mb" in log_text
    assert "first_result" in log_text
    assert "process_finished" in log_text


def test_process_runner_emits_progress_when_stdout_is_written(
    tmp_path,
    qtbot,
    process_runner_factory,
):
    runner = process_runner_factory([
        "-c",
        "import sys; print('Calculating...'); sys.stdout.flush()",
    ])

    with qtbot.waitSignal(runner.stdout_received, timeout=3000) as blocker:
        runner.start(CliRunConfig(project_root=tmp_path))

    assert "Calculating..." in blocker.args[0]
    qtbot.waitUntil(lambda: not runner.is_running(), timeout=3000)


def test_process_runner_reports_missing_executable(
    tmp_path,
    qtbot,
    process_runner_factory,
):
    runner = process_runner_factory([], program="fake_non_existent_program.exe")

    with qtbot.waitSignal(runner.process_error, timeout=2000) as blocker:
        runner.start(CliRunConfig(project_root=tmp_path))

    assert "could not start" in blocker.args[0]


def test_process_runner_reports_non_zero_exit_code_and_keeps_output(
    tmp_path,
    qtbot,
    process_runner_factory,
):
    output_chunks: list[str] = []
    runner = process_runner_factory([
        "-c",
        "import sys; print('Crash logs'); sys.exit(42)",
    ])
    runner.stdout_received.connect(output_chunks.append)

    with qtbot.waitSignal(runner.process_finished, timeout=3000) as blocker:
        runner.start(CliRunConfig(project_root=tmp_path))

    exit_code, _status = blocker.args
    assert exit_code == 42
    assert "Crash logs" in "".join(output_chunks)
