# src/ui/input_panel.py
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.services.cli_run_service import (
    CliRunConfig,
    SchedulerRunConfigBuilder,
    SchedulerRunForm,
)
from src.services.scheduler_input_state import SchedulerInputState
from src.ui.file_loader_widget import FileLoaderWidget
from src.ui.program_selection_widget import MAX_SELECTED_PROGRAMS, ProgramSelectionWidget
from src.ui.selected_programs_panel import SelectedProgramsPanel
from src.services.selected_programs_service import SelectedProgramsViewModel


class InputPanel(QWidget):
    """Collect file paths and CLI options without importing v1 code."""

    run_requested = pyqtSignal(CliRunConfig)
    cancel_requested = pyqtSignal()
    data_load_requested = pyqtSignal(str, str, str, str)

    def __init__(self, project_root: Path, parent=None) -> None:
        super().__init__(parent)
        self._project_root = project_root
        self._scheduler_input_state = SchedulerInputState(
            project_root / "outputs" / "ui_runtime"
        )
        self._run_config_builder = SchedulerRunConfigBuilder(self._scheduler_input_state)

        # Initialize the state management ViewModel for selected programs
        self.selected_programs_vm = SelectedProgramsViewModel()

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["complete-count", "period", "complete-write", "auto"])

        self.output_config_edit = self._path_edit(project_root / "config.json")
        self.course_file_edit = self._path_edit(project_root / "data" / "V1.0CourseDB.txt")
        self.dates_file_edit = self._path_edit(project_root / "data" / "V1.0 ExamDates.txt")
        self.user_file_edit = self._path_edit(project_root / "data" / "Programs.txt")
        self.file_loader = FileLoaderWidget()
        self.file_loader.set_courses_path(self.course_file_edit.text())
        self.file_loader.set_exam_dates_path(self.dates_file_edit.text())
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

        # Initialize the read-only details UI sub-panel
        self.selected_programs_panel = SelectedProgramsPanel()

        self._build_layout()
        self._connect_signals()

    def set_running(self, running: bool) -> None:
        self.run_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)

    def _build_layout(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(28, 24, 28, 24)
        root_layout.setSpacing(18)
        title = QLabel("Exam Scheduler")
        title.setObjectName("screenTitle")
        root_layout.addWidget(title)
        root_layout.addWidget(self.file_loader)
        root_layout.addWidget(self.program_selection_count)
        root_layout.addWidget(self.program_selector)
        
        # Inject the read-only details panel beneath the selection widget
        root_layout.addWidget(self.selected_programs_panel)
        
        root_layout.addWidget(self.program_selection_message)
        self.run_button.setFixedWidth(220)
        self.run_button.setMinimumHeight(36)

        run_action_layout = QHBoxLayout()
        run_action_layout.setContentsMargins(0, 0, 0, 0)
        run_action_layout.addStretch(1)
        run_action_layout.addWidget(self.run_button)
        root_layout.addLayout(run_action_layout)
        root_layout.addStretch()

    def _connect_signals(self) -> None:
        self.file_loader.load_requested.connect(self._handle_data_load_requested)
        self.program_selector.programSelectionChanged.connect(self._store_selected_programs)
        self.program_selector.selectionCountChanged.connect(self._set_program_selection_count)
        self.program_selector.limitMessageChanged.connect(self._set_program_selection_message)
        self.run_button.clicked.connect(self._emit_run_requested)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)

    def set_data_load_success(
        self,
        course_count: int,
        period_count: int,
        program_count: int,
        message: str | None = None,
    ) -> None:
        self.file_loader.show_load_success(course_count, period_count, program_count, message)

    def set_data_load_error(self, message: str) -> None:
        self.file_loader.show_load_error(message)

    def update_program_list(self, program_ids: list[str]) -> None:
        """Forwards the resolved program ID list to the selection widget."""
        self.program_selector.add_programs(program_ids)

    def replace_program_list(self, program_ids: list[str]) -> None:
        """Replaces the visible program ID list in the selection widget."""
        self.program_selector.set_programs(program_ids)

    def _set_program_selection_message(self, message: str) -> None:
        self.program_selection_message.setText(message)
        self.program_selection_message.setVisible(bool(message))

    def _set_program_selection_count(self, selected_count: int, max_selected: int) -> None:
        self.program_selection_count.setText(f"{selected_count}/{max_selected}")

    def _store_selected_programs(self, program_ids: list[str]) -> None:
        """Saves current selection to state and triggers a pipeline view refresh."""
        self._scheduler_input_state.set_selected_programs(program_ids)
        
        # Synchronize UI selection with business logic layer and refresh read-only display
        self.selected_programs_vm.set_selected_program_ids(program_ids)
        details = self.selected_programs_vm.get_selected_program_details()
        self.selected_programs_panel.update_display(details)

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