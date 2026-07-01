import time
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import Qt
from unittest.mock import MagicMock, patch
from src.ui.main_window import MainWindow
from src.services.cli_run_service import CliRunConfig

# Minimal valid test data strings matching production syntax rules for fast loading
COURSES_TEXT = """$$$$
Calculus 1
10001
Dr. Ada Lovelace
83101,1,FALL,Obligatory
Exam
"""

EXAM_DATES_TEXT = """$$$$
FALL,Aleph
01-01-2026, 10-01-2026
03-01-2026 Saturday
"""


def _create_responsive_test_files(tmp_path: Path) -> tuple[Path, Path]:
    """
    Helper function to write lightweight, well-formed input catalog and layout setup
    files to a temporary directory for isolation.
    """
    courses_file = tmp_path / "courses_resp.txt"
    dates_file = tmp_path / "dates_resp.txt"
    courses_file.write_text(COURSES_TEXT, encoding="utf-8")
    dates_file.write_text(EXAM_DATES_TEXT, encoding="utf-8")
    return courses_file, dates_file


def test_ui_file_selection_and_loading_responsiveness(tmp_path, qtbot):
    """
    Test file selection and file loading responsiveness.
    Ensures that opening, reading, parsing, and populating initial database
    records into memory completes well below the 1-second responsiveness limit.
    """
    courses_file, exam_dates_file = _create_responsive_test_files(tmp_path)
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    window.input_panel.file_loader.set_courses_path(str(courses_file))
    window.input_panel.file_loader.set_exam_dates_path(str(exam_dates_file))

    start_time = time.perf_counter()
    qtbot.mouseClick(
        window.input_panel.file_loader.load_button,
        Qt.MouseButton.LeftButton,
    )
    elapsed_time = time.perf_counter() - start_time
    print(f"\n  [latency] File loading: {elapsed_time * 1000:.1f} ms")

    assert elapsed_time < 1.0, f"File loading blocked the UI thread for {elapsed_time:.2f}s"


def test_ui_program_selection_responsiveness(tmp_path, qtbot):
    """
    Test study program option selection responsiveness.
    Verifies that choosing filtering choices, indexing targets, and re-rendering
    the active selection layout summary updates the display dynamically without freezing.
    """
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    start_time = time.perf_counter()
    window.input_panel._store_selected_programs(["83101", "83102", "83104"])
    elapsed_time = time.perf_counter() - start_time
    print(f"\n  [latency] Program selection: {elapsed_time * 1000:.1f} ms")

    assert elapsed_time < 1.0, f"Program selection blocked the UI thread for {elapsed_time:.2f}s"


def test_ui_date_editing_responsiveness(tmp_path, qtbot):
    """
    Test date boundary constraint editing and layout redraw.
    Verifies that changing target start or end boundaries and structurally rebuildable
    grid panels for monthly calendar widgets performs smoothly.
    """
    courses_file, exam_dates_file = _create_responsive_test_files(tmp_path)
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    window.input_panel.file_loader.set_courses_path(str(courses_file))
    window.input_panel.file_loader.set_exam_dates_path(str(exam_dates_file))
    qtbot.mouseClick(
        window.input_panel.file_loader.load_button,
        Qt.MouseButton.LeftButton,
    )

    start_time = time.perf_counter()
    window._update_period_dates(0, date(2026, 1, 2), date(2026, 1, 12))
    elapsed_time = time.perf_counter() - start_time
    print(f"\n  [latency] Date editing + calendar redraw: {elapsed_time * 1000:.1f} ms")

    assert elapsed_time < 1.0, f"Date editing/redraw blocked the UI thread for {elapsed_time:.2f}s"


def test_ui_schedule_generation_is_non_blocking_on_main_thread(tmp_path, qtbot):
    """
    Test background schedule solver execution workflow.
    Confirms that clicking run starts the subprocess asynchronously using QProcess,
    releasing the UI loop immediately rather than freezing while calculations process.
    """
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    config = CliRunConfig(
        project_root=tmp_path,
        mode="complete-count",
        course_file=tmp_path / "courses_resp.txt",
        dates_file=tmp_path / "dates_resp.txt"
    )

    start_time = time.perf_counter()
    window._start_cli_run(config)
    elapsed_time = time.perf_counter() - start_time
    print(f"\n  [latency] QProcess start: {elapsed_time * 1000:.1f} ms")

    assert elapsed_time < 1.0, f"Starting process blocked the UI thread for {elapsed_time:.2f}s"

    window._runner.cancel()


def test_ui_schedule_navigation_and_saving_responsiveness(tmp_path, qtbot):
    """
    Test output screen page navigation.
    Ensures pagination changes, view-model mapping, and canvas refreshes for
    individual solutions return answers within the strict 1-second limit.
    """
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    dummy_system = MagicMock()
    window._calendar_data_service.exams_for_period = MagicMock(return_value=())

    window.output_view.add_systems([dummy_system])
    window.output_view.set_schedule_total(1)

    start_time = time.perf_counter()
    window.output_view._refresh_page()
    elapsed_time = time.perf_counter() - start_time
    print(f"\n  [latency] Schedule page navigation: {elapsed_time * 1000:.1f} ms")

    assert elapsed_time < 1.0, f"Schedule page navigation blocked the UI thread for {elapsed_time:.2f}s"


