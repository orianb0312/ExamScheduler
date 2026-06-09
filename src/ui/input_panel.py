
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.services.cli_run_service import (
    CliRunConfig,
    SchedulerRunConfigBuilder,
    SchedulerRunForm,
)
from src.services.file_loading_service import LoadedSchedulerInput
from src.services.scheduler_input_state import SchedulerInputState
from src.ui.calendar_view_panel import CalendarView
from src.ui.file_loader_widget import FileLoaderWidget
from src.ui.program_selection_widget import MAX_SELECTED_PROGRAMS, ProgramSelectionWidget
from src.ui.selected_programs_panel import SelectedProgramsPanel
from src.services.selected_programs_service import SelectedProgramsViewModel


class InputPanel(QWidget):

    run_requested = pyqtSignal(CliRunConfig)
    cancel_requested = pyqtSignal()
    data_load_requested = pyqtSignal(str, str, str, str)
    view_calendar_requested = pyqtSignal()

    def __init__(self, project_root: Path, parent=None) -> None:
        super().__init__(parent)
        self._project_root = project_root
        self._scheduler_input_state = SchedulerInputState(
            project_root / "outputs" / "ui_runtime"
        )
        self._run_config_builder = SchedulerRunConfigBuilder(self._scheduler_input_state)
        self.selected_programs_vm = SelectedProgramsViewModel()

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["complete-count", "period", "complete-write", "auto"])
        self.mode_combo.setCurrentText("auto")

        self.output_config_edit = self._path_edit(project_root / "config.json")
        self.course_file_edit = self._path_edit(project_root / "data" / "V1.0CourseDB.txt")
        self.dates_file_edit = self._path_edit(project_root / "data" / "V1.0 ExamDates.txt")
        self.user_file_edit = self._path_edit(project_root / "data" / "Programs.txt")
        self.file_loader = FileLoaderWidget()
        self.file_loader.set_courses_path(self.course_file_edit.text())
        self.file_loader.set_exam_dates_path(self.dates_file_edit.text())
        self.nav_tabs = {
            "Dashboard": self._nav_button("Dashboard", enabled=False),
            "Programs": self._nav_button("Programs", active=True),
            "Courses": self._nav_button("Courses", enabled=False),
            "Calendar": self._nav_button("Calendar", enabled=False),
            "Schedules": self._nav_button("Schedules", enabled=False),
        }
        self.view_calendar_button = self.nav_tabs["Calendar"]
        self.view_calendar_button.setEnabled(True)
        self.calendar_view = CalendarView(show_back_button=False)
        self.period_indexes_edit = QLineEdit()
        self.period_indexes_edit.setPlaceholderText("Optional, e.g. 0,1")

        self.max_systems_edit = QLineEdit()
        self.max_systems_edit.setPlaceholderText("No limit")
        self.max_systems_edit.setValidator(QIntValidator(1, 10_000_000, self))

        self.time_limit_edit = QLineEdit("30")
        self.time_limit_edit.setValidator(QIntValidator(1, 3600, self))
        self.time_limit_edit.setToolTip("Auto mode time limit in seconds.")

        self.run_button = QPushButton("Generate Schedules")
        self.run_button.setObjectName("primaryButton")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)

        self.program_selector = ProgramSelectionWidget()
        self.program_selection_count = QLabel(f"0/{MAX_SELECTED_PROGRAMS}")
        self.program_selection_count.setObjectName("programSelectionCount")
        self.program_selection_message = QLabel("")
        self.program_selection_message.setObjectName("programSelectionMessage")
        self.program_selection_message.setVisible(False)

        self.selected_programs_panel = SelectedProgramsPanel()

        self._build_layout()
        self._connect_signals()

    def set_running(self, running: bool) -> None:
        self.run_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        # Update the button text to serve as a clear, non-blocking progress indicator
        if running:
            self.run_button.setText("Generating Schedules...")
        else:
            self.run_button.setText("Generate Schedules")

    @property
    def exam_periods(self):
        return self._scheduler_input_state.exam_periods

    def set_exam_calendar_available(self, available: bool) -> None:
        self.view_calendar_button.setEnabled(True)

    def show_program_page(self) -> None:
        self._content_stack.setCurrentWidget(self._program_page)
        self._set_active_nav("Programs")

    def show_calendar_page(self) -> None:
        self._content_stack.setCurrentWidget(self.calendar_view)
        self._set_active_nav("Calendar")

    def is_calendar_page_visible(self) -> bool:
        return self._content_stack.currentWidget() is self.calendar_view

    def _build_layout(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_top_navigation())

        self._content_stack = QStackedWidget()
        self._program_page = self._build_program_page()
        self._content_stack.addWidget(self._program_page)
        # Calendar lives inside the input shell so the top menu does not jump between pages.
        self._content_stack.addWidget(self.calendar_view)
        root_layout.addWidget(self._content_stack, 1)

        self.run_button.setFixedWidth(220)
        self.run_button.setMinimumHeight(36)

        run_action_layout = QHBoxLayout()
        run_action_layout.setContentsMargins(28, 14, 28, 18)
        run_action_layout.addStretch(1)
        run_action_layout.addWidget(self.run_button)
        root_layout.addLayout(run_action_layout)

    def _build_program_page(self) -> QScrollArea:
        # Keep the main content scrollable so the submit button stays visible.
        scroll_area = QScrollArea()
        scroll_area.setObjectName("inputPanelScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(28, 28, 28, 24)
        content_layout.setSpacing(18)

        content_layout.addWidget(self._build_page_header())
        content_layout.addLayout(self._build_program_configuration_layout())
        content_layout.addStretch(1)

        scroll_area.setWidget(content)
        return scroll_area

    def _build_top_navigation(self) -> QWidget:
        # This is visual navigation for the new shell; routing can be added later.
        nav = QWidget()
        nav.setObjectName("topNavigation")
        layout = QHBoxLayout(nav)
        layout.setContentsMargins(22, 0, 22, 0)
        layout.setSpacing(12)

        back_label = QLabel("<")
        back_label.setObjectName("navBackLabel")
        layout.addWidget(back_label)

        title = QLabel("Exam Scheduler")
        title.setObjectName("navTitleLabel")
        layout.addWidget(title)
        layout.addStretch(1)

        for button in self.nav_tabs.values():
            layout.addWidget(button)

        return nav

    def _build_page_header(self) -> QWidget:
        header = QWidget()
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(6)

        title = QLabel("Program Configuration")
        title.setObjectName("screenTitle")
        subtitle = QLabel("Manage data sources and select target study programs for scheduling.")
        subtitle.setObjectName("pageSubtitleLabel")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        return header

    def _build_program_configuration_layout(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(22)

        file_card = self._section_card(self.file_loader)
        file_card.setMinimumWidth(390)
        file_card.setMaximumWidth(520)
        layout.addWidget(file_card, 1)
        layout.addWidget(self._build_study_programs_card(), 2)
        return layout

    def _build_study_programs_card(self) -> QWidget:
        card = QWidget()
        card.setObjectName("cardPanel")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 22)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("Study Programs")
        title.setObjectName("sectionTitleLabel")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.program_selection_count)
        layout.addLayout(header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(18)

        available = QWidget()
        available_layout = QVBoxLayout(available)
        available_layout.setContentsMargins(0, 0, 0, 0)
        available_layout.setSpacing(8)
        available_label = QLabel("Available Programs")
        available_label.setObjectName("paneTitle")
        available_layout.addWidget(available_label)
        available_layout.addWidget(self.program_selector)

        selected = QWidget()
        selected_layout = QVBoxLayout(selected)
        selected_layout.setContentsMargins(0, 0, 0, 0)
        selected_layout.setSpacing(8)
        selected_layout.addWidget(self.selected_programs_panel)

        body.addWidget(available, 1)
        body.addWidget(selected, 1)
        layout.addLayout(body)
        layout.addWidget(self.program_selection_message)
        return card

    @staticmethod
    def _section_card(widget: QWidget) -> QWidget:
        card = QWidget()
        card.setObjectName("cardPanel")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 22)
        layout.setSpacing(12)
        layout.addWidget(widget)
        return card

    def _connect_signals(self) -> None:
        self.file_loader.load_requested.connect(self._handle_data_load_requested)
        self.program_selector.programSelectionChanged.connect(self._store_selected_programs)
        self.program_selector.selectionCountChanged.connect(self._set_program_selection_count)
        self.program_selector.limitMessageChanged.connect(self._set_program_selection_message)
        self.run_button.clicked.connect(self._emit_run_requested)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        self.nav_tabs["Programs"].clicked.connect(self.show_program_page)
        self.view_calendar_button.clicked.connect(self.view_calendar_requested.emit)
        self.selected_programs_panel.program_detail_requested.connect(
            self._open_program_courses
        )

    def set_data_load_success(
            self,
            course_count: int,
            period_count: int,
            program_count: int,
            message: str | None = None,
    ) -> None:
        self.set_exam_calendar_available(True)
        self.file_loader.show_load_success(course_count, period_count, program_count, message)

    def set_data_load_error(self, message: str) -> None:
        self.set_exam_calendar_available(False)
        self.file_loader.show_load_error(message)

    def notify_data_loaded(self, loaded_data: LoadedSchedulerInput) -> None:

        self.selected_programs_vm.update_available_programs(loaded_data)
        self._scheduler_input_state.set_courses(loaded_data.courses)
        self._scheduler_input_state.set_exam_periods(loaded_data.exam_periods)
        self.set_exam_calendar_available(bool(self._scheduler_input_state.exam_periods))

        current_selected = self.program_selector.get_selected_program_ids()
        self.selected_programs_vm.set_selected_program_ids(current_selected)

        details = self.selected_programs_vm.get_selected_program_details()
        self.selected_programs_panel.update_display(details)

    def update_program_list(self, program_ids: list[str]) -> None:
        self.program_selector.add_programs(program_ids)

    def replace_program_list(self, program_ids: list[str]) -> None:
        self.program_selector.set_programs(program_ids)

    def _set_program_selection_message(self, message: str) -> None:
        self.program_selection_message.setText(message)
        self.program_selection_message.setVisible(bool(message))

    def _set_program_selection_count(self, selected_count: int, max_selected: int) -> None:
        self.program_selection_count.setText(f"{selected_count}/{max_selected}")

    def _store_selected_programs(self, program_ids: list[str]) -> None:
        self._scheduler_input_state.set_selected_programs(program_ids)
        self.selected_programs_vm.set_selected_program_ids(program_ids)
        details = self.selected_programs_vm.get_selected_program_details()
        self.selected_programs_panel.update_display(details)

    def _open_program_courses(self, program_id: str) -> None:
        try:
            from src.ui.program_courses_dialog import ProgramCoursesDialog

            courses = self.selected_programs_vm.get_courses_for_program(program_id)
            display_name = self.selected_programs_vm.get_program_display_name(program_id)

            dialog = ProgramCoursesDialog(
                program_id=program_id,
                display_name=display_name,
                courses=courses,
                parent=self,
            )
            dialog.exec()

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Error",
                f"Could not open courses dialog.\n\n{str(exc)}"
            )

    def exclude_calendar_day(self, period_index: int, day) -> None:
        # Calendar edits go through the same state object used to build scheduler input.
        self._exclude_calendar_day(period_index, day)

    def restore_calendar_day(self, period_index: int, day) -> None:
        # Restoring a date is the same state change as removing an exclusion from the file data.
        self._restore_calendar_day(period_index, day)

    def update_calendar_period_dates(self, period_index: int, start_date, end_date) -> None:
        # Date edits reshape the period, so the calendar must be rebuilt after this succeeds.
        self._set_period_dates(period_index, start_date, end_date)

    def _exclude_calendar_day(self, period_index: int, day) -> None:
        self._scheduler_input_state.exclude_day(period_index, day)

    def _restore_calendar_day(self, period_index: int, day) -> None:
        self._scheduler_input_state.restore_day(period_index, day)

    def _update_period_dates(self, period_index: int, start_date, end_date) -> None:
        try:
            self._set_period_dates(period_index, start_date, end_date)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid exam period dates", str(exc))

    def _set_period_dates(self, period_index: int, start_date, end_date) -> None:
        self._scheduler_input_state.update_period_dates(
            period_index,
            start_date,
            end_date,
        )

    def _handle_data_load_requested(
            self,
            courses_path: str,
            exam_dates_path: str,
            course_mode: str,
            exam_dates_mode: str,
    ) -> None:
        self.course_file_edit.setText(courses_path)
        self.dates_file_edit.setText(exam_dates_path)
        self.data_load_requested.emit(
            courses_path,
            exam_dates_path,
            course_mode,
            exam_dates_mode,
        )

    def _emit_run_requested(self) -> None:
        try:
            config = self._build_config()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid input", str(exc))
            return
        self.run_requested.emit(config)

    def _build_config(self) -> CliRunConfig:
        return self._run_config_builder.build(
            SchedulerRunForm(
                project_root=self._project_root,
                mode=self.mode_combo.currentText(),
                output_config_text=self.output_config_edit.text(),
                period_indexes_text=self.period_indexes_edit.text(),
                max_systems_text=self.max_systems_edit.text(),
                time_limit_text=self.time_limit_edit.text(),
                course_file_text=self.course_file_edit.text(),
                dates_file_text=self.dates_file_edit.text(),
            )
        )

    @staticmethod
    def _path_edit(path: Path) -> QLineEdit:
        edit = QLineEdit(str(path))
        edit.setMinimumWidth(420)
        edit.setToolTip(str(path))
        edit.setCursorPosition(0)
        return edit

    @staticmethod
    def _nav_button(
        label: str,
        active: bool = False,
        enabled: bool = True,
    ) -> QPushButton:
        button = QPushButton(label)
        button.setObjectName("navTabActive" if active else "navTab")
        button.setFlat(True)
        button.setEnabled(enabled)
        return button

    def _set_active_nav(self, active_label: str) -> None:
        for label, button in self.nav_tabs.items():
            button.setObjectName("navTabActive" if label == active_label else "navTab")
            button.style().unpolish(button)
            button.style().polish(button)
