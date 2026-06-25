import pytest
from datetime import date
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QMessageBox, QPushButton, QScrollArea, QSizePolicy

from src.services.cli_run_service import build_cli_arguments
from src.models.academic import Course, Exam, ProgramAffiliation
from src.models.enums import Semester, Term
from src.models.enums import RequirementType
from src.models.scheduling import ExamPeriod
from src.services.file_loading_service import LoadedSchedulerInput
from src.services.constraint_settings_policy import DEFAULT_CONSTRAINT_SETTINGS_POLICY
from src.services.program_selection_policy import (
    DEFAULT_PROGRAM_SELECTION_POLICY,
)
from src.ui.file_loader_widget import FileLoaderWidget
from src.ui.input_panel import InputPanel, _format_constraint_validation_warning
from src.ui.program_selection_widget import LIMIT_MESSAGE, MAX_SELECTED_PROGRAMS


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
    assert widget.get_course_load_mode() == "replace"
    assert widget.get_exam_dates_load_mode() == "replace"
    assert widget.course_replace_button.isChecked()
    assert widget.exam_dates_replace_button.isChecked()
    assert not widget.load_button.isEnabled()

    # UX Check: Ensure placeholder texts are visible to guide the user
    assert widget.courses_input.placeholderText() == "Select catalog data file from local system..."
    assert widget.exams_input.placeholderText() == "Select calendar/period layout configuration..."

    # Check that the error label is hidden at setup (isHidden should be True)
    assert widget.error_label.isHidden()


def test_mode_buttons_are_inline_and_styled(widget):
    labels = [label.text() for label in widget.findChildren(QLabel)]

    assert "Courses Mode:" not in labels
    assert "Exam Dates Mode:" not in labels
    assert "File Management" in labels
    assert "Course Data" in labels
    assert "Date Data" in labels
    assert widget.course_replace_button.objectName() == "modeButton"
    assert widget.course_update_button.objectName() == "modeButton"
    assert widget.exam_dates_replace_button.objectName() == "modeButton"
    assert widget.exam_dates_update_button.objectName() == "modeButton"


def test_input_panel_shows_output_action_without_cli_controls(tmp_path, qtbot):
    panel = InputPanel(project_root=tmp_path)
    qtbot.addWidget(panel)

    assert panel.mode_combo.parent() is None
    assert panel.mode_combo.currentText() == "auto"
    assert panel.output_config_edit.parent() is None
    assert panel.user_file_edit.parent() is None
    assert panel.period_indexes_edit.parent() is None
    assert panel.max_systems_edit.parent() is None
    assert panel.time_limit_edit.parent() is None
    assert panel.run_button.parent() is panel
    assert panel.run_button.text() == "Generate Schedules"
    assert panel.cancel_button.parent() is None


def test_input_panel_uses_dashboard_shell_layout(tmp_path, qtbot):
    panel = InputPanel(project_root=tmp_path)
    qtbot.addWidget(panel)

    assert panel.findChild(QScrollArea, "inputPanelScrollArea") is not None
    assert "Programs" in panel.nav_tabs
    assert panel.nav_tabs["Programs"].objectName() == "navTabActive"
    assert [
        button.text()
        for button in panel.findChildren(QPushButton)
        if button.objectName() in {"navTab", "navTabActive"}
    ] == ["Dashboard", "Programs", "Courses", "Calendar", "Settings", "Schedules"]


def test_input_panel_home_image_fills_lower_page_area(tmp_path, qtbot):
    panel = InputPanel(project_root=tmp_path)
    qtbot.addWidget(panel)

    image_panel = panel.findChild(QFrame, "homeImagePanel")

    assert image_panel is not None
    assert image_panel.minimumHeight() >= 180
    assert image_panel.maximumHeight() <= 340
    assert image_panel.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert image_panel.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding


def test_file_path_fields_are_wider_than_browse_buttons(tmp_path, qtbot):
    panel = InputPanel(project_root=tmp_path)
    qtbot.addWidget(panel)
    panel.resize(1400, 900)
    panel.show()
    qtbot.wait(20)

    loader = panel.file_loader
    assert loader.courses_input.width() > loader.courses_btn.width() * 2
    assert loader.exams_input.width() > loader.exams_btn.width() * 2


