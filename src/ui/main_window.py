"""Main window for the standalone desktop UI."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QMainWindow, QStackedWidget

from src.services.cli_run_service import CliRunConfig
from src.services.file_loading_service import (
    FileLoadingError,
    FileLoadingService,
    LoadedSchedulerInput,
)
from src.services.schedule_output_service import StdoutScheduleParser
from src.ui.calendar_view import CalendarView
from src.ui.input_panel import InputPanel
from src.ui.process_runner import ProcessRunner


class MainWindow(QMainWindow):
    """Coordinate input controls, QProcess execution, and streamed output."""

    def __init__(self, project_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ExamScheduler v2.0")
        self.resize(1200, 760)

        self._parser = StdoutScheduleParser()
        self._runner = ProcessRunner(self)
        self._file_loading_service = FileLoadingService()

        self.input_panel = InputPanel(project_root=project_root)
        self.calendar_view = CalendarView()
        self._stack = QStackedWidget()

        self._build_layout()
        self._connect_signals()
        self._load_stylesheet()

        self._set_default_baseline_programs()
        self._load_default_files_if_available()

    def _build_layout(self) -> None:
        self._stack.addWidget(self.input_panel)
        self._stack.addWidget(self.calendar_view)
        self.setCentralWidget(self._stack)

    def _connect_signals(self) -> None:
        self.input_panel.data_load_requested.connect(self._load_selected_files)
        self.input_panel.run_requested.connect(self._start_cli_run)
        self.input_panel.cancel_requested.connect(self._runner.cancel)
        self.calendar_view.back_requested.connect(self._show_input_screen)
        self._runner.process_started.connect(self._handle_started)
        self._runner.stdout_received.connect(self._handle_stdout)
        self._runner.stderr_received.connect(self._handle_stderr)
        self._runner.process_finished.connect(self._handle_finished)
        self._runner.process_error.connect(self._handle_error)

    @property
    def loaded_input_data(self) -> LoadedSchedulerInput | None:
        return self._file_loading_service.loaded_data

    def _set_default_baseline_programs(self) -> None:
        """Populates the input panel selection view with the standard initial programs."""
        default_baseline = [
            "83101", "83102", "83104", "83107", "83108",
            "83109", "83105", "83182", "83103", "83115"
        ]
        self.input_panel.update_program_list(default_baseline)

    def _load_default_files_if_available(self) -> None:
        courses_path = Path(self.input_panel.file_loader.get_courses_path())
        exam_dates_path = Path(self.input_panel.file_loader.get_exam_dates_path())

        if not courses_path.is_file() or not exam_dates_path.is_file():
            return

        try:
            result = self._file_loading_service.load_selected_files(
                courses_path,
                exam_dates_path,
                "replace",
                "replace",
            )
        except FileLoadingError:
            return

        loaded_data = result.loaded_data
        self.input_panel.notify_data_loaded(loaded_data)

    def _load_selected_files(
            self,
            courses_path: str,
            exam_dates_path: str,
            course_mode: str,
            exam_dates_mode: str,
    ) -> None:
        try:
            result = self._file_loading_service.load_selected_files(
                courses_path,
                exam_dates_path,
                course_mode,
                exam_dates_mode,
            )
        except FileLoadingError as exc:
            self.input_panel.set_data_load_error(str(exc))
            return

        loaded_data = result.loaded_data

        self.input_panel.set_data_load_success(
            loaded_data.course_count,
            loaded_data.exam_period_count,
            loaded_data.program_count,
            result.message,
        )

        resolved_ids = loaded_data.program_ids_as_strings or []

        if course_mode == "update":
            self.input_panel.update_program_list(resolved_ids)
        else:
            self.input_panel.replace_program_list(resolved_ids)

        self.input_panel.notify_data_loaded(loaded_data)

    def _start_cli_run(self, config: CliRunConfig) -> None:
        self._parser.reset()
        self.calendar_view.clear()
        self._show_output_screen()
        self._runner.start(config)

    def _handle_started(self) -> None:
        self.input_panel.set_running(True)
        self.calendar_view.set_running(True)

    def _handle_stdout(self, text: str) -> None:
        self.calendar_view.append_log(text)
        self.calendar_view.add_systems(self._parser.feed(text))

    def _handle_stderr(self, text: str) -> None:
        self.calendar_view.append_log(text)

    def _handle_finished(self, exit_code: int, status: str) -> None:
        self.calendar_view.add_systems(self._parser.flush())
        self.input_panel.set_running(False)
        self.calendar_view.set_finished(exit_code, status)

    def _handle_error(self, message: str) -> None:
        self.input_panel.set_running(False)
        self.calendar_view.set_error(message)

    def _show_input_screen(self) -> None:
        self._stack.setCurrentWidget(self.input_panel)

    def _show_output_screen(self) -> None:
        self._stack.setCurrentWidget(self.calendar_view)

    def _load_stylesheet(self) -> None:
        stylesheet_path = Path(__file__).with_name("styles.qss")
        self.setStyleSheet(stylesheet_path.read_text(encoding="utf-8"))
