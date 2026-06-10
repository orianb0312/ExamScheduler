import pytest
from unittest.mock import patch
from PyQt6.QtCore import QProcess, QObject


class DummySolverRunner(QObject):
    """
    A mockup of how your future Logic Controller should instantiate QProcess.
    This demonstrates the required architecture for executing the scheduling algorithm.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # CRITICAL ARCHITECTURE RULE:
        # Passing 'self' as the parent links the QProcess lifecycle to this QObject.
        # If the user closes the main application window, Qt automatically kills all child processes.
        # This prevents "Zombie processes" (solver.exe continuing to run invisibly in the background).
        self.process = QProcess(self)

    def run_solver(self):
        # Starts the local executable instead of sending an HTTP request.
        self.process.start("solver.exe", ["--local-run"])


def test_algorithm_runs_via_local_qprocess():
    """Verify that the algorithm uses local OS execution, not an HTTP API."""
    runner = DummySolverRunner()

    # We use 'patch' to intercept the QProcess.start method.
    # This lets us verify it was called without actually executing a real .exe file during tests.
    with patch.object(runner.process, 'start') as mock_start:
        runner.run_solver()

        # Ensure the process was triggered exactly once.
        mock_start.assert_called_once()

        # Check the arguments passed to QProcess.start to verify the correct local executable is used.
        args = mock_start.call_args[0]
        assert "solver.exe" in args[0], "Architecture Violation: Did not invoke local executable."


def test_qprocess_has_parent_to_prevent_zombies():
    """
    Verify that the QProcess is linked to the application's lifecycle.
    This ensures no orphaned processes consume CPU if the user closes the window early.
    """
    runner = DummySolverRunner()

    # Assert that the QProcess was instantiated with a valid parent object.
    assert runner.process.parent() is not None, (
        "Architecture Violation: QProcess instantiated without a parent. "
        "This will cause zombie processes if the UI is closed during calculation."
    )