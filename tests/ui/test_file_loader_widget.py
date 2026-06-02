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

    assert widget.error_label.isHidden()
    assert widget.status_label.isHidden()


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


def test_show_load_success_displays_status_message(widget):
    widget.show_load_success(3, 2, 1)

    assert not widget.status_label.isHidden()
    assert widget.status_label.property("status") == "success"
    assert "Successfully loaded 3 courses, 2 exam periods, and 1 study programs." in (
        widget.status_label.text()
    )


def test_show_load_error_displays_status_message(widget):
    widget.show_load_error("Could not parse courses file 'bad.txt': invalid format")

    assert not widget.status_label.isHidden()
    assert widget.status_label.property("status") == "error"
    assert "Failed to load files:" in widget.status_label.text()
    assert "Could not parse courses file" in widget.status_label.text()


def test_path_validation_does_not_clear_load_status_message(widget, tmp_path):
    courses_file = tmp_path / "courses_data"
    exams_file = tmp_path / "exams_data"
    courses_file.touch()
    exams_file.touch()

    widget.set_courses_path(str(courses_file))
    widget.set_exam_dates_path(str(exams_file))
    widget.show_load_success(1, 1, 1)

    widget.set_courses_path(str(courses_file))

    assert "Successfully loaded" in widget.status_label.text()
    assert not widget.status_label.isHidden()


def test_load_click_shows_pending_status_before_signal(widget, tmp_path, qtbot):
    courses_file = tmp_path / "courses_data"
    exams_file = tmp_path / "exams_data"
    courses_file.touch()
    exams_file.touch()

    widget.set_courses_path(str(courses_file))
    widget.set_exam_dates_path(str(exams_file))

    with qtbot.waitSignal(widget.load_requested, timeout=1000):
        qtbot.mouseClick(widget.load_button, Qt.MouseButton.LeftButton)

    assert widget.status_label.property("status") == "pending"
    assert "Loading files" in widget.status_label.text()

def test_load_error_keeps_button_enabled_if_paths_valid(widget, tmp_path):
    """
    Agile Requirement: Verify that a parsing/loading error does not disable
    the load button, allowing the user to fix the file externally and retry.
    """
    courses_file = tmp_path / "courses_data"
    exams_file = tmp_path / "exams_data"
    courses_file.touch()
    exams_file.touch()

    widget.set_courses_path(str(courses_file))
    widget.set_exam_dates_path(str(exams_file))

    # Button is initially enabled because paths are valid
    assert widget.load_button.isEnabled()

    # Simulate a parsing error returned from the backend service
    widget.show_load_error("Parse error: Invalid JSON format in courses file")

    # The status label should show the error
    assert not widget.status_label.isHidden()
    assert widget.status_label.property("status") == "error"

    # CRITICAL: The load button MUST remain enabled so the user can click it again
    assert widget.load_button.isEnabled()


def test_independent_error_and_status_labels_coexist(widget, tmp_path):
    """
    Agile Requirement: Verify that path validation (error_label) and
    load results (status_label) are fully decoupled and can coexist.
    """
    courses_file = tmp_path / "courses_data"
    exams_file = tmp_path / "exams_data"
    courses_file.touch()
    exams_file.touch()

    # 1. Valid initial state -> User clicks Load -> Successful load
    widget.set_courses_path(str(courses_file))
    widget.set_exam_dates_path(str(exams_file))
    widget.show_load_success(5, 2, 1)

    # 2. User later modifies one of the paths to an invalid file
    widget.set_courses_path("invalid_path_now.json")

    # 3. Path validation error should appear
    assert not widget.error_label.isHidden()
    assert "Courses file path is invalid" in widget.error_label.text()

    # 4. Previous load status MUST NOT be wiped out
    assert not widget.status_label.isHidden()
    assert widget.status_label.property("status") == "success"

    # 5. Button disables ONLY because the path is currently bad
    assert not widget.load_button.isEnabled()
