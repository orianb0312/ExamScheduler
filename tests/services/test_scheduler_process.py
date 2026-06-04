import pytest
from PyQt6.QtCore import QProcess
from src.services.scheduler_process import SchedulerProcess


@pytest.fixture
def runner():
    """
    Fixture providing a fresh, isolated SchedulerProcess instance for each test.
    """
    return SchedulerProcess()


def test_process_starts_and_emits_started_signal(qtbot, runner):
    """
    Acceptance Criteria: QProcess is used to run separated processing.
    Verifies that calling run_algorithm() starts the OS process and emits the correct signal.
    """
    # Wait for the custom 'process_started' signal to ensure the executable actually launched
    with qtbot.waitSignal(runner.process_started, timeout=1000):
        # Use a simple cross-platform python command to mock the external solver executable
        runner.run_algorithm("python", ["--version"])

    # Assert the process entered the correct state (Running, or NotRunning if it finished instantly)
    assert runner.process.state() in (QProcess.ProcessState.Running, QProcess.ProcessState.NotRunning)


def test_process_emits_finished_with_results(qtbot, runner):
    """
    Acceptance Criteria: The process result is passed back to the UI in a controlled way.
    Verifies that when the logic finishes, it captures the output buffer and emits it back.
    """
    # Block test execution until the 'process_finished' signal is emitted, or timeout after 3 seconds
    with qtbot.waitSignal(runner.process_finished, timeout=3000) as blocker:
        # Simulate a process that successfully prints "SUCCESS" and exits with code 0
        runner.run_algorithm("python", ["-c", "print('SUCCESS')"])

    # Extract the arguments passed by the signal (exit_code, final_output)
    exit_code, output = blocker.args

    # Assert the execution completed normally and the output buffer caught the text
    assert exit_code == 0
    assert "SUCCESS" in output


def test_process_emits_progress_when_stdout_is_written(qtbot, runner):
    """
    Acceptance Criteria: The UI remains responsive while processing is running.
    Verifies we can receive real-time standard output from the running background logic.
    """
    # Wait specifically for the intermediate progress signal, not the finished signal
    with qtbot.waitSignal(runner.progress_updated, timeout=3000) as blocker:
        # Execute a python command that prints a progress string and flushes the stdout buffer
        runner.run_algorithm("python", ["-c", "import sys; print('Calculating...'); sys.stdout.flush()"])

    # Extract the first argument of the emitted signal to verify the real-time payload
    output_line = blocker.args[0]
    assert "Calculating..." in output_line


# --- EDGE CASES ---

def test_process_emits_error_when_executable_not_found(qtbot, runner):
    """
    Edge Case: The algorithm executable is missing, deleted, or blocked by antivirus.
    Verifies that the error_occurred signal is emitted gracefully so the UI doesn't hang.
    """
    with qtbot.waitSignal(runner.error_occurred, timeout=2000) as blocker:
        runner.run_algorithm("fake_non_existent_program.exe", [])

    # Ensure the error string contains data provided by the OS
    error_message = blocker.args[0]
    assert error_message != ""


def test_process_handles_crash_and_non_zero_exit_codes(qtbot, runner):
    """
    Edge Case: The algorithm crashes mid-calculation (e.g., division by zero or out of memory).
    Verifies that a non-zero exit code and error logs are passed to the UI correctly.
    """
    with qtbot.waitSignal(runner.process_finished, timeout=3000) as blocker:
        # Simulate a crash using sys.exit(42) alongside some printed logs
        runner.run_algorithm("python", ["-c", "import sys; print('Crash logs'); sys.exit(42)"])

    exit_code, output = blocker.args

    # Assert the UI receives the exact failure code and whatever was logged before the crash
    assert exit_code == 42
    assert "Crash logs" in output


def test_process_can_be_cancelled_by_user(qtbot, runner):
    """
    Edge Case: The user clicks 'Cancel' during a long-running calculation.
    Verifies that calling stop() successfully kills the underlying OS process.
    """
    # 1. Listen for the start signal, THEN run the algorithm inside the block
    with qtbot.waitSignal(runner.process_started, timeout=1000):
        # Start a long-running mock process (sleep for 10 seconds)
        runner.run_algorithm("python", ["-c", "import time; time.sleep(10)"])

    # 2. At this point, the signal was caught. Assert it is running.
    assert runner.process.state() == QProcess.ProcessState.Running

    # 3. Trigger explicit cancellation
    runner.stop()

    # 4. Use qtbot.waitUntil to periodically check if the process state updated to NotRunning
    qtbot.waitUntil(lambda: runner.process.state() == QProcess.ProcessState.NotRunning, timeout=2000)

    # 5. Final assertion to guarantee the process is dead
    assert runner.process.state() == QProcess.ProcessState.NotRunning