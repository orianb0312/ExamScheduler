from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIntValidator, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.services.cli_run_service import (
    CliRunConfig,
    SchedulerRunConfigBuilder,
    SchedulerRunForm,
)
from src.services.constraint_settings_policy import (
    CONSTRAINTS_BY_KEY,
    ConstraintValidation,
)
from src.services.file_loading_service import LoadedSchedulerInput
from src.services.scheduler_input_state import SchedulerInputState
from src.ui.ai_copilot_widget import AICopilotWidget
from src.ui.ai_copilot_worker import AICopilotWorker
from src.ui.calendar_view_panel import CalendarView
from src.ui.constraint_settings_widget import ConstraintSettingsWidget
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
            "Settings": self._nav_button("Settings"),
            "Schedules": self._nav_button("Schedules", enabled=False),
        }
        self.view_calendar_button = self.nav_tabs["Calendar"]
        self.view_calendar_button.setEnabled(True)
        self.settings_button = self.nav_tabs["Settings"]
        self.ai_copilot = AICopilotWidget()
        self._ai_copilot_worker: AICopilotWorker | None = None
        self._ai_copilot_rules: dict[str, dict] = {}
        self._next_ai_copilot_rule_number = 1
        self.calendar_view = CalendarView(show_back_button=False)
        self.constraint_settings = ConstraintSettingsWidget()
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

    def show_settings_page(self) -> None:
        self._content_stack.setCurrentWidget(self.constraint_settings)
        self._set_active_nav("Settings")

    def is_settings_page_visible(self) -> bool:
        return self._content_stack.currentWidget() is self.constraint_settings

    @property
    def constraint_parameters(self) -> dict[str, int]:
        """The current enabled-and-valid constraint values held in the state.

        Mirrors how selected programs are exposed: the UI streams every change
        into the state, so this always reflects the latest valid selection.
        """
        return self._scheduler_input_state.constraints

    def _store_constraint_parameters(self, parameters: dict) -> None:
        # Every valid change flows straight into the state, exactly like the
        # program selector. The runtime file is written later, at generate time.
        self._scheduler_input_state.set_constraints(parameters)

    @property
    def ai_copilot_rules(self) -> dict[str, dict]:
        return {
            rule_id: dict(rule)
            for rule_id, rule in self._ai_copilot_rules.items()
        }

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
        # Settings shares the same shell so the top navigation stays consistent.
        self._content_stack.addWidget(self.constraint_settings)
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
        content_layout.addLayout(self._build_program_page_lower_layout(), 1)

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

    def _build_home_image(self) -> QWidget:
        image_path = Path(__file__).with_name("assets") / "exam_scheduler_logo.png"
        return _HomeImagePanel(image_path)

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

    def _build_program_page_lower_layout(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(22)

        copilot_card = self._section_card(self.ai_copilot)
        copilot_card.setMinimumWidth(360)
        copilot_card.setMaximumWidth(480)

        layout.addWidget(self._build_home_image(), 3)
        layout.addWidget(copilot_card, 2)
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
        self.settings_button.clicked.connect(self.show_settings_page)
        self.ai_copilot.message_submitted.connect(self._start_ai_copilot_worker)
        self.constraint_settings.settings_changed.connect(self._store_constraint_parameters)
        self.selected_programs_panel.program_detail_requested.connect(
            self._open_program_courses
        )

    def _start_ai_copilot_worker(self, user_text: str) -> None:
        if self._ai_copilot_worker is not None and self._ai_copilot_worker.isRunning():
            self.ai_copilot.append_message(
                "Copilot",
                "Please wait for the current response to finish.",
                "#ffcf66",
            )
            return

        self.ai_copilot.set_processing(True)
        self.ai_copilot.append_message("Copilot", "Processing request...", "#79d28a")

        self._ai_copilot_worker = AICopilotWorker(
            user_text,
            self,
            existing_constraints=self.constraint_parameters,
            chatbot_rules=self._ai_copilot_rules,
            security_log_path=self._project_root / "security_log.txt",
        )
        self._ai_copilot_worker.constraint_ready.connect(
            self._handle_ai_copilot_constraint
        )
        self._ai_copilot_worker.response_ready.connect(
            self._handle_ai_copilot_response
        )
        self._ai_copilot_worker.finished.connect(
            self._finish_ai_copilot_worker
        )
        self._ai_copilot_worker.start()

    def _handle_ai_copilot_response(self, response_text: str) -> None:
        self.ai_copilot.append_message("Copilot", response_text, "#ff8f88")

    def _handle_ai_copilot_constraint(self, constraint_payload: dict) -> None:
        action = constraint_payload.get("action")
        if action == "system_inquiry":
            self._handle_ai_copilot_inquiry(constraint_payload.get("topic"))
            return

        if action == "already_active":
            self.ai_copilot.append_message(
                "Copilot",
                "That scheduling rule is already active.",
                "#79d28a",
            )
            return

        if action == "clarify":
            message = constraint_payload.get("message")
            if isinstance(message, str):
                self.ai_copilot.append_message(
                    "Copilot",
                    message,
                    "#79d28a",
                )
            else:
                self._handle_ai_copilot_response(
                    AICopilotWorker.GENERIC_FALLBACK_MESSAGE
                )
            return

        if action == "revert_rule":
            self._revert_ai_copilot_rule(constraint_payload.get("rule_id"))
            return

        if action in AICopilotWorker.SUPPORTED_RULE_DEFINITIONS:
            parameters = {
                key: value
                for key, value in constraint_payload.items()
                if key != "action"
            }
            self._create_ai_copilot_rule(
                {
                    "description": self._describe_ai_copilot_rule(
                        action,
                        parameters,
                    ),
                    "rule_type": action,
                    "parameters": parameters,
                }
            )
            return

        self._handle_ai_copilot_response(
            "The local model returned an unsupported rule action."
        )

    def _handle_ai_copilot_inquiry(self, topic) -> None:
        if topic == "supported_rules":
            names = ", ".join(
                definition["name"]
                for definition in AICopilotWorker.SUPPORTED_RULE_DEFINITIONS.values()
            )
            message = f"Supported scheduling rules: {names}."
        elif topic == "active_ai_rules":
            if not self._ai_copilot_rules:
                message = "There are no active AI-created rules."
            else:
                entries = [
                    f'{rule_id}: {rule["description"]}'
                    for rule_id, rule in self._ai_copilot_rules.items()
                ]
                message = "Active AI-created rules: " + "; ".join(entries)
        elif topic == "base_rules":
            message = (
                "Base scheduling rules are read-only and cannot be reverted "
                "or overridden by the chatbot."
            )
        else:
            self._handle_ai_copilot_response(
                "The local model returned an unsupported system inquiry."
            )
            return

        self.ai_copilot.append_message("Copilot", message, "#79d28a")

    @staticmethod
    def _describe_ai_copilot_rule(
        rule_type: str,
        parameters: dict,
    ) -> str:
        if rule_type == "fix_date":
            return (
                f'Fix {parameters.get("course", "course")} on '
                f'{parameters.get("date", "date")}'
            )
        if rule_type == "exclude_day":
            day = parameters.get("date") or parameters.get("weekday") or "day"
            course = parameters.get("course")
            return (
                f"Exclude {day} for {course}"
                if course
                else f"Exclude {day} from exam scheduling"
            )
        if rule_type == "lecturer_unavailable":
            day = parameters.get("date") or parameters.get("weekday") or "day"
            return (
                f'Lecturer {parameters.get("lecturer", "unknown")} '
                f"unavailable on {day}"
            )
        if rule_type == "program_limit":
            return (
                f'Limit {parameters.get("program", "program")} to '
                f'{parameters.get("max_exams_per_day", "N")} exams per day'
            )
        if rule_type == "exam_spacing":
            return (
                f'Minimum {parameters.get("min_days", "N")} days between exams'
            )
        return "AI-created scheduling rule"

    def _create_ai_copilot_rule(self, rule: dict) -> None:
        description = rule.get("description")
        rule_type = rule.get("rule_type")
        parameters = rule.get("parameters")
        if (
            not isinstance(description, str)
            or not description.strip()
            or not AICopilotWorker._is_english_code_text(description)
            or not isinstance(rule_type, str)
            or AICopilotWorker._RULE_TYPE_RE.fullmatch(rule_type) is None
            or rule_type not in AICopilotWorker.SUPPORTED_RULE_DEFINITIONS
            or not isinstance(parameters, dict)
            or not AICopilotWorker._json_strings_are_english(parameters)
            or not AICopilotWorker._parameters_match_supported_rule(
                rule_type,
                parameters,
            )
        ):
            self._handle_ai_copilot_response(
                "The local model returned an invalid scheduling rule."
            )
            return

        normalized_description = AICopilotWorker._normalize_for_comparison(
            description
        )
        if any(
            AICopilotWorker._normalize_for_comparison(
                str(existing.get("description", ""))
            )
            == normalized_description
            for existing in self._ai_copilot_rules.values()
        ):
            self._handle_ai_copilot_response(
                "That chatbot rule already exists."
            )
            return

        rule_id = f"ai_rule_{self._next_ai_copilot_rule_number}"
        self._next_ai_copilot_rule_number += 1
        stored_rule = {
            "description": description.strip(),
            "rule_type": rule_type,
            "parameters": dict(parameters),
        }
        self._ai_copilot_rules[rule_id] = stored_rule
        self.ai_copilot.append_message(
            "Copilot",
            f'Created {rule_id}: {stored_rule["description"]}',
            "#79d28a",
        )

    def _revert_ai_copilot_rule(self, rule_id) -> None:
        if not isinstance(rule_id, str) or rule_id not in self._ai_copilot_rules:
            self._handle_ai_copilot_response(
                "Only rules created by this chatbot can be reverted."
            )
            return

        removed_rule = self._ai_copilot_rules.pop(rule_id)
        self.ai_copilot.append_message(
            "Copilot",
            f'Reverted {rule_id}: {removed_rule["description"]}',
            "#79d28a",
        )

    def _finish_ai_copilot_worker(self) -> None:
        self.ai_copilot.set_processing(False)
        if self._ai_copilot_worker is None:
            return

        self._ai_copilot_worker.deleteLater()
        self._ai_copilot_worker = None

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
        # Constraint errors are part of the run form, so check them before building files.
        if not self._validate_constraints_before_run():
            return
        try:
            config = self._build_config()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid input", str(exc))
            return
        self.run_requested.emit(config)

    def _validate_constraints_before_run(self) -> bool:
        validation = self.constraint_settings.validate()
        if validation.is_valid:
            return True

        # Invalid enabled constraints must stop generation instead of being
        # quietly dropped from the runtime file.
        self.show_settings_page()
        title, message = _format_constraint_validation_warning(validation)
        QMessageBox.warning(
            self,
            title,
            message,
        )
        return False

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


class _HomeImagePanel(QFrame):
    """Responsive lower-page image panel that keeps branding polished."""

    _MAX_IMAGE_WIDTH = 1040
    _MAX_IMAGE_HEIGHT = 320

    def __init__(self, image_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("homeImagePanel")
        self.setMinimumHeight(300)
        self.setMaximumHeight(360)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._pixmap = QPixmap(str(image_path))

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._pixmap.isNull():
            return

        target = self.contentsRect()
        if target.isEmpty():
            return

        available = QSize(
            min(target.width(), self._MAX_IMAGE_WIDTH),
            min(target.height(), self._MAX_IMAGE_HEIGHT),
        )
        scaled = self._pixmap.scaled(
            available,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        destination = QRect(
            target.x() + max(0, (target.width() - scaled.width()) // 2),
            target.y() + max(0, (target.height() - scaled.height()) // 2),
            scaled.width(),
            scaled.height(),
        )

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawPixmap(destination, scaled)


def _format_constraint_validation_warning(
    validation: ConstraintValidation,
) -> tuple[str, str]:
    # Turn policy-level errors into messages a scheduler user can act on.
    problems = [
        _format_constraint_problem(result.key, result.error)
        for result in validation.results
        if result.error is not None
    ]

    # A single bad field gets a direct sentence instead of a bulky list.
    if len(problems) == 1:
        return (
            "Invalid constraint value",
            f"{problems[0]} Fix it before generating schedules.",
        )

    # Several bad fields are shown together so the user can fix them in one visit.
    return (
        "Invalid constraint values",
        "Fix these constraint settings before generating schedules:\n\n"
        + "\n".join(f"- {problem}" for problem in problems),
    )


def _format_constraint_problem(key: str, error: str | None) -> str:
    # Use the friendly title from the shared constraint definition.
    definition = CONSTRAINTS_BY_KEY.get(key)
    title = definition.title if definition else key
    clean_error = (error or "Invalid value.").strip().rstrip(".")

    # Keep required-value errors short and specific.
    if clean_error == "A value is required when this constraint is enabled":
        return f'The value in "{title}" is required.'

    # The policy already knows whether the value must be positive or non-negative.
    if clean_error.startswith("Value must be "):
        requirement = clean_error.removeprefix("Value must be ")
        return f'The value in "{title}" must be {requirement}.'

    return f'The value in "{title}" is invalid: {clean_error}.'