def test_input_panel_shows_program_selection_limit_message(tmp_path, qtbot):
    panel = InputPanel(project_root=tmp_path)
    qtbot.addWidget(panel)
    panel.replace_program_list(["83101", "83102", "83103", "83104", "83105", "83106"])

    assert MAX_SELECTED_PROGRAMS == DEFAULT_PROGRAM_SELECTION_POLICY.max_selected
    assert panel.program_selection_count.text() == f"0/{MAX_SELECTED_PROGRAMS}"

    panel.program_selector.item(0).setCheckState(Qt.CheckState.Checked)
    assert panel.program_selection_count.text() == f"1/{MAX_SELECTED_PROGRAMS}"

    panel.program_selector.item(1).setCheckState(Qt.CheckState.Checked)
    assert panel.program_selection_count.text() == f"2/{MAX_SELECTED_PROGRAMS}"

    for index in range(MAX_SELECTED_PROGRAMS):
        panel.program_selector.item(index).setCheckState(Qt.CheckState.Checked)

    assert panel.program_selection_count.text() == f"5/{MAX_SELECTED_PROGRAMS}"
    assert panel.program_selection_message.text() == LIMIT_MESSAGE
    assert not panel.program_selection_message.isHidden()

    panel.program_selector.item(0).setCheckState(Qt.CheckState.Unchecked)

    assert panel.program_selection_count.text() == f"4/{MAX_SELECTED_PROGRAMS}"
    assert panel.program_selection_message.isHidden()


def test_input_panel_keeps_calendar_action_in_dashboard_nav(tmp_path, qtbot):
    panel = InputPanel(project_root=tmp_path)
    qtbot.addWidget(panel)

    assert panel.view_calendar_button is panel.nav_tabs["Calendar"]
    assert panel.view_calendar_button.text() == "Calendar"
    assert panel.view_calendar_button.isEnabled()

    panel.set_exam_calendar_available(True)

    assert panel.view_calendar_button.isEnabled()
    assert panel.run_button.parent() is panel


def test_input_panel_passes_selected_programs_to_scheduler_config(tmp_path, qtbot):
    panel = InputPanel(project_root=tmp_path)
    qtbot.addWidget(panel)
    panel.replace_program_list(["83101", "83102", "83108"])
    panel.program_selector.item(0).setCheckState(Qt.CheckState.Checked)
    panel.program_selector.item(2).setCheckState(Qt.CheckState.Checked)

    with qtbot.waitSignal(panel.run_requested, timeout=1000) as blocker:
        qtbot.mouseClick(panel.run_button, Qt.MouseButton.LeftButton)

    config = blocker.args[0]
    _program, args = build_cli_arguments(config)
    user_file_index = args.index("--user-file") + 1

    assert config.stream_schedules is True
    assert config.lazy_schedules is True
    assert "--lazy-schedules" in args
    assert config.user_file is not None
    assert args[user_file_index] == str(config.user_file)
    assert config.user_file.read_text(encoding="utf-8") == "83101, 83108"


def test_input_panel_blocks_generation_when_constraint_settings_are_invalid(
    tmp_path,
    qtbot,
    monkeypatch,
):
    panel = InputPanel(project_root=tmp_path)
    qtbot.addWidget(panel)
    panel.replace_program_list(["83101"])
    panel.program_selector.item(0).setCheckState(Qt.CheckState.Checked)

    warnings: list[tuple[str, str]] = []

    def fake_warning(*args, **_kwargs):
        warnings.append((args[1], args[2]))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", fake_warning)

    # Zero is invalid here because this is one of the positive-integer constraints.
    panel.constraint_settings.set_constraint(
        "min_days_between_mandatory",
        enabled=True,
        value="0",
    )
    emitted_configs: list = []
    panel.run_requested.connect(emitted_configs.append)

    qtbot.mouseClick(panel.run_button, Qt.MouseButton.LeftButton)

    assert emitted_configs == []
    assert warnings == [
        (
            "Invalid constraint value",
            (
                'The value in "Minimum days between mandatory exams" must be '
                "a positive whole number. Fix it before generating schedules."
            ),
        )
    ]
    assert panel.is_settings_page_visible()


def test_constraint_warning_names_each_invalid_setting():
    # Build policy errors directly so the message formatter can be tested without a modal.
    validation = DEFAULT_CONSTRAINT_SETTINGS_POLICY.validate_all(
        {
            "min_days_between_mandatory": (True, "0"),
            "min_days_between_any": (True, ""),
            "max_elective_conflicts": (True, "-1"),
        }
    )

    title, message = _format_constraint_validation_warning(validation)

    assert title == "Invalid constraint values"
    assert (
        '- The value in "Minimum days between mandatory exams" must be '
        "a positive whole number."
    ) in message
    assert '- The value in "Minimum days between any two exams" is required.' in message
    assert (
        '- The value in "Maximum elective conflicts" must be '
        "zero or a positive whole number."
    ) in message


