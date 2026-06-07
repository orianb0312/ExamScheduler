"""QProcess wrapper for running the existing CLI through OS pipes."""

from __future__ import annotations

from src.services.cli_run_service import (
    CliCommandBuilder,
    CliRunConfig,
    V1CliRunAdapter,
    build_cli_arguments,
)

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


class ProcessRunner(QObject):
    """Run main.py externally and expose stdout/stderr through Qt signals."""

    stdout_received = pyqtSignal(str)
    stderr_received = pyqtSignal(str)
    process_started = pyqtSignal()
    process_finished = pyqtSignal(int, str)
    process_error = pyqtSignal(str)

    def __init__(
        self,
        parent=None,
        command_builder: CliCommandBuilder | None = None,
    ) -> None:
        if not PYQT_AVAILABLE:
            raise RuntimeError("PyQt6 is required to run ProcessRunner")

        super().__init__(parent)
        self._command_builder = command_builder or V1CliRunAdapter()
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

        program, args = self._command_builder.build_command(config)
        self._process.setWorkingDirectory(str(config.project_root))
        self._process.start(program, args)

    def is_running(self) -> bool:
        return self._process.state() != QProcess.ProcessState.NotRunning

    def cancel(self) -> None:
        if self._process.state() == QProcess.ProcessState.NotRunning:
            return
        self._process.terminate()

    def send_input_line(self, line: str) -> None:
        if self._process.state() == QProcess.ProcessState.NotRunning:
            self.process_error.emit("No CLI process is running.")
            return

        self._process.write(f"{line}\n".encode("utf-8"))

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
