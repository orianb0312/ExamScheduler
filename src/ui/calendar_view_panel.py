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

from src.ui.view_models import ExamPeriodViewModel

# ---------------------------------------------------------------------------
# Palette constants
# ---------------------------------------------------------------------------
_COLOR_VALID = "#d4edda"
_COLOR_EXCLUDED = "#f8d7da"
_COLOR_OUT_OF_PERIOD = "#f0f0f0"
_COLOR_TODAY = "#fff3cd"
_COLOR_HEADER = "#343a40"
_COLOR_HEADER_FG = "#ffffff"


class _DayCell(QLabel):
    """Single cell in the calendar grid."""

    def __init__(self, day_number: int | None, bg_color: str, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(40, 36)
        if day_number is not None:
            self.setText(str(day_number))
        self._apply_style(bg_color)

    def _apply_style(self, bg_color: str) -> None:
        self.setStyleSheet(
            f"background-color: {bg_color}; "
            "border: 1px solid #dee2e6; "
            "border-radius: 4px; "
            "font-size: 12px;"
        )


class _MonthGrid(QWidget):
    """
    Renders a single month as a 7-column grid (Mon–Sun header + day cells).
    Days are coloured according to their status within the given ExamPeriodViewModel.
    """

    _DAY_HEADERS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")

    def __init__(self, year: int, month: int, period: ExamPeriodViewModel, parent=None) -> None:
        super().__init__(parent)
        self._year = year
        self._month = month
        self._period = period
        self._build()
        # 6 possible week-rows × 36px + header row 22px + month title ~28px + spacing
        self.setFixedHeight(6 * 36 + 22 + 28 + 24)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        month_name = date(self._year, self._month, 1).strftime("%B %Y")
        title = QLabel(month_name)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"background-color: {_COLOR_HEADER}; "
            f"color: {_COLOR_HEADER_FG}; "
            "font-weight: bold; "
            "padding: 4px; "
            "border-radius: 4px;"
        )
        root.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(2)

        for col, header in enumerate(self._DAY_HEADERS):
            lbl = QLabel(header)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedSize(40, 22)
            lbl.setStyleSheet("font-weight: bold; font-size: 11px; color: #495057;")
            grid.addWidget(lbl, 0, col)

        first_weekday, days_in_month = calendar.monthrange(self._year, self._month)
        row, col = 1, first_weekday

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
        self._period = period
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        label_text = (
            f"{self._period.semester_label}  ·  {self._period.term_label}  "
            f"({self._period.start_date.isoformat()} → {self._period.end_date.isoformat()})"
        )
        header = QLabel(label_text)
        header.setStyleSheet(
            "font-weight: bold; font-size: 13px; padding: 6px 10px; "
            "background-color: #e9ecef; border-radius: 4px;"
        )
        root.addWidget(header)
        root.addWidget(self._build_legend())

        root.addWidget(_PeriodCalendar(self._period))

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #dee2e6;")
        root.addWidget(line)

    @staticmethod
    def _build_legend() -> QWidget:
        widget = QWidget()
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
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(
                f"background-color: {color}; border: 1px solid #adb5bd; border-radius: 2px;"
            )
            label = QLabel(text)
            label.setStyleSheet("font-size: 11px; color: #495057;")
            layout.addWidget(swatch)
            layout.addWidget(label)
        layout.addStretch()
        return widget


class CalendarView(QWidget):
    """
    Calendar-style screen that displays all loaded exam periods.

    Receives only ExamPeriodViewModel objects — no dependency on the domain model.
    MainWindow is responsible for the conversion before calling load_exam_periods.

    Signals
    -------
    back_requested
        Emitted when the user clicks "Back to Input".
    """

    back_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def load_exam_periods(self, periods: Sequence[ExamPeriodViewModel]) -> None:
        """Populate (or refresh) the calendar with the given view models."""
        self._clear_content()

        if not periods:
            placeholder = QLabel("No exam periods loaded yet.")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("color: #6c757d; font-size: 13px;")
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
        root.setContentsMargins(16, 18, 18, 18)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Exam Period Calendar")
        title.setObjectName("screenTitle")
        self._back_button = QPushButton("Back to Scheduler")
        self._back_button.clicked.connect(self.back_requested.emit)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._back_button)
        root.addLayout(header)

        self._status_label = QLabel("Ready")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self._status_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content_widget = QWidget()
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