"""Output screen for generated exam schedules."""

from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.ui.calendar_view_panel import CalendarPeriodList
from src.ui.pagination_bar import PaginationBar
from src.ui.schedule_best_tracker import ScheduleBestTracker
from src.sorting.schedule_priority import (
    SchedulePrioritySorter,
    sortable_exams_from_display_system,
)
from src.ui.sorting_priority_widget import SortingPriorityWidget
from src.ui.ui_cache import ScheduleCache, ScheduleSystem
from src.ui.view_models import ExamPeriodViewModel


DEFAULT_EMPTY_SCHEDULE_TEXT = "No possible schedule is available yet."


class OutputView(QWidget):
    """Show one generated schedule at a time as a calendar."""

    back_requested = pyqtSignal()
    more_requested = pyqtSignal()
    save_requested = pyqtSignal()

    # Forward calendar actions to MainWindow, which owns the
    # export service and calendar integration logic.
    calendar_export_requested = pyqtSignal()
    calendar_revoke_all_requested = pyqtSignal()

    selected_schedule_changed = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # The output screen pages through schedules one by one.
        self.cache = ScheduleCache(batch_size=1)
        self._generated_systems: list[ScheduleSystem] = []
        self._current_batch_systems: list[ScheduleSystem] = []
        self._schedule_sorter = SchedulePrioritySorter()
        self._best_schedule_tracker = ScheduleBestTracker(self._schedule_sorter)
        self._current_batch_best_tracker = ScheduleBestTracker(self._schedule_sorter)
        self._sort_panel_open = False
        self._sort_panel_width = 480
        self._selected_schedule: ScheduleSystem | None = None
        self._pending_more_page: int | None = None
        self._schedule_total: int | None = None
        self._process_notes: list[str] = []

        self.title_label = QLabel("Possible Exam Schedules")
        self.title_label.setObjectName("screenTitle")
        self.status_label = QLabel("Ready")

        self.sort_options_button = QPushButton("click for sort options")
        self.sort_options_button.setObjectName("sortOptionsButton")
        self.sorting_priority_widget = SortingPriorityWidget(self)
        self.sorting_priority_widget.hide()
        self._sort_panel_animation = QPropertyAnimation(
            self.sorting_priority_widget,
            b"pos",
            self,
        )
        self._sort_panel_animation.setDuration(260)
        self._sort_panel_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.pagination_bar = PaginationBar()
        self.back_button = QPushButton("Back to Input")
        self.schedule_label = QLabel("No schedule selected")
        self.schedule_label.setObjectName("paneTitle")
        self.calendar_body = CalendarPeriodList(DEFAULT_EMPTY_SCHEDULE_TEXT)
        self.calendar_body.setObjectName("calendarContent")

        self._build_layout()
        self._connect_signals()
        self._refresh_page()
        self._resize_sort_panel()

    def clear(self) -> None:
        self._generated_systems.clear()
        self._current_batch_systems.clear()
        self._best_schedule_tracker.reset(self.sorting_priority_widget.priority)
        self._current_batch_best_tracker.reset(self.sorting_priority_widget.priority)
        self.cache.clear()
        self.schedule_label.setText("No schedule selected")
        self.calendar_body.set_empty_text(DEFAULT_EMPTY_SCHEDULE_TEXT)
        self.calendar_body.load_periods(())
        self._set_selected_schedule(None)
        self._pending_more_page = None
        self._schedule_total = None
        self._process_notes.clear()
        self.status_label.setText("Ready")
        self.pagination_bar.reset()
        self._refresh_page()

    def set_running(self, running: bool) -> None:
        self.status_label.setText("Running..." if running else "Ready")

    def set_finished(self, exit_code: int, status: str) -> None:
        self.status_label.setText(f"Finished: exit {exit_code}, {status}")

    def set_stream_progress(self, system_count: int) -> None:
        self.status_label.setText(f"Running... cached {system_count:,} schedule systems")

    def set_more_available(self, available: bool) -> None:
        self.pagination_bar.set_can_request_more(available)

    def set_error(self, message: str) -> None:
        self.status_label.setText(f"Error: {message}")

    def set_empty_result(self, message: str) -> None:
        self._generated_systems.clear()
        self._current_batch_systems.clear()
        self._best_schedule_tracker.reset(self.sorting_priority_widget.priority)
        self._current_batch_best_tracker.reset(self.sorting_priority_widget.priority)
        self.cache.clear()
        self._set_selected_schedule(None)
        self._pending_more_page = None
        self._schedule_total = None
        self.pagination_bar.reset()
        self.schedule_label.setText("No schedule selected")
        self.calendar_body.set_empty_text(message)
        self.calendar_body.load_periods(())

    def append_log(self, text: str) -> None:
        if text:
            self._process_notes.append(text)

    @property
    def process_notes(self) -> str:
        return "".join(self._process_notes)

    @property
    def schedule_total(self) -> int | None:
        return self._schedule_total

    @property
    def can_request_more(self) -> bool:
        return self.pagination_bar.can_request_more

    @property
    def best_schedule_priority(self) -> tuple[str, ...]:
        return self._best_schedule_tracker.priority

    def set_schedule_total(self, total: int | None) -> None:
        self._schedule_total = total if total and total > 0 else None
        self.pagination_bar.set_total_page_count(self._schedule_total)
        self._refresh_page()

    def set_schedule_calendar(self, periods: tuple[ExamPeriodViewModel, ...]) -> None:
        self.calendar_body.load_periods(periods)
        self.calendar_scroll.verticalScrollBar().setValue(0)

    def add_systems(self, systems: list[ScheduleSystem]) -> None:
        if not systems:
            return

        self._generated_systems.extend(systems)
        requested_priority = self.sorting_priority_widget.priority
        self._current_batch_systems.extend(systems)
        if not self._current_batch_best_tracker.matches_priority(requested_priority):
            self._current_batch_best_tracker.rebuild(
                self._current_batch_systems,
                requested_priority,
            )
        else:
            self._current_batch_best_tracker.update_batch(systems)
        if not self._best_schedule_tracker.matches_priority(requested_priority):
            self._best_schedule_tracker.rebuild(
                self._generated_systems,
                requested_priority,
            )
        else:
            self._best_schedule_tracker.update_batch(systems)
        self._replace_cache_with_current_sort()
        self.pagination_bar.set_page_count(self.cache.batch_count)
        if (
            self._pending_more_page is not None
            and self.cache.batch_count >= self._pending_more_page
        ):
            self.pagination_bar.set_current_page(self._pending_more_page)
            self._pending_more_page = None
        self._refresh_page()

    def _apply_sort_priority(self, _priority: tuple[str, ...]) -> None:
        self._replace_cache_with_current_sort()
        self._best_schedule_tracker.rebuild(
            self._generated_systems,
            self.sorting_priority_widget.priority,
        )
        self._current_batch_best_tracker.rebuild(
            self._current_batch_systems,
            self.sorting_priority_widget.priority,
        )
        self.pagination_bar.set_page_count(self.cache.batch_count)
        if self.cache.batch_count:
            self.pagination_bar.set_current_page(1)
        else:
            self._refresh_page()

    def _replace_cache_with_current_sort(self) -> None:
        priority = self.sorting_priority_widget.priority
        if not priority:
            self.cache.replace(self._generated_systems)
            return

        self.cache.replace(
            self._schedule_sorter.sort(
                self._generated_systems,
                priority,
                sortable_exams_from_display_system,
            )
        )

    @property
    def selected_schedule(self) -> ScheduleSystem | None:
        return self._selected_schedule

    @property
    def best_schedule_so_far(self) -> ScheduleSystem | None:
        return self._best_schedule_tracker.best_schedule

    @property
    def current_batch_best_schedule(self) -> ScheduleSystem | None:
        return self._current_batch_best_tracker.best_schedule

    def _build_layout(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 18, 18, 18)
        root_layout.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.sort_options_button)
        header.addWidget(self.back_button)
        root_layout.addLayout(header)

        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        root_layout.addWidget(self.status_label)
        root_layout.addWidget(self.pagination_bar)

        root_layout.addWidget(self.schedule_label)

        self.calendar_scroll = QScrollArea()
        self.calendar_scroll.setObjectName("calendarScroll")
        self.calendar_scroll.setWidgetResizable(True)
        self.calendar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.calendar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.calendar_scroll.setWidget(self.calendar_body)
        root_layout.addWidget(self.calendar_scroll, 1)

    def _connect_signals(self) -> None:
        self.pagination_bar.page_changed.connect(lambda _page: self._refresh_page())
        self.pagination_bar.more_requested.connect(self._request_more_systems)
        self.pagination_bar.future_page_requested.connect(self._request_schedule_page)
        self.pagination_bar.save_requested.connect(self.save_requested.emit)
        self.back_button.clicked.connect(self.back_requested.emit)

        # Sorting signals
        self.sort_options_button.clicked.connect(self._toggle_sort_panel)
        self.sorting_priority_widget.close_requested.connect(self._hide_sort_panel)
        self.sorting_priority_widget.priority_changed.connect(self._apply_sort_priority)
        self._sort_panel_animation.finished.connect(
            self._handle_sort_panel_animation_finished
        )

        # Forward pagination bar calendar actions to the main window layer.
        # OutputView acts as a pass-through component.
        self.pagination_bar.calendar_export_requested.connect(
            self.calendar_export_requested.emit
        )
        self.pagination_bar.calendar_revoke_all_requested.connect(
            self.calendar_revoke_all_requested.emit
        )

    def _request_more_systems(self) -> None:
        self._request_schedule_page(self.pagination_bar.current_page + 1)

    def start_new_generated_batch(self) -> None:
        self._current_batch_systems.clear()
        self._current_batch_best_tracker.reset(self.sorting_priority_widget.priority)

    def show_best_schedule_so_far(self) -> None:
        schedule = self.best_schedule_so_far
        if schedule is None:
            return
        page_number = self.cache.page_number_for_system(schedule)
        if page_number is not None:
            self.pagination_bar.set_current_page(page_number)

    def request_next_generated_batch(self) -> bool:
        if not self.can_request_more:
            return False
        self._request_schedule_page(self.pagination_bar.page_count + 1)
        return True

    def _request_schedule_page(self, page_number: int) -> None:
        # The next batch arrives later from QProcess, so keep the requested page.
        self._pending_more_page = page_number
        self.start_new_generated_batch()
        self.set_more_available(False)
        self.status_label.setText("Generating next 1,000 schedule systems...")
        self.more_requested.emit()

    def _toggle_sort_panel(self) -> None:
        if self._sort_panel_open:
            self._hide_sort_panel()
        else:
            self._show_sort_panel()

    def _show_sort_panel(self) -> None:
        self._sort_panel_open = True
        self._resize_sort_panel()
        self.sorting_priority_widget.move(self.width(), 0)
        self.sorting_priority_widget.show()
        self.sorting_priority_widget.raise_()
        self._animate_sort_panel(
            QPoint(self.width(), 0),
            QPoint(self.width() - self._current_sort_panel_width(), 0),
        )

    def _hide_sort_panel(self) -> None:
        self._sort_panel_open = False
        self._animate_sort_panel(
            self.sorting_priority_widget.pos(),
            QPoint(self.width(), 0),
        )

    def _animate_sort_panel(self, start: QPoint, end: QPoint) -> None:
        self._sort_panel_animation.stop()
        self._sort_panel_animation.setStartValue(start)
        self._sort_panel_animation.setEndValue(end)
        self._sort_panel_animation.start()

    def _handle_sort_panel_animation_finished(self) -> None:
        if not self._sort_panel_open:
            self.sorting_priority_widget.hide()

    def _resize_sort_panel(self) -> None:
        panel_width = self._current_sort_panel_width()
        self.sorting_priority_widget.setFixedSize(panel_width, self.height())
        if self._sort_panel_open:
            self.sorting_priority_widget.move(self.width() - panel_width, 0)
        else:
            self.sorting_priority_widget.move(self.width(), 0)

    def _current_sort_panel_width(self) -> int:
        if self.width() <= 0:
            return self._sort_panel_width
        return min(self._sort_panel_width, self.width())

    def _refresh_page(self) -> None:
        if self.cache.batch_count == 0:
            self.schedule_label.setText("No schedule selected")
            self.calendar_body.load_periods(())
            self._set_selected_schedule(None)
            return

        systems = self.cache.get_page(self.pagination_bar.current_page)
        schedule = systems[0] if systems else None
        if schedule is None:
            self.schedule_label.setText("No schedule selected")
        else:
            total = self._schedule_total or self.cache.system_count
            self.schedule_label.setText(
                f"{self.pagination_bar.current_page} of {_format_compact_count(total)} schedules"
            )
        self._set_selected_schedule(schedule)

    def _set_selected_schedule(self, schedule: ScheduleSystem | None) -> None:
        if self._selected_schedule == schedule:
            return
        self._selected_schedule = schedule
        self.selected_schedule_changed.emit(schedule)

    def set_calendar_revoke_all_enabled(self, enabled: bool) -> None:
        """
        Update the availability of the global calendar cleanup action.

        The actual enablement decision is owned by MainWindow, which
        has access to the export registry state.
        """
        self.pagination_bar.set_calendar_revoke_all_enabled(enabled)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._resize_sort_panel()

    def keyPressEvent(self, event) -> None:
        if (
            self._sort_panel_open
            and event.key() == Qt.Key.Key_Escape
        ):
            self._hide_sort_panel()
            event.accept()
            return
        super().keyPressEvent(event)


def _format_compact_count(value: int) -> str:
    """Keep very large schedule totals readable in the output header."""
    units = (
        (1_000_000_000, "B"),
        (1_000_000, "M"),
        (1_000, "K"),
    )
    for threshold, suffix in units:
        if value >= threshold:
            compact = value / threshold
            text = f"{compact:.1f}".rstrip("0").rstrip(".")
            return f"{text}{suffix}"
    return str(value)
