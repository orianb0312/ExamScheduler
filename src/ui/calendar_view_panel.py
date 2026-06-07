"""Calendar-style view for displaying the current exam period."""

from __future__ import annotations

import calendar
from datetime import date
from typing import Sequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.ui.exam_calendar_day_panel import ExamCalendarDayPanel
from src.ui.view_models import ExamPeriodViewModel

_COLOR_VALID = "#244d3a"
_COLOR_EXCLUDED = "#5a2f3c"
_COLOR_OUT_OF_PERIOD = "#2b303a"
_COLOR_TODAY = "#4b3f25"
_COLOR_HEADER = "#2b415c"
_COLOR_HEADER_FG = "#7ed3ff"
_COLOR_CELL_TEXT = "#f1f3f5"
_COLOR_MUTED_TEXT = "#aeb7c6"
_COLOR_CELL_BORDER = "#4b5568"
_COLOR_VALID_BORDER = "#4e8b6c"
_COLOR_EXCLUDED_BORDER = "#a45b70"
_COLOR_TODAY_BORDER = "#ad8840"


class _DayCell(QLabel):
    """Single cell in the calendar grid."""

    def __init__(self, day_number: int | None, bg_color: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("calendarDayCell")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(40, 36)
        if day_number is not None:
            self.setText(str(day_number))
        self._apply_style(bg_color)

    def _apply_style(self, bg_color: str) -> None:
        border_color = _border_for_cell(bg_color)
        text_color = _COLOR_MUTED_TEXT if bg_color == _COLOR_OUT_OF_PERIOD else _COLOR_CELL_TEXT
        self.setStyleSheet(
            f"background-color: {bg_color}; "
            f"color: {text_color}; "
            f"border: 1px solid {border_color}; "
            "border-radius: 4px; "
            "font-size: 12px; "
            "font-weight: 600;"
        )


class _MonthGrid(QWidget):
    """
    Renders a single month as a 7-column grid with day cells.
    Days are coloured according to their status within the given ExamPeriodViewModel.
    """

    _DAY_HEADERS = ("Su", "Mo", "Tu", "We", "Th", "Fr", "Sa")

    def __init__(self, year: int, month: int, period: ExamPeriodViewModel, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("calendarMonthGrid")
        self._year = year
        self._month = month
        self._period = period
        self._build()
        # Six week rows plus header/title spacing keeps adjacent month grids aligned.
        self.setFixedHeight(6 * 36 + 22 + 28 + 24)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        month_name = date(self._year, self._month, 1).strftime("%B %Y")
        title = QLabel(month_name)
        title.setObjectName("calendarMonthTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"background-color: {_COLOR_HEADER}; "
            f"color: {_COLOR_HEADER_FG}; "
            "font-weight: bold; "
            "padding: 5px; "
            "border-radius: 4px;"
        )
        root.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(2)

        for col, header in enumerate(self._DAY_HEADERS):
            lbl = QLabel(header)
            lbl.setObjectName("calendarWeekdayLabel")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedSize(40, 22)
            lbl.setStyleSheet(
                f"font-weight: bold; font-size: 11px; color: {_COLOR_MUTED_TEXT};"
            )
            grid.addWidget(lbl, 0, col)

        first_weekday, days_in_month = calendar.monthrange(self._year, self._month)

        row, col = 1, (first_weekday + 1) % 7

        for day in range(1, days_in_month + 1):
            d = date(self._year, self._month, day)
            cell = _DayCell(day, self._color_for(d))
            grid.addWidget(cell, row, col)
            col += 1
            if col == 7:
                col = 0
                row += 1

        root.addLayout(grid)

    def _color_for(self, d: date) -> str:
        if d == date.today():
            return _COLOR_TODAY
        if not self._period.is_date_in_period(d):
            return _COLOR_OUT_OF_PERIOD
        if self._period.is_date_excluded(d):
            return _COLOR_EXCLUDED
        return _COLOR_VALID


class _PeriodCalendar(QWidget):
    """Renders all months that overlap with a single ExamPeriodViewModel."""

    def __init__(self, period: ExamPeriodViewModel, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("periodCalendar")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._period = period
        self._build()

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        for year, month in self._months_in_range():
            grid = _MonthGrid(year, month, self._period)
            grid.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            layout.addWidget(grid)

        layout.addStretch()

    def _months_in_range(self) -> list[tuple[int, int]]:
        start = self._period.start_date
        end = self._period.end_date
        result: list[tuple[int, int]] = []
        year, month = start.year, start.month
        while (year, month) <= (end.year, end.month):
            result.append((year, month))
            month += 1
            if month == 13:
                month = 1
                year += 1
        return result


class _PeriodSection(QWidget):
    """Header + legend + month grids for a single ExamPeriodViewModel."""

    def __init__(self, period: ExamPeriodViewModel, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("calendarPeriodSection")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._period = period
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        label_text = (
            f"{self._period.semester_label} - {self._period.term_label} "
            f"({self._period.start_date.isoformat()} to {self._period.end_date.isoformat()})"
        )
        header = QLabel(label_text)
        header.setObjectName("calendarPeriodHeader")
        root.addWidget(header)
        root.addWidget(self._build_legend())

        root.addWidget(_PeriodCalendar(self._period))

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("calendarDivider")
        root.addWidget(line)

    @staticmethod
    def _build_legend() -> QWidget:
        widget = QWidget()
        widget.setObjectName("calendarLegend")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        for color, text in [
            (_COLOR_VALID, "Available"),
            (_COLOR_EXCLUDED, "Excluded"),
            (_COLOR_OUT_OF_PERIOD, "Outside period"),
            (_COLOR_TODAY, "Today"),
        ]:
            swatch = QLabel()
            swatch.setObjectName("calendarLegendSwatch")
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(
                f"background-color: {color}; "
                f"border: 1px solid {_border_for_cell(color)}; "
                "border-radius: 2px;"
            )
            label = QLabel(text)
            label.setObjectName("calendarLegendLabel")
            layout.addWidget(swatch)
            layout.addWidget(label)
        layout.addStretch()
        return widget


class CalendarView(QWidget):
    """
    Calendar-style screen that displays all loaded exam periods.

    Signals
    -------
    back_requested
        Emitted when the user clicks "Back to Input".
    """

    back_requested = pyqtSignal()
    exclude_day_requested = pyqtSignal(int, object)
    restore_day_requested = pyqtSignal(int, object)
    period_dates_changed = pyqtSignal(int, object, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("calendarView")
        self._build_ui()

    def load_exam_periods(
        self,
        periods: Sequence[ExamPeriodViewModel],
        editable_periods: Sequence[object] | None = None,
        selected_period_index: int | None = None,
        selected_day=None,
    ) -> None:
        """Populate (or refresh) the calendar with the given view models."""
        self._clear_content()

        if editable_periods:
            self._day_editor_card.setVisible(True)
            self.day_editor.setVisible(True)
            self.day_editor.set_periods(
                editable_periods,
                selected_period_index=selected_period_index,
                selected_day=selected_day,
            )
        else:
            self._day_editor_card.setVisible(False)
            self.day_editor.setVisible(False)

        if not periods:
            placeholder = QLabel("No exam periods loaded yet.")
            placeholder.setObjectName("calendarPlaceholderLabel")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._content_layout.addWidget(placeholder)
            self._status_label.setText("No data")
            return

        for period in periods:
            self._content_layout.addWidget(_PeriodSection(period))

        self._content_layout.addStretch()
        total = len(periods)
        self._status_label.setText(
            f"{total} exam period{'s' if total != 1 else ''} loaded"
        )

    def clear(self) -> None:
        self._clear_content()
        self._status_label.setText("Ready")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 24)
        root.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("Exam Period Calendar")
        title.setObjectName("screenTitle")
        self._back_button = QPushButton("Back to Input")
        self._back_button.setObjectName("calendarBackButton")
        self._back_button.clicked.connect(self.back_requested.emit)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._back_button)
        root.addLayout(header)

        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("calendarStatusLabel")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self._status_label)

        self.day_editor = ExamCalendarDayPanel()
        self.day_editor.setVisible(False)
        self.day_editor.exclude_day_requested.connect(
            lambda period_index, day: self.exclude_day_requested.emit(period_index, day)
        )
        self.day_editor.restore_day_requested.connect(
            lambda period_index, day: self.restore_day_requested.emit(period_index, day)
        )
        self.day_editor.period_dates_changed.connect(
            lambda period_index, start_date, end_date: self.period_dates_changed.emit(
                period_index,
                start_date,
                end_date,
            )
        )
        self._day_editor_card = _calendar_card(self.day_editor)
        self._day_editor_card.setVisible(False)
        root.addWidget(self._day_editor_card)

        scroll = QScrollArea()
        scroll.setObjectName("calendarScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content_widget = QWidget()
        content_widget.setObjectName("calendarContent")
        self._content_layout = QVBoxLayout(content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(16)
        self._content_layout.addStretch()

        scroll.setWidget(content_widget)
        root.addWidget(scroll)

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


def _calendar_card(widget: QWidget) -> QWidget:
    card = QWidget()
    card.setObjectName("cardPanel")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(22, 20, 22, 22)
    layout.setSpacing(12)
    layout.addWidget(widget)
    return card


def _border_for_cell(bg_color: str) -> str:
    # The status colors share one helper so the grid and legend stay consistent.
    if bg_color == _COLOR_VALID:
        return _COLOR_VALID_BORDER
    if bg_color == _COLOR_EXCLUDED:
        return _COLOR_EXCLUDED_BORDER
    if bg_color == _COLOR_TODAY:
        return _COLOR_TODAY_BORDER
    return _COLOR_CELL_BORDER
