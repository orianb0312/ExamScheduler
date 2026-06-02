"""QProcess wrapper for running the existing CLI through OS pipes."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

try:
    from PyQt6.QtCore import QObject, QProcess, pyqtSignal

    PYQT_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - exercised only without PyQt6 installed
    PYQT_AVAILABLE = False
    QProcess = None

    class QObject:  # type: ignore[no-redef]
        pass

    class _UnavailableSignal:
        def connect(self, *_args, **_kwargs) -> None:
            return None

        def emit(self, *_args, **_kwargs) -> None:
            return None

    def pyqtSignal(*_args, **_kwargs):  # type: ignore[no-redef]
        return _UnavailableSignal()


VALID_CLI_MODES = {"period", "complete-count", "complete-write", "auto"}


@dataclass(frozen=True)
class CliRunConfig:
    """UI-local description of a CLI run request."""

    project_root: Path
    mode: str = "complete-count"
    python_executable: str = field(default_factory=lambda: sys.executable)
    output_config: Path | None = None
    source_type: str | None = None
    period_indexes: Sequence[int] = ()
    max_systems: int | None = None
    time_limit_seconds: float | None = None
    course_file: Path | None = None
    dates_file: Path | None = None
    user_file: Path | None = None


def build_cli_arguments(config: CliRunConfig) -> tuple[str, list[str]]:
    """Build the external command used by QProcess."""
    if config.mode not in VALID_CLI_MODES:
        raise ValueError(f"Unsupported CLI mode: {config.mode}")

    main_script = config.project_root / "main.py"
    output_config = config.output_config or config.project_root / "config.json"
    program = config.python_executable or sys.executable

    args = [
        "-u",
        str(main_script),
        "--mode",
        config.mode,
        "--output-config",
        str(output_config),
    ]

    if config.source_type:
        args.extend(["--source-type", config.source_type])

    for period_index in config.period_indexes:
        args.extend(["--period-index", str(period_index)])

    if config.mode == "complete-write" and config.max_systems is not None:
        args.extend(["--max-systems", str(config.max_systems)])

    if config.mode == "auto" and config.time_limit_seconds is not None:
        args.extend(["--time-limit", str(config.time_limit_seconds)])

    if config.course_file is not None:
        args.extend(["--course-file", str(config.course_file)])
    if config.dates_file is not None:
        args.extend(["--dates-file", str(config.dates_file)])
    if config.user_file is not None:
        args.extend(["--user-file", str(config.user_file)])

    return program, args


class ProcessRunner(QObject):
    """Run main.py externally and expose stdout/stderr through Qt signals."""

    stdout_received = pyqtSignal(str)
    stderr_received = pyqtSignal(str)
    process_started = pyqtSignal()
    process_finished = pyqtSignal(int, str)
    process_error = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        if not PYQT_AVAILABLE:
            raise RuntimeError("PyQt6 is required to run ProcessRunner")

        super().__init__(parent)
        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(self._read_stdout)
        self._process.readyReadStandardError.connect(self._read_stderr)
        self._process.started.connect(self.process_started.emit)
        self._process.finished.connect(self._handle_finished)
        self._process.errorOccurred.connect(self._handle_error)

    def start(self, config: CliRunConfig) -> None:
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self.process_error.emit("A CLI process is already running.")
            return

        program, args = build_cli_arguments(config)
        self._process.setWorkingDirectory(str(config.project_root))
        self._process.start(program, args)

    def cancel(self) -> None:
        if self._process.state() == QProcess.ProcessState.NotRunning:
            return
        self._process.terminate()

    def _read_stdout(self) -> None:
        text = bytes(self._process.readAllStandardOutput()).decode(
            "utf-8",
            errors="replace",
        )
        if text:
            self.stdout_received.emit(text)

    def _read_stderr(self) -> None:
        text = bytes(self._process.readAllStandardError()).decode(
            "utf-8",
            errors="replace",
        )
        if text:
            self.stderr_received.emit(text)

    def _handle_finished(self, exit_code: int, exit_status) -> None:
        status_name = getattr(exit_status, "name", str(exit_status))
        self.process_finished.emit(exit_code, status_name)

    def _handle_error(self, error) -> None:
        error_name = getattr(error, "name", str(error))
        self.process_error.emit(error_name)
