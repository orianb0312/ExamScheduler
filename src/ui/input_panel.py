"""Main desktop input shell, top navigation menu, and run configuration UI."""

from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIntValidator, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
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
from src.services.dashboard_analytics_service import DashboardAnalyticsService
from src.services.scheduler_input_state import SchedulerInputState
from src.ui.ai_copilot_widget import AICopilotWidget
from src.ui.ai_copilot_worker import AICopilotWorker
from src.ui.calendar_view_panel import CalendarView
from src.ui.constraint_settings_widget import ConstraintSettingsWidget
from src.ui.dashboard_view import ExamSchedulerDashboard
from src.ui.file_loader_widget import FileLoaderWidget
from src.ui.program_selection_widget import MAX_SELECTED_PROGRAMS, ProgramSelectionWidget
from src.ui.selected_programs_panel import SelectedProgramsPanel
from src.services.selected_programs_service import SelectedProgramsViewModel


_MIN_COMPACT_LOWER_PANEL_HEIGHT = 144


class InputPanel(QWidget):
    """Compose the Stage 3 UI pages and emit application-level user intents.

    Widgets in this shell collect input and emit signals; they do not call the
    scheduler directly. MainWindow listens to those signals and coordinates
    services, QProcess execution, and result rendering.
    """

    run_requested = pyqtSignal(CliRunConfig)
    run_without_loaded_data_requested = pyqtSignal()
    cancel_requested = pyqtSignal()
    data_load_requested = pyqtSignal(str, str, str, str)
    view_calendar_requested = pyqtSignal()
    ai_constraint_requested = pyqtSignal(dict)
    dashboard_view_results_requested = pyqtSignal()
    dashboard_next_batch_requested = pyqtSignal()
    input_changed = pyqtSignal()

    def __init__(self, project_root: Path, parent=None) -> None:
        super().__init__(parent)
        self._project_root = project_root
        self._scheduler_input_state = SchedulerInputState(
            project_root / "outputs" / "ui_runtime"
        )
        self._run_config_builder = SchedulerRunConfigBuilder(self._scheduler_input_state)
        self._dashboard_analytics = DashboardAnalyticsService()
        self.selected_programs_vm = SelectedProgramsViewModel()
        self._has_loaded_input_data = False

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
            "Dashboard": self._nav_button("Dashboard"),
            "Programs": self._nav_button("Programs", active=True),
            "Calendar": self._nav_button("Calendar", enabled=False),
            "Settings": self._nav_button("Settings"),
            "Schedules": self._nav_button("Schedules", enabled=False),
        }
        self.view_calendar_button = self.nav_tabs["Calendar"]
        self.view_calendar_button.setEnabled(True)
        self.settings_button = self.nav_tabs["Settings"]
        self.ai_copilot = AICopilotWidget(self)
        self.analytics_dashboard = ExamSchedulerDashboard(self)
        self.analytics_dashboard.view_results_requested.connect(
            self.dashboard_view_results_requested.emit
        )
        self.analytics_dashboard.next_batch_requested.connect(
            self.dashboard_next_batch_requested.emit
        )
        self._ai_copilot_worker: AICopilotWorker | None = None
        self._ai_copilot_rules: dict[str, dict] = {}
        self._next_ai_copilot_rule_number = 1
        self._compact_dashboard_layout: bool | None = None
        self._compact_dashboard_height: bool | None = None
        self._schedules_page: QWidget | None = None
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
        self._set_run_footer_visible(True)

    def show_dashboard_page(self) -> None:
        self._content_stack.setCurrentWidget(self._dashboard_page)
        self._set_active_nav("Dashboard")
        self._set_run_footer_visible(False)

    def is_dashboard_page_visible(self) -> bool:
        return self._content_stack.currentWidget() is self._dashboard_page

    def show_calendar_page(self) -> None:
        self._content_stack.setCurrentWidget(self.calendar_view)
        self._set_active_nav("Calendar")
        self._set_run_footer_visible(False)

    def is_calendar_page_visible(self) -> bool:
        return self._content_stack.currentWidget() is self.calendar_view

    def show_settings_page(self) -> None:
        self._content_stack.setCurrentWidget(self.constraint_settings)
        self._set_active_nav("Settings")
        self._set_run_footer_visible(True)

    def is_settings_page_visible(self) -> bool:
        return self._content_stack.currentWidget() is self.constraint_settings

    def attach_schedules_page(self, schedules_page: QWidget) -> None:
        if self._schedules_page is schedules_page:
            return
        if self._schedules_page is not None:
            raise RuntimeError("Schedules page is already attached.")
        self._schedules_page = schedules_page
        self._content_stack.addWidget(schedules_page)

    def set_schedules_available(self, available: bool) -> None:
        self.nav_tabs["Schedules"].setEnabled(available)
        if not available and self.is_schedules_page_visible():
            self.show_program_page()

    def show_schedules_page(self) -> None:
        if self._schedules_page is None:
            return
        self.set_schedules_available(True)
        self._content_stack.setCurrentWidget(self._schedules_page)
        self._set_active_nav("Schedules")
        self._set_run_footer_visible(False)

    def is_schedules_page_visible(self) -> bool:
        return (
            self._schedules_page is not None
            and self._content_stack.currentWidget() is self._schedules_page
        )

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
        self.input_changed.emit()

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
        self._dashboard_page = self._build_dashboard_page()
        self._program_page = self._build_program_page()
        self._content_stack.addWidget(self._dashboard_page)
        self._content_stack.addWidget(self._program_page)
        # Calendar lives inside the input shell so the top menu does not jump between pages.
        self._content_stack.addWidget(self.calendar_view)
        # Settings shares the same shell so the top navigation stays consistent.
        self._content_stack.addWidget(self.constraint_settings)
        self._content_stack.setCurrentWidget(self._program_page)
        root_layout.addWidget(self._content_stack, 1)

        self.run_button.setMinimumWidth(190)
        self.run_button.setMinimumHeight(36)
        self.run_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self._run_action_layout = QHBoxLayout()
        self._run_action_layout.setContentsMargins(28, 14, 28, 18)
        self._run_action_layout.addStretch(1)
        self._run_action_layout.addWidget(self.run_button, 2)
        self._run_action_layout.addStretch(1)
        root_layout.addLayout(self._run_action_layout)

    def _build_dashboard_page(self) -> QScrollArea:
        scroll_area = QScrollArea()
        scroll_area.setObjectName("inputPanelScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.analytics_dashboard, 1)
        scroll_area.setWidget(content)
        return scroll_area

    def _build_program_page(self) -> QScrollArea:
        # Keep the main content scrollable so the submit button stays visible.
        scroll_area = QScrollArea()
        scroll_area.setObjectName("inputPanelScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self._program_content = QWidget()
        self._program_content_layout = QVBoxLayout(self._program_content)
        self._program_content_layout.setContentsMargins(28, 28, 28, 24)
        self._program_content_layout.setSpacing(18)

        self._program_header = self._build_page_header()
        self._program_content_layout.addWidget(self._program_header)
        self._program_configuration_layout = (
            self._build_program_configuration_layout()
        )
        self._program_page_lower_layout = self._build_program_page_lower_layout()
        self._program_content_layout.addLayout(
            self._program_configuration_layout
        )
        self._program_content_layout.addLayout(
            self._program_page_lower_layout,
            1,
        )

        scroll_area.setWidget(self._program_content)
        return scroll_area

    def _build_top_navigation(self) -> QWidget:
        # The SDD menu model lives here: one stable shell with page widgets
        # swapped underneath, so users do not lose context between tabs.
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
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            layout.addWidget(button, 1)

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

    def _build_program_configuration_layout(self) -> QGridLayout:
        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(22)

        self._file_card = self._section_card(self.file_loader)
        self._study_programs_card = self._build_study_programs_card()
        layout.addWidget(self._file_card, 0, 0)
        layout.addWidget(self._study_programs_card, 0, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 2)
        return layout

    def _build_program_page_lower_layout(self) -> QGridLayout:
        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(22)

        self._home_image_panel = self._build_home_image()
        self._copilot_card = self._section_card(self.ai_copilot)
        layout.addWidget(self._home_image_panel, 0, 0)
        layout.addWidget(self._copilot_card, 0, 1)
        layout.setColumnStretch(0, 3)
        layout.setColumnStretch(1, 2)
        return layout

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_responsive_dashboard_layout(
            event.size().width(),
            event.size().height(),
        )

    def _apply_responsive_dashboard_layout(
        self,
        width: int,
        height: int | None = None,
    ) -> None:
        if not hasattr(self, "_program_configuration_layout"):
            return

        compact = width < 1080
        if compact == self._compact_dashboard_layout:
            self._resize_lower_dashboard_panels(width, height, compact)
            return

        self._compact_dashboard_layout = compact
        for layout, widgets in (
            (
                self._program_configuration_layout,
                (self._file_card, self._study_programs_card),
            ),
            (
                self._program_page_lower_layout,
                (self._home_image_panel, self._copilot_card),
            ),
        ):
            for widget in widgets:
                layout.removeWidget(widget)

        if compact:
            self._program_configuration_layout.addWidget(
                self._file_card, 0, 0, 1, 2
            )
            self._program_configuration_layout.addWidget(
                self._study_programs_card, 1, 0, 1, 2
            )
            self._program_page_lower_layout.addWidget(
                self._home_image_panel, 0, 0, 1, 2
            )
            self._program_page_lower_layout.addWidget(
                self._copilot_card, 1, 0, 1, 2
            )
        else:
            self._program_configuration_layout.addWidget(
                self._file_card, 0, 0
            )
            self._program_configuration_layout.addWidget(
                self._study_programs_card, 0, 1
            )
            self._program_page_lower_layout.addWidget(
                self._home_image_panel, 0, 0
            )
            self._program_page_lower_layout.addWidget(
                self._copilot_card, 0, 1
            )

        self._resize_lower_dashboard_panels(width, height, compact)

    def _resize_lower_dashboard_panels(
        self,
        width: int,
        height: int | None,
        compact: bool,
    ) -> None:
        if not hasattr(self, "_home_image_panel"):
            return

        viewport_height = self._program_page.viewport().height()
        if viewport_height <= 0:
            viewport_height = height or self.height()

        compact_height = viewport_height < 760
        self._apply_dashboard_vertical_density(compact_height)

        if compact:
            # Stacked cards remain comfortably usable and the page scrolls when
            # the window is too short to show every section simultaneously.
            target_height = max(190, min(280, int(viewport_height * 0.34)))
        else:
            margins = self._program_content_layout.contentsMargins()
            spacing = self._program_content_layout.spacing()
            occupied_height = (
                margins.top()
                + margins.bottom()
                + self._program_header.sizeHint().height()
                + self._program_configuration_layout.sizeHint().height()
                + spacing * 2
            )
            remaining_height = viewport_height - occupied_height
            width_based_height = int(max(1, width - 56) * 0.18)
            target_height = max(
                _MIN_COMPACT_LOWER_PANEL_HEIGHT,
                min(
                    340,
                    max(0, remaining_height - 4),
                    width_based_height,
                ),
            )

        self._home_image_panel.set_responsive_height(target_height)
        self._copilot_card.setMinimumHeight(target_height)
        self._copilot_card.setMaximumHeight(target_height)
        card_vertical_margins = 27 if compact_height else 42
        self.ai_copilot.set_responsive_height(
            max(108, target_height - card_vertical_margins)
        )

    def _apply_dashboard_vertical_density(self, compact: bool) -> None:
        if compact == self._compact_dashboard_height:
            return
        self._compact_dashboard_height = compact

        card_margins = (16, 13, 16, 14) if compact else (22, 20, 22, 22)
        card_spacing = 8 if compact else 14
        for card in (self._file_card, self._study_programs_card):
            layout = card.layout()
            layout.setContentsMargins(*card_margins)
            layout.setSpacing(card_spacing)

        self.file_loader.set_compact_vertical(compact)
        self.program_selector.setMinimumHeight(140 if compact else 180)
        self.program_selector.setMaximumHeight(190 if compact else 260)
        self.selected_programs_panel.table.setMinimumHeight(
            150 if compact else 190
        )
        self.selected_programs_panel.layout().setContentsMargins(
            0,
            4 if compact else 10,
            0,
            4 if compact else 10,
        )

        self._program_configuration_layout.invalidate()
        self._program_content_layout.invalidate()
        self._program_content_layout.activate()

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
        self.nav_tabs["Dashboard"].clicked.connect(self.show_dashboard_page)
        self.nav_tabs["Programs"].clicked.connect(self.show_program_page)
        self.view_calendar_button.clicked.connect(self.view_calendar_requested.emit)
        self.settings_button.clicked.connect(self.show_settings_page)
        self.nav_tabs["Schedules"].clicked.connect(self.show_schedules_page)
        self.ai_copilot.message_submitted.connect(self._start_ai_copilot_worker)
        self.ai_copilot.constraint_generated.connect(
            self.ai_constraint_requested.emit
        )
        self.ai_copilot.clear_rules_requested.connect(
            self._confirm_clear_all_ai_copilot_rules
        )
        self.constraint_settings.settings_changed.connect(self._store_constraint_parameters)
        self.selected_programs_panel.program_detail_requested.connect(
            self._open_program_courses
        )

    def _set_run_footer_visible(self, visible: bool) -> None:
        self.run_button.setVisible(visible)
        if visible:
            self._run_action_layout.setContentsMargins(28, 14, 28, 18)
        else:
            self._run_action_layout.setContentsMargins(0, 0, 0, 0)

    def refresh_analytics_dashboard(
        self,
        schedule,
        current_batch_schedule=None,
        previous_best_schedule=None,
        active_priorities=(),
        *,
        total_schedules: int | None = None,
        current_page: int = 0,
        can_request_more: bool = False,
    ) -> None:
        snapshot = self._dashboard_analytics.build_snapshot(
            schedule,
            current_batch_schedule=current_batch_schedule,
            previous_best_schedule=previous_best_schedule,
            active_priorities=active_priorities,
            total_schedules=total_schedules,
            current_page=current_page,
        )
        self.analytics_dashboard.update_metrics(
            snapshot.total_schedules,
            snapshot.fitness_score,
            snapshot.min_study_gap,
            snapshot.current_batch_score,
        )
        self.analytics_dashboard.update_chart_data(
            snapshot.chart_dates,
            snapshot.chart_values,
        )
        self.analytics_dashboard.update_insights(
            snapshot.winning_text,
            snapshot.bottleneck_text,
        )
        self.analytics_dashboard.set_pagination(
            snapshot.chunk_number,
            snapshot.start_index,
            snapshot.end_index,
        )
        self.analytics_dashboard.set_action_state(
            has_results=schedule is not None,
            can_request_more=can_request_more,
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
            rule_id = constraint_payload.get("rule_id")
            if self._confirm_ai_rule_change(
                "Confirm AI rule removal",
                f"Remove {rule_id}?",
                constraint_payload,
            ):
                self._revert_ai_copilot_rule(rule_id)
            return

        if action == "clear_ai_rules":
            self._confirm_clear_all_ai_copilot_rules()
            return

        if action in AICopilotWorker.SUPPORTED_RULE_DEFINITIONS:
            parameters = {
                key: value
                for key, value in constraint_payload.items()
                if key != "action"
            }
            rule = {
                "description": self._describe_ai_copilot_rule(
                    action,
                    parameters,
                ),
                "rule_type": action,
                "parameters": parameters,
            }
            if self._confirm_ai_rule_change(
                "Confirm AI scheduling rule",
                rule["description"],
                constraint_payload,
            ):
                self._create_ai_copilot_rule(rule)
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

    def _confirm_ai_rule_change(
        self,
        title: str,
        summary: str,
        payload: dict,
    ) -> bool:
        # Unit-level calls use a hidden panel; real user submissions always
        # arrive through the visible application and require confirmation.
        if not self.isVisible():
            return True

        dialog = QDialog(self)
        dialog.setObjectName("aiRuleConfirmationDialog")
        dialog.setWindowTitle(title)
        dialog.setModal(True)
        dialog.resize(720, 420)

        layout = QVBoxLayout(dialog)
        summary_label = QLabel(summary)
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)

        diff_layout = QGridLayout()
        diff_layout.addWidget(QLabel("Current AI rules"), 0, 0)
        diff_layout.addWidget(QLabel("Proposed change"), 0, 1)

        current_view = QPlainTextEdit()
        current_view.setObjectName("aiRuleCurrentState")
        current_view.setReadOnly(True)
        current_view.setPlainText(
            json.dumps(
                self._ai_copilot_rules,
                ensure_ascii=False,
                indent=2,
            )
        )
        proposed_view = QPlainTextEdit()
        proposed_view.setObjectName("aiRuleProposedState")
        proposed_view.setReadOnly(True)
        proposed_view.setPlainText(
            json.dumps(payload, ensure_ascii=False, indent=2)
        )
        diff_layout.addWidget(current_view, 1, 0)
        diff_layout.addWidget(proposed_view, 1, 1)
        diff_layout.setColumnStretch(0, 1)
        diff_layout.setColumnStretch(1, 1)
        layout.addLayout(diff_layout, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        apply_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        apply_button.setText("Apply")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        return dialog.exec() == QDialog.DialogCode.Accepted

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
        if rule_type == "exclude_period":
            if "month" in parameters:
                month_names = (
                    "January",
                    "February",
                    "March",
                    "April",
                    "May",
                    "June",
                    "July",
                    "August",
                    "September",
                    "October",
                    "November",
                    "December",
                )
                period = month_names[int(parameters["month"]) - 1]
                if parameters.get("year"):
                    period = f'{period} {parameters["year"]}'
            else:
                period = (
                    f'{parameters.get("start_date", "start date")} through '
                    f'{parameters.get("end_date", "end date")}'
                )
            if parameters.get("lecturer"):
                return f'Exclude {period} for lecturer {parameters["lecturer"]}'
            if parameters.get("course"):
                return f'Exclude {period} for {parameters["course"]}'
            if parameters.get("program"):
                return f'Exclude {period} for program {parameters["program"]}'
            return f"Exclude {period} from exam scheduling"
        if rule_type == "lecturer_unavailable":
            day = (
                parameters.get("date")
                or parameters.get("weekday")
                or InputPanel._format_ai_month_day(parameters)
                or "day"
            )
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

    @staticmethod
    def _format_ai_month_day(parameters: dict) -> str | None:
        if "month" not in parameters or "day" not in parameters:
            return None
        month_names = (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        )
        try:
            month = month_names[int(parameters["month"]) - 1]
            day = int(parameters["day"])
        except (TypeError, ValueError, IndexError):
            return None
        value = f"{month} {day}"
        if parameters.get("year"):
            value = f'{value}, {parameters["year"]}'
        return value

    def _create_ai_copilot_rule(self, rule: dict) -> None:
        if not self._is_valid_ai_copilot_rule(rule):
            self._handle_ai_copilot_response(
                "The local model returned an invalid scheduling rule."
            )
            return

        description = rule.get("description")
        rule_type = rule.get("rule_type")
        parameters = rule.get("parameters")
        assert isinstance(description, str)
        assert isinstance(rule_type, str)
        assert isinstance(parameters, dict)

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
        self.ai_copilot.set_active_rules(self._ai_copilot_rules)
        persisted_rule = {"rule_id": rule_id, **stored_rule}
        self.ai_copilot.constraint_generated.emit(
            {
                "operation": "upsert",
                "rule": persisted_rule,
            }
        )
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
        self.ai_copilot.set_active_rules(self._ai_copilot_rules)
        self.ai_copilot.constraint_generated.emit(
            {
                "operation": "remove",
                "rule_id": rule_id,
            }
        )
        self.ai_copilot.append_message(
            "Copilot",
            f'Reverted {rule_id}: {removed_rule["description"]}',
            "#79d28a",
        )

    def restore_ai_copilot_rules(self, persisted_rules: list[dict]) -> None:
        """Restore validated chatbot-owned rules without re-emitting save events."""
        restored: dict[str, dict] = {}
        highest_rule_number = 0
        for record in persisted_rules:
            if not isinstance(record, dict):
                continue
            rule_id = record.get("rule_id")
            rule = {
                "description": record.get("description"),
                "rule_type": record.get("rule_type"),
                "parameters": record.get("parameters"),
            }
            if (
                not isinstance(rule_id, str)
                or AICopilotWorker._AI_RULE_ID_RE.fullmatch(rule_id) is None
                or not self._is_valid_ai_copilot_rule(rule)
                or rule_id in restored
            ):
                continue
            restored[rule_id] = {
                "description": str(rule["description"]).strip(),
                "rule_type": str(rule["rule_type"]),
                "parameters": dict(rule["parameters"]),
            }
            highest_rule_number = max(
                highest_rule_number,
                int(rule_id.removeprefix("ai_rule_")),
            )

        self._ai_copilot_rules = restored
        self._next_ai_copilot_rule_number = highest_rule_number + 1
        self.ai_copilot.set_active_rules(self._ai_copilot_rules)

    def _confirm_clear_all_ai_copilot_rules(self) -> None:
        if not self._ai_copilot_rules:
            return

        answer = QMessageBox.question(
            self,
            "Clear all AI rules",
            (
                f"Remove all {len(self._ai_copilot_rules)} AI-created rules?\n\n"
                "Base scheduling rules will not be changed."
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        cleared_count = len(self._ai_copilot_rules)
        self._ai_copilot_rules.clear()
        self._next_ai_copilot_rule_number = 1
        self.ai_copilot.set_active_rules(self._ai_copilot_rules)
        self.ai_copilot.constraint_generated.emit({"operation": "clear"})
        self.ai_copilot.append_message(
            "Copilot",
            f"Cleared {cleared_count} AI-created rules. Base rules were preserved.",
            "#79d28a",
        )

    @staticmethod
    def _is_valid_ai_copilot_rule(rule: dict) -> bool:
        description = rule.get("description")
        rule_type = rule.get("rule_type")
        parameters = rule.get("parameters")
        return (
            isinstance(description, str)
            and bool(description.strip())
            and AICopilotWorker._is_english_code_text(description)
            and isinstance(rule_type, str)
            and AICopilotWorker._RULE_TYPE_RE.fullmatch(rule_type) is not None
            and rule_type in AICopilotWorker.SUPPORTED_RULE_DEFINITIONS
            and isinstance(parameters, dict)
            and AICopilotWorker._json_strings_are_english(parameters)
            and AICopilotWorker._parameters_match_supported_rule(
                rule_type,
                parameters,
            )
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
        self._has_loaded_input_data = False
        self.set_exam_calendar_available(False)
        self.file_loader.show_load_error(message)

    def notify_data_loaded(self, loaded_data: LoadedSchedulerInput) -> None:
        self._has_loaded_input_data = True

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
        self.input_changed.emit()

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
        self.input_changed.emit()

    def restore_calendar_day(self, period_index: int, day) -> None:
        # Restoring a date is the same state change as removing an exclusion from the file data.
        self._restore_calendar_day(period_index, day)
        self.input_changed.emit()

    def update_calendar_period_dates(self, period_index: int, start_date, end_date) -> None:
        # Date edits reshape the period, so the calendar must be rebuilt after this succeeds.
        self._set_period_dates(period_index, start_date, end_date)
        self.input_changed.emit()

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
        if not self._has_loaded_input_data:
            self.run_without_loaded_data_requested.emit()
            return

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
        button.setMinimumWidth(0)
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
        self.setMinimumHeight(180)
        self.setMaximumHeight(340)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._pixmap = QPixmap(str(image_path))

    def set_responsive_height(self, height: int) -> None:
        target_height = max(
            _MIN_COMPACT_LOWER_PANEL_HEIGHT,
            min(340, height),
        )
        self.setMinimumHeight(target_height)
        self.setMaximumHeight(target_height)

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
