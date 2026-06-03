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
    """Verify that initially the load button is ALWAYS enabled per new UX rules."""
    assert widget.get_courses_path() == ""
    assert widget.get_exam_dates_path() == ""

    # UX Check: The button must be fully clickable at all times
    assert widget.load_button.isEnabled()

    # UX Check: Ensure placeholder texts are visible to guide the user
    assert widget.courses_input.placeholderText() == "Select catalog data file from local system..."
    assert widget.exams_input.placeholderText() == "Select calendar/period layout configuration..."

    # Ensure the status label is the sole indicator and defaults to pending
    assert not widget.status_label.isHidden()
    assert "⏳ Waiting for files..." in widget.status_label.text()


def test_valid_files_keep_button_enabled(widget, tmp_path):
    """Verify that valid paths keep the button enabled and status pending."""
    courses_file = tmp_path / "courses_data"
    exams_file = tmp_path / "exams_data"
    courses_file.touch()
    exams_file.touch()

    widget.set_courses_path(str(courses_file))
    widget.set_exam_dates_path(str(exams_file))

    assert widget.load_button.isEnabled()
    assert "⏳ Waiting for files..." in widget.status_label.text()


def test_missing_or_invalid_file_updates_status_label(widget, tmp_path):
    """Verify that bad paths update the main Status Label to ERROR, without locking the button."""
    valid_file = tmp_path / "existing_mock_file"
    valid_file.touch()

    # Case 1: Courses file exists, but Exam Dates file path is invalid/missing
    widget.set_courses_path(str(valid_file))
    widget.set_exam_dates_path("C:/invalid/path/missing_exams_file")

    assert widget.load_button.isEnabled()
    assert "❌ ERROR" in widget.status_label.text()
    assert "Exam Dates file path is invalid" in widget.status_label.text()

    # Case 2: Exam Dates file exists, but Courses file path is invalid/missing
    widget.set_courses_path("C:/invalid/path/missing_courses_file")
    widget.set_exam_dates_path(str(valid_file))

    assert widget.load_button.isEnabled()
    assert "❌ ERROR" in widget.status_label.text()
    assert "Courses file path is invalid" in widget.status_label.text()


def test_invalid_path_handling_behavior(widget):
    """Verify explicit invalid paths trigger an error state on the main label."""
    widget.set_courses_path("C:/invalid/path/courses_file.csv")

    assert widget.load_button.isEnabled()
    assert "❌ ERROR" in widget.status_label.text()
    assert "Courses file path is invalid" in widget.status_label.text()


def test_load_action_emits_mvp_signal(widget, tmp_path, qtbot):
    """Verify that clicking the load button correctly emits the signal."""
    courses_path_obj = tmp_path / "courses_data"
    exams_path_obj = tmp_path / "exams_data"
    courses_path_obj.touch()
    exams_path_obj.touch()

    courses_file = str(courses_path_obj)
    exams_file = str(exams_path_obj)

    widget.set_courses_path(courses_file)
    widget.set_exam_dates_path(exams_file)

    with qtbot.waitSignal(widget.load_requested, timeout=1000) as blocker:
        qtbot.mouseClick(widget.load_button, Qt.MouseButton.LeftButton)

    assert blocker.args == [courses_file, exams_file]


def test_show_load_success_displays_status_message(widget):
    widget.show_load_success(3, 2, 1)

    assert not widget.status_label.isHidden()
    assert widget.status_label.property("status") == "success"
    assert "✓ SUCCESS" in widget.status_label.text()
    assert "Loaded 3 courses, 2 exam periods, and 1 study programs" in widget.status_label.text()


def test_show_load_error_displays_status_message(widget):
    widget.show_load_error("Could not parse courses file 'bad.txt': invalid format")

    assert not widget.status_label.isHidden()
    assert widget.status_label.property("status") == "error"
    assert "❌ ERROR" in widget.status_label.text()
    assert "Could not parse courses file" in widget.status_label.text()


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
    assert "⏳ Waiting for files..." in widget.status_label.text()


def test_load_error_keeps_button_enabled_if_paths_valid(widget, tmp_path):
    courses_file = tmp_path / "courses_data"
    exams_file = tmp_path / "exams_data"
    courses_file.touch()
    exams_file.touch()

    widget.set_courses_path(str(courses_file))
    widget.set_exam_dates_path(str(exams_file))

    assert widget.load_button.isEnabled()

    widget.show_load_error("Parse error: Invalid JSON format in courses file")

    assert not widget.status_label.isHidden()
    assert widget.status_label.property("status") == "error"
    assert widget.load_button.isEnabled()


# =======================================================================
# TESTS FOR 3-STATE STATUS LABEL (PENDING, SUCCESS, ERROR)
# =======================================================================

def test_status_label_initial_state_and_styling(widget):
    assert "⏳ Waiting for files..." in widget.status_label.text()
    assert "#808080" in widget.status_label.styleSheet()
    assert widget.status_label.alignment() == Qt.AlignmentFlag.AlignCenter


def test_show_load_success_updates_status_label_ui(widget):
    widget.show_load_success(4, 2, 1)

    status_text = widget.status_label.text()
    assert "✓ SUCCESS" in status_text
    assert "4 courses, 2 exam periods, and 1 study programs" in status_text
    assert "#28a745" in widget.status_label.styleSheet()


def test_show_load_error_updates_status_label_ui(widget):
    detailed_error = "File format is not recognized"
    widget.show_load_error(detailed_error)

    status_text = widget.status_label.text()
    assert "❌ ERROR" in status_text
    assert detailed_error in status_text
    assert "#dc3545" in widget.status_label.styleSheet()


def test_input_modification_updates_status_dynamically(widget, tmp_path):
    """
    Verify that typing into the input fields updates the status label dynamically
    based on whether the path being typed exists or not.
    """
    # 1. Force the UI into a Success state
    widget.show_load_success(1, 1, 1)

    # 2. Simulate typing an invalid path (evaluates instantly to Error per your logic)
    widget.courses_input.setText("C:/user/bad_path.txt")
    assert "❌ ERROR" in widget.status_label.text()

    # 3. Simulate resolving the path (evaluates back to Pending)
    valid_file = tmp_path / "valid.txt"
    valid_file.touch()

    # Needs both to be valid to go back to pure pending
    valid_exams = tmp_path / "valid_exams.txt"
    valid_exams.touch()
    widget.exams_input.setText(str(valid_exams))

    widget.courses_input.setText(str(valid_file))
    assert "⏳ Waiting for files..." in widget.status_label.text()


def test_invalid_path_triggers_error_status_label(widget):
    widget.set_courses_path("C:/fake/path/that/does/not/exist.txt")

    status_text = widget.status_label.text()
    assert "❌ ERROR" in status_text
    assert "Courses file path is invalid" in status_text
    assert "#dc3545" in widget.status_label.styleSheet()