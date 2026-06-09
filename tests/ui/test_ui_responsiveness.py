import time
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import Qt

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
    Step 1 Requirement: Test file selection and file loading responsiveness.
    Ensures that opening, reading, parsing, and populating initial database
    records into memory completes well below the 1-second responsiveness limit.
    """
    courses_file, exam_dates_file = _create_responsive_test_files(tmp_path)
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    # Set file paths into the UI fields to simulate completion of file selection browsing
    window.input_panel.file_loader.set_courses_path(str(courses_file))
    window.input_panel.file_loader.set_exam_dates_path(str(exam_dates_file))

    # Benchmark the complete synchronous parsing loop triggered by clicking the load button
    start_time = time.perf_counter()
    qtbot.mouseClick(
        window.input_panel.file_loader.load_button,
        Qt.MouseButton.LeftButton,
    )
    elapsed_time = time.perf_counter() - start_time

    # Assert the main thread is never blocked or frozen for more than 1 second
    assert elapsed_time < 1.0, f"File loading blocked the UI thread for {elapsed_time:.2f}s"


def test_ui_program_selection_responsiveness(tmp_path, qtbot):
    """
    Step 2 Requirement: Test study program option selection responsiveness.
    Verifies that choosing filtering choices, indexing targets, and re-rendering
    the active selection layout summary updates the display dynamically without freezing.
    """
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    # Benchmark program state modification and subsequent widget status updates
    start_time = time.perf_counter()
    window.input_panel._store_selected_programs(["83101", "83102", "83104"])
    elapsed_time = time.perf_counter() - start_time

    # Confirm UI response time meets the latency threshold criteria
    assert elapsed_time < 1.0, f"Program selection blocked the UI thread for {elapsed_time:.2f}s"


def test_ui_date_editing_responsiveness(tmp_path, qtbot):
    """
    Step 3 Requirement: Test date boundary constraint editing and layout redraw.
    Verifies that changing target start or end boundaries and structurally rebuildable
    grid panels for monthly calendar widgets performs smoothly.
    """
    courses_file, exam_dates_file = _create_responsive_test_files(tmp_path)
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    # Load valid files first to populate an exam period at index 0 and avoid validation alerts
    window.input_panel.file_loader.set_courses_path(str(courses_file))
    window.input_panel.file_loader.set_exam_dates_path(str(exam_dates_file))
    qtbot.mouseClick(
        window.input_panel.file_loader.load_button,
        Qt.MouseButton.LeftButton,
    )

    # Benchmark full calendar rendering routine when data ranges shift
    start_time = time.perf_counter()
    window._update_period_dates(0, date(2026, 1, 2), date(2026, 1, 12))
    elapsed_time = time.perf_counter() - start_time

    # Validate redraw calculations finish in under 1 second
    assert elapsed_time < 1.0, f"Date editing/redraw blocked the UI thread for {elapsed_time:.2f}s"


def test_ui_schedule_generation_is_non_blocking_on_main_thread(tmp_path, qtbot):
    """
    Step 4 Requirement: Test background schedule solver execution workflow.
    Confirms that clicking run starts the subprocess asynchronously using QProcess,
    releasing the UI loop immediately rather than freezing while calculations process.
    """
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    # Construct standard test command pipeline configuration parameters
    config = CliRunConfig(
        project_root=tmp_path,
        mode="complete-count",
        course_file=tmp_path / "courses_resp.txt",
        dates_file=tmp_path / "dates_resp.txt"
    )

    # Measure initiation cost; launching an OS thread pipe must be instantaneous
    start_time = time.perf_counter()
    window._start_cli_run(config)
    elapsed_time = time.perf_counter() - start_time

    # Confirm process initialization yields execution context immediately back to the GUI loop
    assert elapsed_time < 1.0, f"Starting process blocked the UI thread for {elapsed_time:.2f}s"

    # Safely terminate the launched test worker process to avoid orphan resource leaks
    window._runner.cancel()


def test_ui_schedule_navigation_and_saving_responsiveness(tmp_path, qtbot):
    """
    Step 5 Requirement: Test output screen page navigation.
    Ensures pagination changes, view-model mapping, and canvas refreshes for
    individual solutions return answers within the strict 1-second limit.
    """
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    # Use MagicMock to genericize the ScheduleSystem object initialization and avoid constructor mismatches
    dummy_system = MagicMock()
    window._calendar_data_service.exams_for_period = MagicMock(return_value=())

    window.output_view.add_systems([dummy_system])
    window.output_view.set_schedule_total(1)

    # Measure page navigation refresh rate when moving through cached options
    start_time = time.perf_counter()
    window.output_view._refresh_page()
    elapsed_time = time.perf_counter() - start_time

    # Assert navigation paging switches screens seamlessly under 1 second
    assert elapsed_time < 1.0, f"Schedule page navigation blocked the UI thread for {elapsed_time:.2f}s"

def test_ui_bulk_schedule_cache_loading_responsiveness(tmp_path, qtbot):
    """
    Edge Case 1: Test responsiveness when loading a very large batch of schedule systems into the cache.
    Verifies that the pagination bar and cache layout scaling do not freeze the UI thread.
    """
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    # Simulate receiving a massive list of 2,000 generated schedules at once from the runner
    large_batch = [MagicMock() for _ in range(2000)]

    # Measure the cost of expanding the cache list and updating total pages simultaneously
    start_time = time.perf_counter()
    window.output_view.add_systems(large_batch)
    elapsed_time = time.perf_counter() - start_time

    assert elapsed_time < 1.0, f"Loading a bulk batch of systems blocked the UI for {elapsed_time:.2f}s"

def test_ui_post_process_file_loading_responsiveness(tmp_path, qtbot):
    """
    Edge Case 2: Test responsiveness when the process finishes and attempts to post-process output data files.
    Ensures that transition states and final data adapters do not cause UI lockups upon process exit.
    """
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    # Mock the internal file loading behavior to prevent actual heavy disk IO crashes during test execution
    window._load_generated_output_file = MagicMock()
    window._should_show_empty_schedule_message = MagicMock(return_value=False)

    start_time = time.perf_counter()
    # Trigger the process finished event handler directly with a successful exit code (0)
    window._handle_finished(0, "NormalExit")
    elapsed_time = time.perf_counter() - start_time

    assert elapsed_time < 1.0, f"Process finish handling blocked the UI for {elapsed_time:.2f}s"

def test_ui_shows_processing_indicator_when_process_is_active(tmp_path, qtbot):
    """
    Requirement Verification:
    - Add a simple loading indicator, status label, or progress message.
    - Show the indicator when QProcess starts.
    - Hide or update the indicator when QProcess finishes.
    """
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    # 1. Before execution, the action button must display its default idle text
    assert window.input_panel.run_button.text() == "Generate Schedules"
    assert window.output_view.status_label.text() == "Ready"

    # 2. Simulate the process starting (triggering the QProcess active signals)
    window._handle_started()

    # Verify that the loading indicators instantly change to notify the user
    assert window.input_panel.run_button.text() == "Generating Schedules..."
    assert window.input_panel.run_button.isEnabled() is False
    assert window.output_view.status_label.text() == "Running..."

    # 3. Simulate the process finishing execution successfully
    window._handle_finished(0, "NormalExit")

    # Verify that indicators are updated/hidden and button control returns to normal idle state
    assert window.input_panel.run_button.text() == "Generate Schedules"
    assert window.input_panel.run_button.isEnabled() is True