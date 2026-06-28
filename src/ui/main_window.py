"""Main window for the standalone desktop UI."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QFileDialog, QMainWindow, QMessageBox, QStackedWidget

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
from src.services.selected_schedule_analytics_writer import SelectedScheduleAnalyticsWriter
from src.services.selected_schedule_file_writer import SelectedScheduleFileWriter
from src.ui.calendar_view import OutputView
from src.ui.input_panel import InputPanel
from src.ui.process_runner import ProcessRunner
from src.ui.toast_notification import ToastNotification
from src.ui.view_models import (
    ExamPeriodViewModel,
    ExclusionViewModel,
    ScheduledExamViewModel,
)
from src.services.schedule_calendar_export_service import (
    CalendarExportError,
    CalendarExportResult,
    ScheduleCalendarExportService,
)
from src.ui.loading_view import LoadingView

NO_EXAM_SCHEDULES_MESSAGE = (
    "No exam schedules were generated for the selected programs. "
    "Check that the selected courses include exam assessments."
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
        self.setMinimumSize(820, 620)

        self._project_root = Path(project_root)
        self._active_ai_rules_file = (
            self._project_root / "data" / "active_ai_rules.json"
        ).resolve()
        self._parser = StdoutScheduleParser()
        self._output_adapter = ScheduleOutputDataAdapter()
        self._calendar_data_service = ScheduleCalendarDataService()
        self._selected_schedule_writer = SelectedScheduleFileWriter()
        self._selected_schedule_analytics_writer = SelectedScheduleAnalyticsWriter()
        # Tests can inject a fake runner, while the real app still uses QProcess.
        runner_factory = process_runner_factory or ProcessRunner
        self._runner = runner_factory(self)
        self._file_loading_service = FileLoadingService()
        self._active_run_config: CliRunConfig | None = None
        self._selected_schedule: ScheduleSystem | None = None
        self._stay_on_input_after_lazy_stop = False
        self._ignore_stale_runner_result = False
        self._pending_run_after_stale_stop: CliRunConfig | None = None

        self.input_panel = InputPanel(project_root=project_root)
        self.calendar_view = self.input_panel.calendar_view
        self.output_view = OutputView()
        self.loading_view = LoadingView()
        self._stack = QStackedWidget()

        self._build_layout()
        self._toast = ToastNotification(self)
        self._connect_signals()
        self._initialize_active_ai_rules()
        self._load_stylesheet()

        self._set_default_baseline_programs()
        # Manage calendar exports, cancellation files, and export history.
        # The service persists exported events so future cancellation files
        # can target the correct calendar UIDs.
        self._calendar_export_service = ScheduleCalendarExportService(
            self._project_root / ".exam_scheduler_cache" / "calendar"
        )
        self._sync_calendar_revoke_all_button()

        self._load_default_files_if_available()

    def show_resizable_maximized(self) -> None:
        """Start full-size while retaining normal restore and resize controls."""
        self.showMaximized()

    def _build_layout(self) -> None:
        self.input_panel.attach_schedules_page(self.output_view)
        self._stack.addWidget(self.input_panel)
        self._stack.addWidget(self.loading_view)
        self.setCentralWidget(self._stack)

    def _connect_signals(self) -> None:
        self.input_panel.data_load_requested.connect(self._load_selected_files)
        self.input_panel.run_requested.connect(self._start_cli_run)
        self.input_panel.cancel_requested.connect(self._cancel_process)
        self.input_panel.input_changed.connect(
            self._stop_active_lazy_run_for_input_edit
        )
        self.loading_view.cancel_button.clicked.connect(self._cancel_process)
        self.input_panel.view_calendar_requested.connect(self._show_calendar_screen)
        self.input_panel.dashboard_view_results_requested.connect(
            self._show_top_schedule_screen
        )
        self.input_panel.dashboard_next_batch_requested.connect(
            self._request_next_schedule_batch_from_dashboard
        )
        self.input_panel.ai_constraint_requested.connect(
            self.handle_new_ai_constraint
        )
        self.calendar_view.back_requested.connect(self._show_input_screen)
        self.calendar_view.day_clicked.connect(self._toggle_calendar_day)
        self.calendar_view.period_dates_changed.connect(self._update_period_dates)
        self.output_view.back_requested.connect(self._show_input_screen)
        self.output_view.more_requested.connect(self._request_next_schedule_batch)
        self.output_view.save_requested.connect(self._save_selected_schedule)
        self.output_view.selected_schedule_changed.connect(self._set_selected_schedule)
        self.output_view.sorting_priority_widget.priority_changed.connect(
            lambda _priority: self._refresh_analytics_dashboard()
        )
        self._runner.process_started.connect(self._handle_started)
        self._runner.stdout_received.connect(self._handle_stdout)
        self._runner.stderr_received.connect(self._handle_stderr)
        self._runner.process_finished.connect(self._handle_finished)
        self._runner.process_error.connect(self._handle_error)
        # Calendar-related actions originate in the OutputView and are routed
        # through MainWindow because MainWindow owns the export service and
        # application-level error handling.

        self.output_view.calendar_export_requested.connect(
            self._export_selected_schedule_to_calendar
        )

        self.output_view.calendar_revoke_all_requested.connect(
            self._revoke_all_app_calendar_entries
        )

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
                # Synchronize the initial state of the "Remove All" button with the
                # persisted export registry. This allows previously exported entries
                # from earlier application sessions to be detected immediately.
                self._sync_calendar_revoke_all_button()

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
            self._toast.show_message(
                "The source files were modified since your last session. "
                "The application has automatically reloaded the newest data."
            )

    def _load_selected_files(
        self,
        courses_path: str,
        exam_dates_path: str,
        course_mode: str,
        exam_dates_mode: str,
    ) -> None:
        self._stop_stale_run_for_file_reload()
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
        self._clear_scheduler_results_for_new_input()

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

    def _stop_stale_run_for_file_reload(self) -> None:
        self._pending_run_after_stale_stop = None
        if self._runner.is_running():
            self._ignore_stale_runner_result = True
            self._runner.cancel()

        self._active_run_config = None
        self._stay_on_input_after_lazy_stop = False
        self._parser.reset()
        self.input_panel.set_running(False)
        self.output_view.set_running(False)
        self.output_view.set_more_available(False)

    def _clear_scheduler_results_for_new_input(self) -> None:
        self._selected_schedule = None
        self.output_view.clear()
        self.input_panel.set_schedules_available(False)
        self._refresh_analytics_dashboard()

    def _load_exam_period_calendar(
        self,
        selected_period_index: int | None = None,
    ) -> None:
        period_view_models = self._build_schedule_period_view_models(None)
        self.calendar_view.load_exam_periods(
            period_view_models,
            selected_period_index=selected_period_index,
        )

    def _toggle_calendar_day(self, period_index: int, day) -> None:
        periods = self.input_panel.exam_periods
        # Clicks come from the UI, so keep this boundary defensive.
        if period_index < 0 or period_index >= len(periods):
            QMessageBox.warning(
                self,
                "Invalid calendar day",
                f"Unknown exam period index: {period_index}",
            )
            return

        period = periods[period_index]
        if self._is_day_excluded_by_ai_rule(period, day):
            self._toast.show_message(
                "This day is excluded by an active AI rule. "
                "Revert or clear the AI rule before allowing this day.",
            )
            self.calendar_view.update_day_status(
                period_index,
                day,
                is_excluded=True,
            )
            return

        # The model already defines validity; the UI just flips the current state.
        is_excluding = period.is_date_valid(day)
        try:
            if is_excluding:
                self.input_panel.exclude_calendar_day(period_index, day)
            else:
                self.input_panel.restore_calendar_day(period_index, day)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid calendar day", str(exc))
            return

        # A day toggle is only a color change, so keep the calendar in place and repaint one cube.
        did_repaint = self.calendar_view.update_day_status(
            period_index,
            day,
            is_excluded=is_excluding,
        )
        if not did_repaint:
            # If the visible widgets are out of sync, rebuild once instead of leaving stale color.
            self._load_exam_period_calendar(selected_period_index=period_index)

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
        if self._runner.is_running():
            if self._ignore_stale_runner_result:
                self._pending_run_after_stale_stop = config
                self.input_panel.set_running(True)
                self.output_view.set_more_available(False)
                return

            self._toast.show_message("The scheduler is already running.")
            return

        self._start_cli_run_now(config)

    def _start_cli_run_now(self, config: CliRunConfig) -> None:
        self._ignore_stale_runner_result = False
        self._pending_run_after_stale_stop = None
        self._active_run_config = config
        self._stay_on_input_after_lazy_stop = False
        self._refresh_output_adapter(self.loaded_input_data)
        self._parser.reset()
        self.output_view.clear()
        self.output_view.set_more_available(False)
        self.input_panel.set_schedules_available(False)
        if config.mode == "complete-count":
            self._show_output_screen()
        self._runner.start(config)

    def _cancel_process(self) -> None:
        # Handle manual cancellation, stop the runner, and reset UI states immediately
        self._stay_on_input_after_lazy_stop = True
        self._runner.cancel()
        self.input_panel.set_running(False)
        self.output_view.set_running(False)
        self.input_panel.show_program_page()
        self._stack.setCurrentWidget(self.input_panel)

    def _stop_active_lazy_run_for_input_edit(self) -> None:
        if (
            self._active_run_config is None
            or not self._active_run_config.lazy_schedules
            or not self._runner.is_running()
        ):
            return

        self._ignore_stale_runner_result = True
        self._pending_run_after_stale_stop = None
        self._stay_on_input_after_lazy_stop = False
        self._active_run_config = None
        self._runner.send_input_line(LAZY_STOP_COMMAND)
        self.input_panel.set_running(False)
        self.output_view.set_running(False)
        self.output_view.set_more_available(False)

    def _handle_started(self) -> None:
        # Disable input controls and prepare output screens for execution state
        self.input_panel.set_running(True)
        self.output_view.set_running(True)
        self.loading_view.reset()
        # Seamlessly transition stack widget to display the dedicated loading view
        self._stack.setCurrentWidget(self.loading_view)

    def _handle_stdout(self, text: str) -> None:
        if self._ignore_stale_runner_result:
            return

        schedule_total = parse_schedule_total(text)
        if schedule_total is not None:
            self.output_view.set_schedule_total(schedule_total)

        systems = _systems_with_scheduled_exams(
            self._output_adapter.convert(self._parser.feed(text))
        )
        self.output_view.add_systems(systems)

        if systems:
            self._show_output_screen()

        if (
            systems
            and self._active_run_config is not None
            and self._active_run_config.lazy_schedules
        ):
            self._show_output_screen()
            self.output_view.set_stream_progress(self.output_view.cache.system_count)
            self.output_view.set_more_available(True)
            self._refresh_analytics_dashboard()
        elif not _looks_like_schedule_output(text):
            self.output_view.append_log(text)

    def _handle_stderr(self, text: str) -> None:
        if self._ignore_stale_runner_result:
            return

        self.output_view.append_log(text)

    def _handle_finished(self, exit_code: int, status: str) -> None:
        if self._ignore_stale_runner_result:
            pending_run = self._pending_run_after_stale_stop
            self._ignore_stale_runner_result = False
            self._pending_run_after_stale_stop = None
            self._parser.reset()
            self.input_panel.set_running(False)
            self.output_view.set_running(False)
            self.output_view.set_more_available(False)
            self._refresh_analytics_dashboard()
            if pending_run is not None:
                self._start_cli_run_now(pending_run)
            return

        self.output_view.add_systems(
            _systems_with_scheduled_exams(
                self._output_adapter.convert(self._parser.flush())
            )
        )
        self.input_panel.set_running(False)
        self.output_view.set_more_available(False)
        self._refresh_analytics_dashboard()
        if self._stay_on_input_after_lazy_stop:
            self._stay_on_input_after_lazy_stop = False
            self.output_view.set_finished(exit_code, status)
            return

        if exit_code == 0:
            self.output_view.set_finished(exit_code, status)
            self._load_generated_output_file()
            if self._should_show_empty_schedule_message():
                self._show_no_exam_schedules_toast()
                return
            if self.output_view.cache.system_count:
                self._show_output_screen()
            if self.output_view.schedule_total is None and self.output_view.cache.system_count:
                self.output_view.set_schedule_total(self.output_view.cache.system_count)
            return

        self._show_output_screen()
        self.output_view.set_error(
            f"Scheduler process exited with code {exit_code} ({status})."
        )

    def _handle_error(self, message: str) -> None:
        if self._ignore_stale_runner_result:
            self.input_panel.set_running(False)
            self.output_view.set_more_available(False)
            return

        self.input_panel.set_running(False)
        self.output_view.set_more_available(False)
        self._refresh_analytics_dashboard()
        if self._stay_on_input_after_lazy_stop:
            self._stay_on_input_after_lazy_stop = False
            self.output_view.set_error(message)
            return

        self._show_output_screen()
        self.output_view.set_error(message)

    def _request_next_schedule_batch(self) -> None:
        if self._active_run_config is None or not self._active_run_config.lazy_schedules:
            return

        self._runner.send_input_line(LAZY_NEXT_COMMAND)

    def _request_next_schedule_batch_from_dashboard(self) -> None:
        self._show_output_screen()
        if not self.output_view.request_next_generated_batch():
            self._toast.show_message("No next schedule batch is available.")
        self._refresh_analytics_dashboard()

    def _save_selected_schedule(self) -> None:
        schedule = self.output_view.selected_schedule
        if schedule is None:
            QMessageBox.information(
                self,
                "No schedule selected",
                "Generate or select a schedule before saving.",
            )
            return

        default_path = self._default_selected_schedule_path(schedule)
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Schedule",
            str(default_path),
            self._save_file_filter(),
        )
        if not file_path:
            return

        try:
            # The same save button handles raw schedules and deterministic analytics exports.
            if _is_analytics_export_request(file_path, selected_filter):
                saved_path = self._selected_schedule_analytics_writer.write(
                    schedule,
                    file_path,
                    format_name=_analytics_format_from_selection(
                        file_path,
                        selected_filter,
                    ),
                    active_priorities=self.output_view.sorting_priority_widget.priority,
                )
                message = f"Analytics saved to {saved_path}"
            else:
                saved_path = self._selected_schedule_writer.write(schedule, file_path)
                message = f"Schedule saved to {saved_path}"
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not save schedule", str(exc))
            return

        self._toast.show_message(message)

    def _default_selected_schedule_path(self, schedule: ScheduleSystem) -> Path:
        return (
            self._project_root
            / "outputs"
            / self._selected_schedule_writer.suggested_filename(schedule)
        )

    def _save_file_filter(self) -> str:
        return (
            "Text Files (*.txt);;"
            "Analytics JSON Files (*.json);;"
            "Analytics Text Files (*.txt);;"
            "Analytics CSV Files (*.csv);;"
            "Analytics PDF Files (*.pdf);;"
            "All Files (*)"
        )

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
                        _systems_with_scheduled_exams(
                            self._output_adapter.convert(parser.feed(chunk))
                        )
                    )
        except OSError as exc:
            self.output_view.set_error(f"Could not load output file: {exc}")
            return

        self.output_view.add_systems(
            _systems_with_scheduled_exams(
                self._output_adapter.convert(parser.flush())
            )
        )
        if self.output_view.cache.system_count:
            self.output_view.set_schedule_total(self.output_view.cache.system_count)

    def _should_show_empty_schedule_message(self) -> bool:
        config = self._active_run_config
        return (
            config is not None
            and config.mode != "complete-count"
            and self.output_view.cache.system_count == 0
        )

    def _show_no_exam_schedules_toast(self) -> None:
        self.output_view.clear()
        self.input_panel.set_schedules_available(False)
        self.input_panel.show_program_page()
        self._stack.setCurrentWidget(self.input_panel)
        self._toast.show_message(NO_EXAM_SCHEDULES_MESSAGE)

    def _refresh_output_adapter(self, loaded_data: LoadedSchedulerInput | None) -> None:
        courses = loaded_data.courses if loaded_data is not None else ()
        selected_program_ids = self.input_panel.program_selector.get_selected_program_ids()
        # Widgets receive adapted schedule rows, not raw scheduler text.
        self._output_adapter.update_course_catalog(courses, selected_program_ids)

    def _set_selected_schedule(self, schedule: ScheduleSystem | None) -> None:
        self._selected_schedule = schedule
        self._refresh_analytics_dashboard()
        self.output_view.set_schedule_calendar(
            self._build_schedule_period_view_models(schedule)
        )
        if (
            self._stack.currentWidget() is self.input_panel
            and self.input_panel.is_calendar_page_visible()
        ):
            self._load_exam_period_calendar()

    def _refresh_analytics_dashboard(self) -> None:
        total_schedules = (
            self.output_view.schedule_total
            or self.output_view.cache.system_count
            or None
        )
        self.input_panel.refresh_analytics_dashboard(
            self.output_view.best_schedule_so_far,
            current_batch_schedule=self.output_view.current_batch_best_schedule,
            active_priorities=self.output_view.best_schedule_priority,
            total_schedules=total_schedules,
            current_page=self.output_view.pagination_bar.current_page,
            can_request_more=self.output_view.can_request_more,
        )

    def _build_schedule_period_view_models(
        self,
        schedule: ScheduleSystem | None,
    ) -> tuple[ExamPeriodViewModel, ...]:
        active_ai_rules = self._read_active_ai_rules()
        view_models = []
        for period in self.input_panel.exam_periods:
            exclusions = tuple(
                ExclusionViewModel(
                    start_date=exclusion.start_date,
                    end_date=exclusion.end_date,
                )
                for exclusion in period.exclusions
            ) + self._ai_calendar_exclusions_for_period(period, active_ai_rules)
            view_models.append(
                ExamPeriodViewModel(
                    semester_label=period.semester.value,
                    term_label=period.term.value,
                    start_date=period.start_date,
                    end_date=period.end_date,
                    exclusions=exclusions,
                    scheduled_exams=_scheduled_exam_view_models_for_period(
                        self._calendar_data_service,
                        schedule,
                        period.semester.value,
                        period.term.value,
                        period.start_date,
                        period.end_date,
                    ),
                ),
            )
        return tuple(view_models)

    def _ai_calendar_exclusions_for_period(
        self,
        period,
        active_ai_rules: list[dict],
    ) -> tuple[ExclusionViewModel, ...]:
        exclusions: list[ExclusionViewModel] = []
        seen: set[tuple[date, date | None]] = set()
        for rule in active_ai_rules:
            parameters = rule.get("parameters")
            if not isinstance(parameters, dict):
                continue

            for exclusion in _global_ai_calendar_exclusions_for_rule(
                str(rule.get("rule_type", "")),
                parameters,
                period.start_date,
                period.end_date,
            ):
                key = (exclusion.start_date, exclusion.end_date)
                if key in seen:
                    continue
                seen.add(key)
                exclusions.append(exclusion)
        return tuple(exclusions)

    def _is_day_excluded_by_ai_rule(self, period, day: date) -> bool:
        return any(
            _exclusion_contains_date(exclusion, day)
            for exclusion in self._ai_calendar_exclusions_for_period(
                period,
                self._read_active_ai_rules(),
            )
        )

    def _show_input_screen(self) -> None:
        self.input_panel.show_program_page()
        self._stack.setCurrentWidget(self.input_panel)

    def _show_calendar_screen(self) -> None:
        self._load_exam_period_calendar()
        # Calendar is an input-page tab; schedule generation is the only action that leaves it.
        self.input_panel.show_calendar_page()
        self._stack.setCurrentWidget(self.input_panel)

    def _show_top_schedule_screen(self) -> None:
        self.output_view.show_best_schedule_so_far()
        self._show_output_screen()

    def _show_output_screen(self) -> None:
        self.input_panel.show_schedules_page()
        self._stack.setCurrentWidget(self.input_panel)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_toast"):
            self._toast.reposition()

    def _load_stylesheet(self) -> None:
        stylesheet_path = Path(__file__).with_name("styles.qss")
        self.setStyleSheet(stylesheet_path.read_text(encoding="utf-8"))

    def handle_new_ai_constraint(self, rule_dict: dict) -> None:
        """Persist one validated upsert or removal event from the copilot."""
        print(
            "DEBUG [MainWindow]: Received constraint event: "
            f"{json.dumps(rule_dict, ensure_ascii=True, sort_keys=True)}",
            flush=True,
        )
        if not isinstance(rule_dict, dict):
            return

        current_rules = self._read_active_ai_rules()
        original_rules = list(current_rules)
        operation = rule_dict.get("operation")
        if operation == "upsert" and set(rule_dict) == {"operation", "rule"}:
            persisted_rule = rule_dict.get("rule")
            if not self._is_persistable_ai_rule(persisted_rule):
                return
            assert isinstance(persisted_rule, dict)
            rule_id = persisted_rule["rule_id"]
            current_rules = [
                rule
                for rule in current_rules
                if rule.get("rule_id") != rule_id
            ]
            current_rules.append(dict(persisted_rule))
        elif operation == "remove" and set(rule_dict) == {
            "operation",
            "rule_id",
        }:
            rule_id = rule_dict.get("rule_id")
            if not self._is_ai_rule_id(rule_id):
                return
            current_rules = [
                rule
                for rule in current_rules
                if rule.get("rule_id") != rule_id
            ]
        elif operation == "clear" and set(rule_dict) == {"operation"}:
            current_rules = []
        else:
            return

        try:
            self._write_active_ai_rules(current_rules)
        except OSError as exc:
            print(
                "DEBUG [MainWindow]: Failed to save active AI rules: "
                f"{exc}",
                flush=True,
            )
            self._toast.show_message(
                "The AI rule was processed, but its file could not be saved. "
                "Please try again."
            )
            return
        print(
            "DEBUG [MainWindow]: Saved active AI rules to "
            f"{self._active_ai_rules_file}",
            flush=True,
        )
        if current_rules != original_rules:
            self._stop_active_lazy_run_for_input_edit()
            if (
                self._stack.currentWidget() is self.input_panel
                and self.input_panel.is_calendar_page_visible()
            ):
                self._load_exam_period_calendar()

    def _initialize_active_ai_rules(self) -> None:
        self._active_ai_rules_file.parent.mkdir(parents=True, exist_ok=True)
        self._recover_pending_ai_rules_write()
        if not self._active_ai_rules_file.exists():
            self._write_active_ai_rules([])
        self.input_panel.restore_ai_copilot_rules(
            self._read_active_ai_rules()
        )

    def _read_active_ai_rules(self) -> list[dict]:
        try:
            payload = json.loads(
                self._active_ai_rules_file.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError, RecursionError):
            return []
        if not isinstance(payload, list) or len(payload) > 100:
            return []
        return [
            dict(rule)
            for rule in payload
            if self._is_persistable_ai_rule(rule)
        ]

    def _write_active_ai_rules(self, rules: list[dict]) -> None:
        self._active_ai_rules_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._active_ai_rules_file.with_suffix(".json.tmp")
        serialized_rules = (
            json.dumps(rules, ensure_ascii=False, indent=2) + "\n"
        )
        temporary_path.write_text(serialized_rules, encoding="utf-8")

        last_error: OSError | None = None
        for retry_delay in (0.0, 0.05, 0.1, 0.2, 0.4):
            if retry_delay:
                time.sleep(retry_delay)
            try:
                os.replace(temporary_path, self._active_ai_rules_file)
                return
            except PermissionError as exc:
                last_error = exc

        # OneDrive and antivirus scanners can hold the destination open while
        # still permitting a normal write. Use that as a final safe fallback.
        try:
            self._active_ai_rules_file.write_text(
                serialized_rules,
                encoding="utf-8",
            )
            temporary_path.unlink(missing_ok=True)
        except OSError:
            if last_error is not None:
                raise last_error
            raise

    def _recover_pending_ai_rules_write(self) -> None:
        temporary_path = self._active_ai_rules_file.with_suffix(".json.tmp")
        if not temporary_path.is_file():
            return

        try:
            temporary_is_newer = (
                not self._active_ai_rules_file.exists()
                or temporary_path.stat().st_mtime
                > self._active_ai_rules_file.stat().st_mtime
            )
            pending_rules = json.loads(
                temporary_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError, RecursionError):
            temporary_path.unlink(missing_ok=True)
            return

        if (
            temporary_is_newer
            and isinstance(pending_rules, list)
            and len(pending_rules) <= 100
            and all(
                self._is_persistable_ai_rule(rule)
                for rule in pending_rules
            )
        ):
            try:
                self._write_active_ai_rules(
                    [dict(rule) for rule in pending_rules]
                )
                print(
                    "DEBUG [MainWindow]: Recovered pending active AI rules "
                    f"write to {self._active_ai_rules_file}",
                    flush=True,
                )
                return
            except OSError as exc:
                print(
                    "DEBUG [MainWindow]: Pending AI rules recovery failed: "
                    f"{exc}",
                    flush=True,
                )
                return

        temporary_path.unlink(missing_ok=True)

    @classmethod
    def _is_persistable_ai_rule(cls, value: object) -> bool:
        if not isinstance(value, dict):
            return False
        if set(value) != {
            "rule_id",
            "description",
            "rule_type",
            "parameters",
        }:
            return False
        return (
            cls._is_ai_rule_id(value.get("rule_id"))
            and isinstance(value.get("description"), str)
            and isinstance(value.get("rule_type"), str)
            and isinstance(value.get("parameters"), dict)
        )

    @staticmethod
    def _is_ai_rule_id(value: object) -> bool:
        if not isinstance(value, str) or not value.startswith("ai_rule_"):
            return False
        return value.removeprefix("ai_rule_").isdigit()

    def _sync_calendar_revoke_all_button(self) -> None:
        """
        Keep the global calendar cleanup button synchronized with the
        export registry state.

        The button should only be available when at least one exam event
        previously exported by this application exists in the registry.
        """
        self.output_view.set_calendar_revoke_all_enabled(
            self._calendar_export_service.has_exported_entries()
        )

    def _export_selected_schedule_to_calendar(self) -> None:
        self._run_calendar_export_action(
            action=lambda: self._calendar_export_service.export_schedule(
                self.output_view.selected_schedule
            ),
            success_prefix="Successfully exported schedule to calendar:",
        )

    def _revoke_current_schedule_from_calendar(self) -> None:
        self._run_calendar_export_action(
            action=lambda: self._calendar_export_service.revoke_current_schedule(
                self.output_view.selected_schedule
            ),
            success_prefix="Successfully generated cancellation file for schedule:",
        )

    def _revoke_all_app_calendar_entries(self) -> None:
        self._run_calendar_export_action(
            action=self._calendar_export_service.revoke_all_exported,
            success_prefix="Successfully generated global cancellation file:",
        )

    def _run_calendar_export_action(
            self,
            action,
            success_prefix: str,
    ) -> None:
        try:
            result = action()
        except CalendarExportError as exc:
            QMessageBox.information(self, "Calendar Sync", str(exc))
            return
        except OSError as exc:
            QMessageBox.warning(self, "Calendar Sync", f"System Error: {exc}")
            return

        if not hasattr(result, 'ics_content') or not result.ics_content:
            self._toast.show_message("No valid events to process.")
            return

        # Open native file save dialog so the user saves the .ics file locally
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Calendar File (.ics)",
            str(self._project_root / "outputs" / "exam_schedule.ics"),
            "Calendar Files (*.ics)",
        )

        if not file_path:
            return  # User aborted the save flow

        try:
            saved_path = Path(file_path)
            saved_path.write_text(result.ics_content, encoding="utf-8", newline="")
        except OSError as exc:
            QMessageBox.warning(self, "Calendar Sync", f"Could not save file: {exc}")
            return

        # Automatically open the saved file using the OS default calendar app (Outlook, Apple Calendar, etc.)
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(saved_path.resolve())))

        self._toast.show_message(
            self._calendar_success_message(result, success_prefix)
        )
        self._sync_calendar_revoke_all_button()

    def _calendar_success_message(
            self,
            result: CalendarExportResult,
            prefix: str,
    ) -> str:
        message = f"{prefix} {result.event_count} exam event(s)."
        if result.skipped_without_date:
            message += f" Skipped {result.skipped_without_date} exam(s) without dates."
        return message


_AI_WEEKDAY_INDEXES = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _global_ai_calendar_exclusions_for_rule(
    rule_type: str,
    parameters: dict,
    period_start: date,
    period_end: date,
) -> tuple[ExclusionViewModel, ...]:
    if not _is_global_calendar_scope(parameters):
        return ()

    if rule_type == "exclude_day":
        return _exclude_day_calendar_exclusions(
            parameters,
            period_start,
            period_end,
        )

    if rule_type == "exclude_period":
        return _exclude_period_calendar_exclusions(
            parameters,
            period_start,
            period_end,
        )

    return ()


def _exclusion_contains_date(exclusion: ExclusionViewModel, current_date: date) -> bool:
    if exclusion.end_date is None:
        return exclusion.start_date == current_date
    return exclusion.start_date <= current_date <= exclusion.end_date


def _is_global_calendar_scope(parameters: dict) -> bool:
    return not any(key in parameters for key in ("course", "lecturer", "program"))


def _exclude_day_calendar_exclusions(
    parameters: dict,
    period_start: date,
    period_end: date,
) -> tuple[ExclusionViewModel, ...]:
    if "date" in parameters:
        excluded_date = _parse_ai_iso_date(parameters.get("date"))
        if excluded_date is None or not period_start <= excluded_date <= period_end:
            return ()
        return (ExclusionViewModel(excluded_date, None),)

    weekday = str(parameters.get("weekday", "")).casefold()
    weekday_index = _AI_WEEKDAY_INDEXES.get(weekday)
    if weekday_index is None:
        return ()

    return tuple(
        ExclusionViewModel(current_date, None)
        for current_date in _period_dates(period_start, period_end)
        if current_date.weekday() == weekday_index
    )


def _exclude_period_calendar_exclusions(
    parameters: dict,
    period_start: date,
    period_end: date,
) -> tuple[ExclusionViewModel, ...]:
    if "month" in parameters:
        month = parameters.get("month")
        year = parameters.get("year")
        if not isinstance(month, int):
            return ()
        return tuple(
            ExclusionViewModel(current_date, None)
            for current_date in _period_dates(period_start, period_end)
            if current_date.month == month
            and (year is None or current_date.year == year)
        )

    start_date = _parse_ai_iso_date(parameters.get("start_date"))
    end_date = _parse_ai_iso_date(parameters.get("end_date"))
    if start_date is None or end_date is None:
        return ()

    clipped_start = max(period_start, start_date)
    clipped_end = min(period_end, end_date)
    if clipped_start > clipped_end:
        return ()
    return (ExclusionViewModel(clipped_start, clipped_end),)


def _parse_ai_iso_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _period_dates(period_start: date, period_end: date):
    current_date = period_start
    while current_date <= period_end:
        yield current_date
        current_date += timedelta(days=1)


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


def _scheduled_exam_view_models_for_period(
    calendar_data_service: ScheduleCalendarDataService,
    schedule: ScheduleSystem | None,
    semester_label: str,
    term_label: str,
    start_date,
    end_date,
) -> tuple[ScheduledExamViewModel, ...]:
    if schedule is None:
        return ()

    return tuple(
        _to_scheduled_exam_view_model(exam)
        for exam in calendar_data_service.exams_for_period(
            schedule,
            semester_label,
            term_label,
            start_date,
            end_date,
        )
    )


def _looks_like_schedule_output(text: str) -> bool:
    return (
        "Complete System #" in text
        or "Schedule #" in text
        or "=== SEMESTER:" in text
        or "[TERM:" in text
    )


def _systems_with_scheduled_exams(
    systems: list[ScheduleSystem],
) -> list[ScheduleSystem]:
    return [
        system
        for system in systems
        if any(period.exams for period in system.periods)
    ]


def _is_analytics_export_request(file_path: str, selected_filter: str) -> bool:
    suffix = Path(file_path).suffix.casefold()
    # JSON/CSV/PDF are analytics-only in this dialog; TXT can still mean a raw schedule.
    return "Analytics" in selected_filter or suffix in {".json", ".csv", ".pdf"}


def _analytics_format_from_selection(file_path: str, selected_filter: str) -> str:
    suffix = Path(file_path).suffix.casefold().lstrip(".")
    if suffix in {"json", "txt", "csv", "pdf"}:
        return suffix
    if "JSON" in selected_filter:
        return "json"
    if "CSV" in selected_filter:
        return "csv"
    if "PDF" in selected_filter:
        return "pdf"
    if "Text" in selected_filter:
        return "txt"
    return "json"
