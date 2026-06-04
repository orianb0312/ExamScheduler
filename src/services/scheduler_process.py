from PyQt6.QtCore import QObject, QProcess, pyqtSignal


class SchedulerProcess(QObject):
    """
    Manages the execution of the heavy scheduling algorithm in a separate OS process.
    Ensures the main PyQt6 UI thread remains fully responsive.
    Strictly standalone and local (No client-server/HTTP).
    """

    # Custom signals to communicate cleanly with the UI without blocking it
    process_started = pyqtSignal()
    progress_updated = pyqtSignal(str)  # Emits real-time logs or standard output
    process_finished = pyqtSignal(int, str)  # Emits the exit code and the complete final output
    error_occurred = pyqtSignal(str)  # Emits crash or OS-level error details

    def __init__(self, parent=None):
        super().__init__(parent)

        # Passing 'parent' links the process to the UI lifecycle to prevent zombie processes
        self.process = QProcess(self)

        # Buffer to accumulate output during the process run, resolving the empty buffer issue
        self._output_buffer = []

        # Connect QProcess native signals to our custom internal handler methods
        self.process.started.connect(self._on_started)
        self.process.readyReadStandardOutput.connect(self._on_stdout_ready)
        self.process.readyReadStandardError.connect(self._on_stderr_ready)
        self.process.finished.connect(self._on_finished)
        self.process.errorOccurred.connect(self._on_error)

    def run_algorithm(self, executable: str, arguments: list):
        """
        Starts the external scheduling logic asynchronously.
        This function returns immediately, preventing GUI freezes.
        """
        # Clear the buffer from any previous runs before starting a new process
        self._output_buffer.clear()
        self.process.start(executable, arguments)

    def stop(self):
        """Allows the UI to safely cancel the long-running task."""
        if self.process.state() == QProcess.ProcessState.Running:
            self.process.kill()

    # --- Internal Event Handlers ---

    def _on_started(self):
        """Triggered when the OS successfully launches the executable."""
        self.process_started.emit()

    def _on_stdout_ready(self):
        """Reads real-time standard output from the process and caches it."""
        data = self.process.readAllStandardOutput().data().decode('utf-8', errors='ignore').strip()
        if data:
            self._output_buffer.append(data)  # Accumulate data to avoid losing it after reading
            self.progress_updated.emit(data)

    def _on_stderr_ready(self):
        """Captures and emits standard error output or warnings."""
        data = self.process.readAllStandardError().data().decode('utf-8', errors='ignore').strip()
        if data:
            self.progress_updated.emit(f"WARN/ERR: {data}")

    def _on_finished(self, exit_code, exit_status):
        """Fired when the process exits. Compiles the buffer and emits the final result."""
        # Read any lingering data that might not have triggered the readyRead signal
        lingering_data = self.process.readAllStandardOutput().data().decode('utf-8', errors='ignore').strip()
        if lingering_data:
            self._output_buffer.append(lingering_data)

        # Combine all gathered output lines into a single string
        final_output = "\n".join(self._output_buffer)
        self.process_finished.emit(exit_code, final_output)

    def _on_error(self, error):
        """Catches OS-level process errors (e.g., missing executable file)."""
        self.error_occurred.emit(self.process.errorString())