def test_ui_constraint_settings_value_change_responsiveness(tmp_path, qtbot):
    """
    Test scheduling-constraints (Settings) page responsiveness.
    Changing a constraint value triggers full validation of all five constraints
    plus a UI refresh of each row. Verify this per-keystroke work never blocks
    the UI thread beyond the 1-second responsiveness limit.
    """
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    settings = window.input_panel.constraint_settings

    start_time = time.perf_counter()
    settings.set_constraint("min_days_between_mandatory", enabled=True, value="5")
    settings.set_constraint("max_exams_per_day", enabled=True, value="2")
    elapsed_time = time.perf_counter() - start_time
    print(f"\n  [latency] Settings value change: {elapsed_time * 1000:.1f} ms")

    assert elapsed_time < 1.0, (
        f"Constraint value change blocked the UI thread for {elapsed_time:.2f}s"
    )


def test_ui_constraint_settings_pre_run_validation_responsiveness(tmp_path, qtbot):
    """
    Test the pre-Generate constraint validation gate.
    The guard validates all enabled constraints before building runtime files.
    Confirm the gate stays well under the 1-second limit even in its slowest
    case (an invalid constraint that also builds the per-constraint warning).
    """
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    settings = window.input_panel.constraint_settings
    settings.set_constraint("min_days_between_mandatory", enabled=True, value="")

    start_time = time.perf_counter()
    with patch("src.ui.input_panel.QMessageBox"):
        can_run = window.input_panel._validate_constraints_before_run()
    elapsed_time = time.perf_counter() - start_time
    print(f"\n  [latency] Settings pre-run guard: {elapsed_time * 1000:.1f} ms")

    assert can_run is False
    assert elapsed_time < 1.0, (
        f"Constraint pre-run validation blocked the UI thread for {elapsed_time:.2f}s"
    )


def test_ui_bulk_schedule_cache_loading_responsiveness(tmp_path, qtbot):
    """
    Edge Case 1: Test responsiveness when loading a very large batch of schedule systems into the cache.
    Verifies that the pagination bar and cache layout scaling do not freeze the UI thread.
    """
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    large_batch = [MagicMock() for _ in range(2000)]

    start_time = time.perf_counter()
    window.output_view.add_systems(large_batch)
    elapsed_time = time.perf_counter() - start_time
    print(f"\n  [latency] Bulk cache load (2,000 systems): {elapsed_time * 1000:.1f} ms")

    assert elapsed_time < 1.0, f"Loading a bulk batch of systems blocked the UI for {elapsed_time:.2f}s"


def test_ui_post_process_file_loading_responsiveness(tmp_path, qtbot):
    """
    Edge Case 2: Test responsiveness when the process finishes and attempts to post-process output data files.
    Ensures that transition states and final data adapters do not cause UI lockups upon process exit.
    """
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    window._load_generated_output_file = MagicMock()
    window._should_show_empty_schedule_message = MagicMock(return_value=False)

    start_time = time.perf_counter()
    window._handle_finished(0, "NormalExit")
    elapsed_time = time.perf_counter() - start_time
    print(f"\n  [latency] Process finish handler: {elapsed_time * 1000:.1f} ms")

    assert elapsed_time < 1.0, f"Process finish handling blocked the UI for {elapsed_time:.2f}s"


def test_ui_shows_processing_indicator_when_process_is_active(tmp_path, qtbot):
    """
    Requirement Verification:
    - Show the dedicated loading view overlay when QProcess starts.
    - Hide or transition the loading view when QProcess finishes.
    """
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    assert window.input_panel.run_button.text() == "Generate Schedules"
    assert window.output_view.status_label.text() == "Ready"

    window._handle_started()

    # Verify that stack switches layout to loading view overlay correctly
    assert window._stack.currentWidget() is window.loading_view
    assert window.input_panel.run_button.isEnabled() is False
    assert window.input_panel.run_button.text() == "Generating Schedules..."

    window._handle_finished(0, "NormalExit")

    assert window.input_panel.run_button.text() == "Generate Schedules"
    assert window.input_panel.run_button.isEnabled() is True


def test_loading_view_cancel_button_stops_process(tmp_path, qtbot):
    # Create a mock for the ProcessRunner
    mock_runner = MagicMock()

    # Inject the mock directly via the factory parameter.
    # This avoids brittle string-based patching and guarantees
    # the signals bind to our mock.
    window = MainWindow(
        project_root=tmp_path,
        process_runner_factory=lambda parent: mock_runner
    )
    qtbot.addWidget(window)

    # Simulate process start to display the loading view overlay
    window._handle_started()

    # Verify we actually transitioned to the loading screen
    assert window._stack.currentWidget() is window.loading_view

    # Click the cancel button on the loading screen
    qtbot.mouseClick(window.loading_view.cancel_button, Qt.MouseButton.LeftButton)

    # Verify that the cancel signal was properly forwarded to the runner exactly once
    mock_runner.cancel.assert_called_once()
