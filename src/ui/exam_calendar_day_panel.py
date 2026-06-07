"""Input-screen editor for exam-period day availability."""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.services.day_status_service import iter_period_days


DAY_ROLE = Qt.ItemDataRole.UserRole


class ExamCalendarDayPanel(QWidget):
    """Shows exam-period days and lets the user request exclude/restore actions."""

    exclude_day_requested = pyqtSignal(int, object)
    restore_day_requested = pyqtSignal(int, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._periods: tuple[object, ...] = ()

        self.title_label = QLabel("Exam Calendar Days")
        self.title_label.setObjectName("sectionTitleLabel")
        self.period_selector = QComboBox()
        self.period_selector.setObjectName("examPeriodSelector")
        self.day_table = QTableWidget()
        self.day_table.setObjectName("examCalendarDayTable")
        self.exclude_button = QPushButton("Exclude Day")
        self.restore_button = QPushButton("Restore Day")
        self.status_label = QLabel("Load files to edit calendar days.")
        self.status_label.setObjectName("calendarDayStatusLabel")

        self._build_ui()
        self._connect_signals()
        self._set_empty_state()

    def set_periods(
        self,
        periods,
        selected_period_index: int | None = None,
        selected_day: date | None = None,
    ) -> None:
        self._periods = tuple(periods)
        self._populate_period_selector(selected_period_index)
        self._populate_days(selected_day)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.addWidget(self.period_selector)
        controls.addStretch(1)
        controls.addWidget(self.exclude_button)
        controls.addWidget(self.restore_button)
        layout.addLayout(controls)

        self.day_table.setColumnCount(2)
        self.day_table.setHorizontalHeaderLabels(["Date", "Status"])
        self.day_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.day_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.day_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.day_table.verticalHeader().setVisible(False)
        self.day_table.setAlternatingRowColors(True)
        self.day_table.setMinimumHeight(150)
        self.day_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.day_table)
        layout.addWidget(self.status_label)

    def _connect_signals(self) -> None:
        self.period_selector.currentIndexChanged.connect(
            lambda _index: self._populate_days()
        )
        self.day_table.itemSelectionChanged.connect(self._sync_action_state)
        self.exclude_button.clicked.connect(self._emit_exclude_day)
        self.restore_button.clicked.connect(self._emit_restore_day)

    def _populate_period_selector(self, selected_period_index: int | None) -> None:
        self.period_selector.blockSignals(True)
        try:
            self.period_selector.clear()
            for index, period in enumerate(self._periods):
                self.period_selector.addItem(_period_label(period), index)

            if self._periods:
                target_index = selected_period_index or 0
                if target_index < 0 or target_index >= len(self._periods):
                    target_index = 0
                self.period_selector.setCurrentIndex(target_index)
        finally:
            self.period_selector.blockSignals(False)

    def _populate_days(self, selected_day: date | None = None) -> None:
        period = self._current_period()
        if period is None:
            self._set_empty_state()
            return

        days = list(iter_period_days(period))
        self.day_table.setRowCount(len(days))
        selected_row = 0

        for row, day in enumerate(days):
            if selected_day == day:
                selected_row = row

            date_item = QTableWidgetItem(day.strftime("%d-%m-%Y"))
            date_item.setData(DAY_ROLE, day)
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            status_item = QTableWidgetItem(_day_status(period, day))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.day_table.setItem(row, 0, date_item)
            self.day_table.setItem(row, 1, status_item)

        if days:
            self.day_table.selectRow(selected_row)

        self.status_label.setText(f"{len(days)} days in selected period.")
        self._sync_action_state()

    def _set_empty_state(self) -> None:
        self.period_selector.setEnabled(False)
        self.day_table.setRowCount(0)
        self.exclude_button.setEnabled(False)
        self.restore_button.setEnabled(False)
        self.status_label.setText("Load files to edit calendar days.")

    def _sync_action_state(self) -> None:
        period = self._current_period()
        day = self._selected_day()
        has_selection = period is not None and day is not None

        self.period_selector.setEnabled(bool(self._periods))
        self.exclude_button.setEnabled(
            bool(has_selection and period.is_date_valid(day))
        )
        self.restore_button.setEnabled(
            bool(has_selection and not period.is_date_valid(day))
        )

    def _emit_exclude_day(self) -> None:
        self._emit_day_action(self.exclude_day_requested)

    def _emit_restore_day(self) -> None:
        self._emit_day_action(self.restore_day_requested)

    def _emit_day_action(self, signal) -> None:
        day = self._selected_day()
        period_index = self.period_selector.currentData()
        if day is None or period_index is None:
            return
        signal.emit(int(period_index), day)

    def _current_period(self):
        period_index = self.period_selector.currentData()
        if period_index is None:
            return None
        try:
            return self._periods[int(period_index)]
        except IndexError:
            return None

    def _selected_day(self) -> date | None:
        selected = self.day_table.selectedItems()
        if not selected:
            return None
        day = selected[0].data(DAY_ROLE)
        return day if isinstance(day, date) else None


def _period_label(period) -> str:
    semester = _enum_value(getattr(period, "semester", ""))
    term = _enum_value(getattr(period, "term", ""))
    start = getattr(period, "start_date", None)
    end = getattr(period, "end_date", None)
    if isinstance(start, date) and isinstance(end, date):
        return f"{semester} / {term} ({start:%d-%m-%Y} - {end:%d-%m-%Y})"
    return f"{semester} / {term}".strip()


def _day_status(period, day: date) -> str:
    return "Available" if period.is_date_valid(day) else "Excluded"


def _enum_value(value) -> str:
    return str(getattr(value, "value", value))