def test_input_panel_passes_loaded_courses_to_scheduler_config(tmp_path, qtbot):
    panel = InputPanel(project_root=tmp_path)
    qtbot.addWidget(panel)
    course = Course(
        course_id=77777,
        name="Dynamic Program Exam",
        instructor="Dr. Runtime",
        evaluation=Exam(),
        affiliations=[
            ProgramAffiliation(
                program_id=83108,
                year=2,
                semester=Semester.SUMMER,
                requirement_type=RequirementType.OBLIGATORY,
            )
        ],
    )
    panel.replace_program_list(["83108"])
    panel.program_selector.item(0).setCheckState(Qt.CheckState.Checked)
    panel.notify_data_loaded(
        LoadedSchedulerInput(
            courses=(course,),
            exam_periods=(),
            programs=(),
        )
    )

    with qtbot.waitSignal(panel.run_requested, timeout=1000) as blocker:
        qtbot.mouseClick(panel.run_button, Qt.MouseButton.LeftButton)

    config = blocker.args[0]

    assert config.course_file is not None
    assert config.course_file.name == "ui_courses.txt"
    assert "83108,2,SUMM,Obligatory" in config.course_file.read_text(encoding="utf-8")
    assert config.user_file is not None
    assert config.user_file.read_text(encoding="utf-8") == "83108"


def test_input_panel_passes_excluded_day_state_to_scheduler_config(tmp_path, qtbot):
    panel = InputPanel(project_root=tmp_path)
    qtbot.addWidget(panel)
    panel.replace_program_list(["83101"])
    panel.program_selector.item(0).setCheckState(Qt.CheckState.Checked)
    panel.notify_data_loaded(
        LoadedSchedulerInput(
            courses=(),
            exam_periods=(
                ExamPeriod(
                    semester=Semester.FALL,
                    term=Term.ALEPH,
                    start_date=date(2026, 1, 1),
                    end_date=date(2026, 1, 3),
                ),
            ),
            programs=(),
        )
    )
    panel.exclude_calendar_day(0, date(2026, 1, 2))

    with qtbot.waitSignal(panel.run_requested, timeout=1000) as blocker:
        qtbot.mouseClick(panel.run_button, Qt.MouseButton.LeftButton)

    config = blocker.args[0]
    assert config.dates_file is not None
    assert config.dates_file.name == "ui_exam_dates.txt"
    assert "- 02-01-2026" in config.dates_file.read_text(encoding="utf-8")


def test_input_panel_passes_edited_period_dates_to_scheduler_config(tmp_path, qtbot):
    panel = InputPanel(project_root=tmp_path)
    qtbot.addWidget(panel)
    panel.replace_program_list(["83101"])
    panel.program_selector.item(0).setCheckState(Qt.CheckState.Checked)
    panel.notify_data_loaded(
        LoadedSchedulerInput(
            courses=(),
            exam_periods=(
                ExamPeriod(
                    semester=Semester.FALL,
                    term=Term.ALEPH,
                    start_date=date(2026, 1, 1),
                    end_date=date(2026, 1, 3),
                ),
            ),
            programs=(),
        )
    )
    panel._update_period_dates(0, date(2026, 1, 2), date(2026, 1, 4))

    with qtbot.waitSignal(panel.run_requested, timeout=1000) as blocker:
        qtbot.mouseClick(panel.run_button, Qt.MouseButton.LeftButton)

    config = blocker.args[0]
    assert config.dates_file is not None
    assert "02-01-2026, 04-01-2026" in config.dates_file.read_text(encoding="utf-8")


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

    # The user should get a clear reason why loading is blocked.
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
    widget.set_course_load_mode("replace")
    widget.set_exam_dates_load_mode("update")

    # qtbot records the signal payload after the button click.
    with qtbot.waitSignal(widget.load_requested, timeout=1000) as blocker:
        qtbot.mouseClick(widget.load_button, Qt.MouseButton.LeftButton)

    # Assert that the signal was emitted with the exact expected file path payloads
    assert blocker.args == [courses_file, exams_file, "replace", "update"]


def test_network_drive_paths_are_rejected(widget):
    """
    Architecture Rule: Prevent loading files directly from network drives (UNC paths).
    This enforces the Standalone/Offline architecture requirement.
    """
    # Simulate an attempt to load from a network shared folder
    widget.set_courses_path(r"\\CorporateServer\SharedFiles\courses.csv")

    # 1. Verify the UI correctly identifies the error and shows the label
    assert not widget.error_label.isHidden()

    # 2. We expect the UI to specifically reject network paths
    error_text = widget.error_label.text()
    assert "Network paths" in error_text

    # 3. Ensure the load button remains strictly disabled to prevent server/network calls
    assert not widget.load_button.isEnabled()
