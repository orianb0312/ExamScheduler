import pytest
from PyQt6.QtCore import Qt
from src.ui.file_loader_widget import FileLoaderWidget


@pytest.fixture
def widget(qtbot):
    """Creates an instance of the widget and registers it with pytest-qt's qtbot."""
    file_loader = FileLoaderWidget()
    qtbot.addWidget(file_loader)
    return file_loader


def test_initial_state(widget):
    """Verify that initially the load button is disabled and file paths are empty."""
    assert widget.get_courses_path() == ""
    assert widget.get_exam_dates_path() == ""
    assert not widget.load_button.isEnabled()

    # UX Check: Ensure placeholder texts are visible to guide the user
    assert widget.courses_input.placeholderText() == "Select catalog data file from local system..."
    assert widget.exams_input.placeholderText() == "Select calendar/period layout configuration..."

    # Check that the error label is hidden at setup (isHidden should be True)
    assert widget.error_label.isHidden()


def test_valid_files_enable_load_button(widget, tmp_path):
    """Verify that the load button is enabled only when both required files exist on disk."""
    courses_file = tmp_path / "courses_data"
    exams_file = tmp_path / "exams_data"
    courses_file.touch()
    exams_file.touch()

    # Simulate programmatic file path selection
    widget.set_courses_path(str(courses_file))
    widget.set_exam_dates_path(str(exams_file))

    # The load button should now be enabled as paths are validated successfully
    assert widget.load_button.isEnabled()

    # Verify that the error label remains hidden when inputs are valid
    assert widget.error_label.isHidden()


def test_missing_or_invalid_file_keeps_button_disabled(widget, tmp_path):
    """Verify that if one or both files do not exist on disk, the load button stays disabled."""
    valid_file = tmp_path / "existing_mock_file"
    valid_file.touch()

    # Case 1: Courses file exists, but Exam Dates file path is invalid/missing
    widget.set_courses_path(str(valid_file))
    widget.set_exam_dates_path("C:/invalid/path/missing_exams_file")
    assert not widget.load_button.isEnabled()

    # Using isHidden() instead of isVisible() resolves the offscreen CI/CD headless execution issue
    assert not widget.error_label.isHidden()
    assert "Exam Dates file path is invalid" in widget.error_label.text()

    # Case 2: Exam Dates file exists, but Courses file path is invalid/missing
    widget.set_courses_path("C:/invalid/path/missing_courses_file")
    widget.set_exam_dates_path(str(valid_file))
    assert not widget.load_button.isEnabled()
    assert not widget.error_label.isHidden()
    assert "Courses file path is invalid" in widget.error_label.text()


def test_invalid_path_handling_behavior(widget):
    """
    Verify that providing an invalid path explicitly changes the UI state
    to reveal a clear, descriptive error message and blocks execution.
    """
    # Simulate an invalid course path inject
    widget.set_courses_path("C:/invalid/path/courses_file.csv")

    # 1. Ensure the error label is NO LONGER hidden (meaning it was instructed to reveal itself)
    assert not widget.error_label.isHidden()

    # 2. Verify that the correct descriptive string is injected for user clarity
    assert "Courses file path is invalid or does not exist." in widget.error_label.text()

    # 3. Ensure the widget clearly flags this as invalid by keeping the execution path disabled
    assert not widget.load_button.isEnabled()


def test_load_action_emits_mvp_signal(widget, tmp_path, qtbot):
    """Verify that clicking the load button correctly emits the load_requested signal with proper paths."""
    courses_path_obj = tmp_path / "courses_data"
    exams_path_obj = tmp_path / "exams_data"
    courses_path_obj.touch()
    exams_path_obj.touch()

    courses_file = str(courses_path_obj)
    exams_file = str(exams_path_obj)

    widget.set_courses_path(courses_file)
    widget.set_exam_dates_path(exams_file)

    # Catch the Qt Signal emission natively using qtbot context manager
    with qtbot.waitSignal(widget.load_requested, timeout=1000) as blocker:
        qtbot.mouseClick(widget.load_button, Qt.MouseButton.LeftButton)

    # Assert that the signal was emitted with the exact expected file path payloads
    assert blocker.args == [courses_file, exams_file]