"""QProcess wrapper for running the existing CLI through OS pipes."""

from __future__ import annotations

from src.services.cli_run_service import (
    CliCommandBuilder,
    CliRunConfig,
    V1CliRunAdapter,
)
from src.services.process_resource_logger import ProcessResourceLogger

CANCEL_FORCE_KILL_TIMEOUT_MS = 1500

try:
    from PyQt6.QtCore import QObject, QProcess, QTimer, pyqtSignal

    PYQT_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - exercised only without PyQt6 installed
    PYQT_AVAILABLE = False
    QProcess = None
    QTimer = None

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
    performance_log_created = pyqtSignal(str)

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
        self._process.started.connect(self._handle_started)
        self._process.finished.connect(self._handle_finished)
        self._process.errorOccurred.connect(self._handle_error)
        self._resource_logger: ProcessResourceLogger | None = None
        self._performance_log_path = None
        self._resource_timer = QTimer(self)
        self._resource_timer.setInterval(1000)
        self._resource_timer.timeout.connect(self._sample_resources)

    @property
    def performance_log_path(self):
        """Return the CSV path for the latest scheduler run."""
        return self._performance_log_path

    def start(self, config: CliRunConfig) -> None:
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self.process_error.emit("A CLI process is already running.")
            return

        program, args = self._command_builder.build_command(config)
        self._resource_logger = ProcessResourceLogger(
            config.project_root / "performance_logs",
            project_root=config.project_root,
        )
        self._resource_logger.start(program, args)
        self._performance_log_path = self._resource_logger.path
        self.performance_log_created.emit(str(self._performance_log_path))
        self._process.setWorkingDirectory(str(config.project_root))
        self._process.start(program, args)

    def is_running(self) -> bool:
        return self._process.state() != QProcess.ProcessState.NotRunning

    def cancel(self) -> None:
        if self._process.state() == QProcess.ProcessState.NotRunning:
            return
        process_id = int(self._process.processId())
        if self._resource_logger is not None:
            self._resource_logger.record_event("cancel_requested")
        self._process.terminate()
        QTimer.singleShot(
            CANCEL_FORCE_KILL_TIMEOUT_MS,
            lambda: self._kill_cancelled_process_if_needed(process_id),
        )

    def _kill_cancelled_process_if_needed(self, process_id: int) -> None:
        if self._process.state() == QProcess.ProcessState.NotRunning:
            return
        if int(self._process.processId()) != process_id:
            return
        if self._resource_logger is not None:
            self._resource_logger.record_event(
                "force_kill_after_cancel",
                detail=str(process_id),
            )
        self._process.kill()

    def send_input_line(self, line: str) -> None:
        if self._process.state() == QProcess.ProcessState.NotRunning:
            self.process_error.emit("No CLI process is running.")
            return

        if self._resource_logger is not None:
            self._resource_logger.record_event(
                "stdin_command",
                detail=line,
            )
        self._process.write(f"{line}\n".encode("utf-8"))

    def _handle_started(self) -> None:
        if self._resource_logger is not None:
            self._resource_logger.process_started(int(self._process.processId()))
            self._resource_timer.start()
            self._resource_logger.sample()
        self.process_started.emit()

    def _read_stdout(self) -> None:
        text = bytes(self._process.readAllStandardOutput()).decode(
            "utf-8",
            errors="replace",
        )
        if text:
            if self._resource_logger is not None:
                self._resource_logger.record_output("stdout", text)
            self.stdout_received.emit(text)

    def _read_stderr(self) -> None:
        text = bytes(self._process.readAllStandardError()).decode(
            "utf-8",
            errors="replace",
        )
        if text:
            if self._resource_logger is not None:
                self._resource_logger.record_output("stderr", text)
            self.stderr_received.emit(text)

    def _handle_finished(self, exit_code: int, exit_status) -> None:
        self._resource_timer.stop()
        # A very short process can finish before Qt delivers the last readyRead signal.
        self._read_stdout()
        self._read_stderr()
        status_name = getattr(exit_status, "name", str(exit_status))
        if self._resource_logger is not None:
            self._resource_logger.finish(exit_code, status_name)
            self._resource_logger = None
        self.process_finished.emit(exit_code, status_name)

    def _handle_error(self, error) -> None:
        error_name = getattr(error, "name", str(error))
        if self._resource_logger is not None:
            self._resource_logger.record_event(
                "process_error",
                detail=error_name,
            )
            if self._process.state() == QProcess.ProcessState.NotRunning:
                self._resource_timer.stop()
                self._resource_logger.close()
                self._resource_logger = None
        self.process_error.emit(format_process_error(error_name))

    def _sample_resources(self) -> None:
        if self._resource_logger is not None:
            self._resource_logger.sample()


def format_process_error(error_name: str) -> str:
    messages = {
        "FailedToStart": "Scheduler process could not start. Check the Python path and main.py.",
        "Crashed": "Scheduler process crashed before finishing.",
        "Timedout": "Scheduler process timed out.",
        "WriteError": "Could not send a command to the scheduler process.",
        "ReadError": "Could not read output from the scheduler process.",
        "UnknownError": "Unknown scheduler process error.",
    }
    return messages.get(error_name, f"Scheduler process error: {error_name}")
