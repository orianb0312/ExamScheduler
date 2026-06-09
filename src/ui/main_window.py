"""Main window for the standalone desktop UI."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget

from src.process_protocol import LAZY_NEXT_COMMAND, LAZY_STOP_COMMAND
from src.services.cli_run_service import CliRunConfig, resolve_cli_output_file
from src.services.file_loading_service import (
    FileLoadingError,
    FileLoadingService,
    LoadedSchedulerInput,
)
from src.services.schedule_calendar_service import ScheduleCalendarDataService
from src.services.schedule_output_service import (
    ScheduleOutputDataAdapter,
    ScheduleExamDisplay,
    ScheduleSystem,
    StdoutScheduleParser,
    parse_schedule_total,
)
from src.ui.calendar_view import OutputView
from src.ui.calendar_view_panel import CalendarView as ExamCalendarView
from src.ui.input_panel import InputPanel
from src.ui.process_runner import ProcessRunner
from src.ui.view_models import (
    ExamPeriodViewModel,
    ExclusionViewModel,
    ScheduledExamViewModel,
)


ProcessRunnerFactory = Callable[[object], ProcessRunner]


class MainWindow(QMainWindow):
    """Coordinate input controls, QProcess execution, and streamed output."""

    def __init__(
        self,
        project_root: Path,
        parent=None,
        process_runner_factory: ProcessRunnerFactory | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("ExamScheduler v2.0")
        self.resize(1200, 760)

        self._parser = StdoutScheduleParser()
        self._output_adapter = ScheduleOutputDataAdapter()
        self._calendar_data_service = ScheduleCalendarDataService()
        # Tests can inject a fake runner, while the real app still uses QProcess.
        runner_factory = process_runner_factory or ProcessRunner
        self._runner = runner_factory(self)
        self._file_loading_service = FileLoadingService()
        self._active_run_config: CliRunConfig | None = None
        self._selected_schedule: ScheduleSystem | None = None

        self.input_panel = InputPanel(project_root=project_root)
        self.calendar_view = ExamCalendarView()
        self.output_view = OutputView()
        self._stack = QStackedWidget()

        self._build_layout()
        self._connect_signals()
        self._load_stylesheet()

        self._set_default_baseline_programs()
        self._load_default_files_if_available()

    def _build_layout(self) -> None:
        self._stack.addWidget(self.input_panel)
        self._stack.addWidget(self.calendar_view)
        self._stack.addWidget(self.output_view)
        self.setCentralWidget(self._stack)

    def _connect_signals(self) -> None:
        self.input_panel.data_load_requested.connect(self._load_selected_files)
        self.input_panel.run_requested.connect(self._start_cli_run)
        self.input_panel.cancel_requested.connect(self._runner.cancel)
        self.input_panel.view_calendar_requested.connect(self._show_calendar_screen)
        self.calendar_view.back_requested.connect(self._show_input_screen)
        self.calendar_view.exclude_day_requested.connect(self._exclude_calendar_day)
        self.calendar_view.restore_day_requested.connect(self._restore_calendar_day)
        self.calendar_view.period_dates_changed.connect(self._update_period_dates)
        self.output_view.back_requested.connect(self._show_input_screen)
        self.output_view.more_requested.connect(self._request_next_schedule_batch)
        self.output_view.selected_schedule_changed.connect(self._set_selected_schedule)
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
            "83109", "83105", "83182", "83103", "83115",
        ]
        self.input_panel.update_program_list(default_baseline)

    def _load_default_files_if_available(self) -> None:
        # First, try to recover the last used paths from the internal data cache
        last_paths = self._file_loading_service.get_last_source_paths()
        courses_path = None
        exam_dates_path = None
        if last_paths:
            # Verify the cached paths actually still exist on the computer
            if last_paths[0].is_file() and last_paths[1].is_file():
                courses_path, exam_dates_path = last_paths
                # Populate the UI text fields so the user sees the paths from their last session
                self.input_panel.file_loader.set_courses_path(str(courses_path))
                self.input_panel.file_loader.set_exam_dates_path(str(exam_dates_path))

            # If we didn't get valid paths from the cache, fallback to UI defaults
        if not courses_path or not exam_dates_path:
            courses_path = Path(self.input_panel.file_loader.get_courses_path())
            exam_dates_path = Path(self.input_panel.file_loader.get_exam_dates_path())

        # If either path is invalid or missing, abort the auto-load process
        if not courses_path.is_file() or not exam_dates_path.is_file():
            return
        # Check if the files have changed since the last time they were saved
        is_stale = self._file_loading_service.is_cache_stale(courses_path, exam_dates_path)
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
        self._refresh_output_adapter(loaded_data)
        self.input_panel.set_exam_calendar_available(True)
        self.input_panel.notify_data_loaded(loaded_data)
        self._load_exam_period_calendar()
        # Notify the user clearly if a stale state was detected and resolved
        if is_stale:
            QMessageBox.information(
                self,
                "Data Reloaded",
                "The source files were modified since your last session.\n"
                "The application has automatically reloaded the newest data."
            )

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
        self._refresh_output_adapter(loaded_data)

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
        self._load_exam_period_calendar()

    def _load_exam_period_calendar(
        self,
        selected_period_index: int | None = None,
        selected_day=None,
    ) -> None:
        periods = self.input_panel.exam_periods
        period_view_models = self._build_schedule_period_view_models(
            self._selected_schedule
        )
        self.calendar_view.load_exam_periods(
            period_view_models,
            editable_periods=periods,
            selected_period_index=selected_period_index,
            selected_day=selected_day,
        )

    def _exclude_calendar_day(self, period_index: int, day) -> None:
        try:
            self.input_panel.exclude_calendar_day(period_index, day)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid calendar day", str(exc))
            return

        self._load_exam_period_calendar(
            selected_period_index=period_index,
            selected_day=day,
        )

    def _restore_calendar_day(self, period_index: int, day) -> None:
        try:
            self.input_panel.restore_calendar_day(period_index, day)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid calendar day", str(exc))
            return

        self._load_exam_period_calendar(
            selected_period_index=period_index,
            selected_day=day,
        )

    def _update_period_dates(self, period_index: int, start_date, end_date) -> None:
        try:
            self.input_panel.update_calendar_period_dates(
                period_index,
                start_date,
                end_date,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid exam period dates", str(exc))
            self._load_exam_period_calendar(selected_period_index=period_index)
            return

        self._load_exam_period_calendar(selected_period_index=period_index)

    def _start_cli_run(self, config: CliRunConfig) -> None:
        self._active_run_config = config
        self._refresh_output_adapter(self.loaded_input_data)
        self._parser.reset()
        self.output_view.clear()
        self.output_view.set_more_available(False)
        self._show_output_screen()
        self._runner.start(config)

    def _handle_started(self) -> None:
        self.input_panel.set_running(True)
        self.output_view.set_running(True)

    def _handle_stdout(self, text: str) -> None:
        schedule_total = parse_schedule_total(text)
        if schedule_total is not None:
            self.output_view.set_schedule_total(schedule_total)

        systems = self._output_adapter.convert(self._parser.feed(text))
        self.output_view.add_systems(systems)

        if (
            systems
            and self._active_run_config is not None
            and self._active_run_config.lazy_schedules
        ):
            self.output_view.set_stream_progress(self.output_view.cache.system_count)
            self.output_view.set_more_available(True)
        elif not _looks_like_schedule_output(text):
            self.output_view.append_log(text)

    def _handle_stderr(self, text: str) -> None:
        self.output_view.append_log(text)

    def _handle_finished(self, exit_code: int, status: str) -> None:
        self.output_view.add_systems(self._output_adapter.convert(self._parser.flush()))
        self.input_panel.set_running(False)
        self.output_view.set_more_available(False)
        if exit_code == 0:
            self.output_view.set_finished(exit_code, status)
            self._load_generated_output_file()
            if self.output_view.schedule_total is None and self.output_view.cache.system_count:
                self.output_view.set_schedule_total(self.output_view.cache.system_count)
            return

        self.output_view.set_error(
            f"Scheduler process exited with code {exit_code} ({status})."
        )

    def _handle_error(self, message: str) -> None:
        self.input_panel.set_running(False)
        self.output_view.set_more_available(False)
        self.output_view.set_error(message)

    def _request_next_schedule_batch(self) -> None:
        if self._active_run_config is None or not self._active_run_config.lazy_schedules:
            return

        self._runner.send_input_line(LAZY_NEXT_COMMAND)

    def _load_generated_output_file(self) -> None:
        config = self._active_run_config
        if config is None or config.mode == "complete-count":
            return
        if config.stream_schedules or config.lazy_schedules:
            return
        if self.output_view.cache.system_count:
            return

        output_path = resolve_cli_output_file(config)
        if not output_path.is_file():
            return

        # The CLI writes schedules to a file, so the UI reads that file after the run.
        parser = StdoutScheduleParser()
        try:
            with open(output_path, encoding="utf-8") as file:
                while chunk := file.read(64 * 1024):
                    self.output_view.add_systems(
                        self._output_adapter.convert(parser.feed(chunk))
                    )
        except OSError as exc:
            self.output_view.set_error(f"Could not load output file: {exc}")
            return

        self.output_view.add_systems(self._output_adapter.convert(parser.flush()))
        self.output_view.set_schedule_total(self.output_view.cache.system_count)

    def _refresh_output_adapter(self, loaded_data: LoadedSchedulerInput | None) -> None:
        courses = loaded_data.courses if loaded_data is not None else ()
        selected_program_ids = self.input_panel.program_selector.get_selected_program_ids()
        # Widgets receive adapted schedule rows, not raw scheduler text.
        self._output_adapter.update_course_catalog(courses, selected_program_ids)

    def _set_selected_schedule(self, schedule: ScheduleSystem | None) -> None:
        self._selected_schedule = schedule
        self.output_view.set_schedule_calendar(
            self._build_schedule_period_view_models(schedule)
        )
        if self._stack.currentWidget() is self.calendar_view:
            self._load_exam_period_calendar()

    def _build_schedule_period_view_models(
        self,
        schedule: ScheduleSystem | None,
    ) -> tuple[ExamPeriodViewModel, ...]:
        return tuple(
            ExamPeriodViewModel(
                semester_label=period.semester.value,
                term_label=period.term.value,
                start_date=period.start_date,
                end_date=period.end_date,
                exclusions=tuple(
                    ExclusionViewModel(
                        start_date=exclusion.start_date,
                        end_date=exclusion.end_date,
                    )
                    for exclusion in period.exclusions
                ),
                scheduled_exams=tuple(
                    _to_scheduled_exam_view_model(exam)
                    for exam in self._calendar_data_service.exams_for_period(
                        schedule,
                        period.semester.value,
                        period.term.value,
                        period.start_date,
                        period.end_date,
                    )
                ),
            )
            for period in self.input_panel.exam_periods
        )

    def _show_input_screen(self) -> None:
        if (
            self._active_run_config is not None
            and self._active_run_config.lazy_schedules
            and self._runner.is_running()
        ):
            self._runner.send_input_line(LAZY_STOP_COMMAND)
        self._stack.setCurrentWidget(self.input_panel)

    def _show_calendar_screen(self) -> None:
        self._load_exam_period_calendar()
        self._stack.setCurrentWidget(self.calendar_view)

    def _show_output_screen(self) -> None:
        self._stack.setCurrentWidget(self.output_view)

    def _load_stylesheet(self) -> None:
        stylesheet_path = Path(__file__).with_name("styles.qss")
        self.setStyleSheet(stylesheet_path.read_text(encoding="utf-8"))


def _to_scheduled_exam_view_model(exam: ScheduleExamDisplay) -> ScheduledExamViewModel:
    if exam.exam_date is None:
        raise ValueError("calendar exams must have a date")
    return ScheduledExamViewModel(
        course_name=exam.course_name,
        course_id=exam.course_id,
        exam_date=exam.exam_date,
        instructor=exam.instructor,
        program_ids=exam.program_ids,
        requirement_types=exam.requirement_types,
    )


def _looks_like_schedule_output(text: str) -> bool:
    return (
        "Complete System #" in text
        or "Schedule #" in text
        or "=== SEMESTER:" in text
        or "[TERM:" in text
    )

def _load_default_files_if_available(self) -> None:
    # First, try to recover the last used paths from the internal data cache
    last_paths = self._file_loading_service.get_last_source_paths()

    if last_paths:
        courses_path, exam_dates_path = last_paths
        # Populate the UI text fields so the user sees the paths from their last session
        self.input_panel.file_loader.set_courses_path(str(courses_path))
        self.input_panel.file_loader.set_exam_dates_path(str(exam_dates_path))
    else:
        # Fallback: get the paths currently written in the UI (which might be empty on startup)
        courses_path = Path(self.input_panel.file_loader.get_courses_path())
        exam_dates_path = Path(self.input_panel.file_loader.get_exam_dates_path())

    # If either path is invalid or missing, abort the auto-load process
    if not courses_path.is_file() or not exam_dates_path.is_file():
        return

    try:
        # Attempt to load the files (this will hit the cache first due to the internal logic)
        result = self._file_loading_service.load_selected_files(
            courses_path,
            exam_dates_path,
            "replace",
            "replace",
        )
    except FileLoadingError:
        # Abort if the files cannot be loaded or parsed
        return

    # Successfully loaded data; update the UI state and display the calendar
    loaded_data = result.loaded_data
    self._refresh_output_adapter(loaded_data)
    self.input_panel.set_exam_calendar_available(True)
    self.input_panel.notify_data_loaded(loaded_data)
    self._load_exam_period_calendar()
