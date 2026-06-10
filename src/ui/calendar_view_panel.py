"""Calendar-style view for displaying the current exam period."""

from __future__ import annotations

import calendar
from datetime import date
from pathlib import Path
from typing import Sequence

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
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

from src.ui.view_models import ExamPeriodViewModel, ScheduledExamViewModel

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
_DAY_CELL_WIDTH = 76
_DAY_CELL_HEIGHT = 92
_MONTH_GRID_COLUMNS = 2
_WEEK_ROW_COUNT = 6
_MAX_EXAMS_SHOWN_IN_CELL = 2
_DATE_EDIT_WIDTH = 132
_DATE_EDIT_HEIGHT = 34
_INFO_ICON_PATH = Path(__file__).with_name("assets") / "img.png"
_INFO_ICON_SIZE = 18
_CALENDAR_EDIT_HINT = (
    "To exclude or restore a specific day, click the cube of the desired day."
)


class _EmptyDayCell(QFrame):
    """Muted filler cell that keeps each month aligned to a full 6-week grid."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("calendarEmptyDayCell")
        self.setMinimumSize(_DAY_CELL_WIDTH, _DAY_CELL_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            f"background-color: {_COLOR_OUT_OF_PERIOD}; "
            f"border: 1px solid {_COLOR_CELL_BORDER}; "
            "border-radius: 4px;"
        )


class _DayCell(QFrame):
    """Single cell in the calendar grid."""

    clicked = pyqtSignal(object)

    def __init__(
        self,
        day_number: int | None,
        bg_color: str,
        exams: Sequence[ScheduledExamViewModel] = (),
        day_date: date | None = None,
        is_togglable: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("calendarDayCell")
        self.setMinimumSize(_DAY_CELL_WIDTH, _DAY_CELL_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._day_number = day_number
        # Only real, editable dates get stored here; filler cells and output previews stay passive.
        self._day_date = day_date
        self._is_togglable = is_togglable
        self._exams = tuple(exams)
        if self._is_togglable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style(bg_color)
        self._build()

    def text(self) -> str:
        return "" if self._day_number is None else str(self._day_number)

    def exam_text(self) -> str:
        compact = len(self._exams) > 1
        return "\n".join(_exam_cell_text(exam, compact=compact) for exam in self._exams)

    def set_exclusion_state(self, is_excluded: bool) -> None:
        # Toggling availability should only repaint the square; exam labels stay untouched.
        color = _COLOR_EXCLUDED if is_excluded else _COLOR_VALID
        self._apply_style(color)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 4, 5, 4)
        layout.setSpacing(2)

        day_label = QLabel(self.text())
        day_label.setObjectName("calendarDayNumber")
        day_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        day_label.setStyleSheet("font-size: 11px; font-weight: 700; background: transparent;")
        layout.addWidget(day_label)

        compact = len(self._exams) > 1
        for exam in self._exams[:_MAX_EXAMS_SHOWN_IN_CELL]:
            exam_label = QLabel(_exam_cell_text(exam, compact=compact))
            exam_label.setObjectName("calendarExamItem")
            exam_label.setToolTip(_exam_tooltip(exam))
            exam_label.setWordWrap(True)
            exam_label.setStyleSheet(
                "background: #1f2024; "
                "color: #f1f3f5; "
                "border: 1px solid #60758f; "
                "border-radius: 3px; "
                "padding: 1px 3px; "
                "font-size: 10px;"
            )
            layout.addWidget(exam_label)

        hidden_count = len(self._exams) - _MAX_EXAMS_SHOWN_IN_CELL
        if hidden_count > 0:
            more_label = QLabel(f"+{hidden_count} more")
            more_label.setObjectName("calendarExamMore")
            more_label.setStyleSheet("font-size: 10px; color: #d7dce2; background: transparent;")
            layout.addWidget(more_label)

        if self._exams:
            self.setToolTip("\n\n".join(_exam_tooltip(exam) for exam in self._exams))

        layout.addStretch()

    def mouseReleaseEvent(self, event) -> None:
        # Treat a normal left-click as a request, then let MainWindow decide exclude vs restore.
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._is_togglable
            and self._day_date is not None
        ):
            self.clicked.emit(self._day_date)
            event.accept()
            return

        super().mouseReleaseEvent(event)

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
    day_clicked = pyqtSignal(object)

    def __init__(
        self,
        year: int,
        month: int,
        period: ExamPeriodViewModel,
        is_editable: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("calendarMonthGrid")
        self._year = year
        self._month = month
        self._period = period
        self._is_editable = is_editable
        # Editable cells are kept by date so one click can repaint one cell without rebuilding the month.
        self._day_cells_by_date: dict[date, _DayCell] = {}
        self._build()
        # Six week rows plus header/title spacing keeps adjacent month grids aligned.
        self.setMinimumHeight(6 * _DAY_CELL_HEIGHT + 22 + 28 + 24)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

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
            lbl.setMinimumSize(_DAY_CELL_WIDTH, 22)
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            lbl.setStyleSheet(
                f"font-weight: bold; font-size: 11px; color: {_COLOR_MUTED_TEXT};"
            )
            grid.addWidget(lbl, 0, col)
            grid.setColumnStretch(col, 1)

        first_weekday, days_in_month = calendar.monthrange(self._year, self._month)

        row, col = 1, (first_weekday + 1) % 7
        for blank_col in range(col):
            grid.addWidget(_EmptyDayCell(), row, blank_col)

        for day in range(1, days_in_month + 1):
            d = date(self._year, self._month, day)
            is_in_period = self._period.is_date_in_period(d)
            # The same month grid is reused by output previews, so editability stays opt-in.
            is_togglable = self._is_editable and is_in_period
            cell = _DayCell(
                day,
                self._color_for(d),
                self._period.exams_on(d),
                day_date=d if is_togglable else None,
                is_togglable=is_togglable,
            )
            if is_togglable:
                self._day_cells_by_date[d] = cell
                cell.clicked.connect(self.day_clicked.emit)
            grid.addWidget(cell, row, col)
            col += 1
            if col == 7:
                col = 0
                row += 1

        while row <= _WEEK_ROW_COUNT:
            grid.addWidget(_EmptyDayCell(), row, col)
            col += 1
            if col == 7:
                col = 0
                row += 1

        for week_row in range(1, _WEEK_ROW_COUNT + 1):
            grid.setRowMinimumHeight(week_row, _DAY_CELL_HEIGHT)

        root.addLayout(grid)

    def update_day_status(self, day: date, is_excluded: bool) -> bool:
        # Only editable, in-period days are indexed here; everything else should stay passive.
        cell = self._day_cells_by_date.get(day)
        if cell is None:
            return False

        cell.set_exclusion_state(is_excluded)
        return True

    def _color_for(self, d: date) -> str:
        if not self._period.is_date_in_period(d):
            # Inside a period, green/red must win so the toggle state is always visible.
            if d == date.today():
                return _COLOR_TODAY
            return _COLOR_OUT_OF_PERIOD
        if self._period.is_date_excluded(d):
            return _COLOR_EXCLUDED
        return _COLOR_VALID


class _PeriodCalendar(QWidget):
    """Renders all months that overlap with a single ExamPeriodViewModel."""

    day_clicked = pyqtSignal(object)

    def __init__(
        self,
        period: ExamPeriodViewModel,
        is_editable: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("periodCalendar")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._period = period
        self._is_editable = is_editable
        self._month_grids: list[_MonthGrid] = []
        self._build()

    def _build(self) -> None:
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        for index, (year, month) in enumerate(self._months_in_range()):
            grid = _MonthGrid(year, month, self._period, is_editable=self._is_editable)
            grid.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            # Bubble the date upward without teaching the month grid about period indexes.
            grid.day_clicked.connect(self.day_clicked.emit)
            self._month_grids.append(grid)
            row = index // _MONTH_GRID_COLUMNS
            column = index % _MONTH_GRID_COLUMNS
            layout.addWidget(grid, row, column)

        for column in range(_MONTH_GRID_COLUMNS):
            layout.setColumnStretch(column, 1)

    def update_day_status(self, day: date, is_excluded: bool) -> bool:
        # A period may span several months, so ask each month until the matching square is found.
        for grid in self._month_grids:
            if grid.update_day_status(day, is_excluded):
                return True
        return False

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

    day_clicked = pyqtSignal(int, object)

    def __init__(
        self,
        period_index: int,
        period: ExamPeriodViewModel,
        is_editable: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("calendarPeriodSection")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._period_index = period_index
        self._period = period
        self._is_editable = is_editable
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        label_text = (
            f"{self._period.semester_label} - {self._period.term_label} "
            f"({self._period.start_date.isoformat()} to {self._period.end_date.isoformat()})"
        )
        header = QLabel(label_text)
        header.setObjectName("calendarPeriodHeader")
        root.addWidget(header)
        root.addWidget(self._build_legend())

        self._calendar_widget = _PeriodCalendar(self._period, is_editable=self._is_editable)
        self._calendar_widget.day_clicked.connect(
            # Add the period index at this boundary; lower widgets only know about dates.
            lambda day: self.day_clicked.emit(self._period_index, day)
        )
        root.addWidget(self._calendar_widget)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("calendarDivider")
        root.addWidget(line)

    def update_day_status(self, day: date, is_excluded: bool) -> bool:
        return self._calendar_widget.update_day_status(day, is_excluded)

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


class CalendarPeriodList(QWidget):
    """Reusable calendar body for screens that need to show exam periods."""

    day_clicked = pyqtSignal(int, object)

    def __init__(
        self,
        empty_text: str,
        is_editable: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._is_editable = is_editable
        self._empty_text = empty_text
        self._period_sections: dict[int, _PeriodSection] = {}
        self._content_layout = QVBoxLayout(self)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(16)
        self._content_layout.addStretch()

    def set_empty_text(self, text: str) -> None:
        self._empty_text = text

    def load_periods(self, periods: Sequence[ExamPeriodViewModel]) -> None:
        self._clear_content()

        if not periods:
            placeholder = QLabel(self._empty_text)
            placeholder.setObjectName("calendarPlaceholderLabel")
            placeholder.setWordWrap(True)
            placeholder.setMaximumWidth(680)
            placeholder.setMinimumHeight(76)
            placeholder.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.Minimum,
            )
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._content_layout.addStretch(1)
            self._content_layout.addWidget(
                placeholder,
                0,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            )
            self._content_layout.addStretch(1)
            return

        for period_index, period in enumerate(periods):
            section = _PeriodSection(
                period_index,
                period,
                is_editable=self._is_editable,
            )
            section.day_clicked.connect(self.day_clicked.emit)
            self._period_sections[period_index] = section
            self._content_layout.addWidget(section)

        self._content_layout.addStretch()

    def update_day_status(self, period_index: int, day: date, is_excluded: bool) -> bool:
        # Period indexes come from the currently loaded list, the same list the user is seeing.
        section = self._period_sections.get(period_index)
        if section is None:
            return False
        return section.update_day_status(day, is_excluded)

    def _clear_content(self) -> None:
        self._period_sections.clear()
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                # Detach first so the old calendar disappears before Qt deletes it.
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()


class _PeriodDateRangeEditor(QWidget):
    """Small editor for the loaded exam-period boundaries."""

    period_dates_changed = pyqtSignal(int, object, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._periods: tuple[ExamPeriodViewModel, ...] = ()
        self._syncing_date_fields = False

        self.title_label = QLabel("Exam Period Dates")
        self.title_label.setObjectName("sectionTitleLabel")
        self.period_selector = QComboBox()
        self.period_selector.setObjectName("examPeriodSelector")
        self.start_date_edit = _date_edit("periodStartDateEdit")
        self.end_date_edit = _date_edit("periodEndDateEdit")

        self._build_ui()
        self._connect_signals()
        self._set_enabled(False)

    def set_periods(
        self,
        periods: Sequence[ExamPeriodViewModel],
        selected_period_index: int | None = None,
    ) -> None:
        self._periods = tuple(periods)
        self._populate_period_selector(selected_period_index)
        self._sync_date_fields(self._current_period())
        self._set_enabled(bool(self._periods))

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.title_label)
        header.addWidget(self._build_instruction_panel(), 1)
        header.addStretch(1)
        header.addWidget(self.period_selector)
        root.addLayout(header)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.addWidget(QLabel("Start Date"))
        controls.addWidget(self.start_date_edit)
        controls.addWidget(QLabel("End Date"))
        controls.addWidget(self.end_date_edit)
        controls.addStretch(1)
        root.addLayout(controls)

    def _connect_signals(self) -> None:
        self.period_selector.currentIndexChanged.connect(
            lambda _index: self._sync_date_fields(self._current_period())
        )
        self.start_date_edit.dateChanged.connect(lambda _date: self._emit_dates_changed())
        self.end_date_edit.dateChanged.connect(lambda _date: self._emit_dates_changed())

    def _populate_period_selector(self, selected_period_index: int | None) -> None:
        self.period_selector.blockSignals(True)
        try:
            self.period_selector.clear()
            for index, period in enumerate(self._periods):
                self.period_selector.addItem(_period_label(period), index)

            if not self._periods:
                return

            target_index = selected_period_index or 0
            if target_index < 0 or target_index >= len(self._periods):
                target_index = 0
            self.period_selector.setCurrentIndex(target_index)
        finally:
            self.period_selector.blockSignals(False)

    def _sync_date_fields(self, period: ExamPeriodViewModel | None) -> None:
        self._syncing_date_fields = True
        try:
            if period is not None:
                self.start_date_edit.setDate(_date_to_qdate(period.start_date))
                self.end_date_edit.setDate(_date_to_qdate(period.end_date))
        finally:
            self._syncing_date_fields = False

    def _emit_dates_changed(self) -> None:
        if self._syncing_date_fields:
            return

        period_index = self.period_selector.currentData()
        if period_index is None:
            return

        # Keep Qt's date type inside the widget and send plain Python dates outward.
        self.period_dates_changed.emit(
            int(period_index),
            _qdate_to_date(self.start_date_edit.date()),
            _qdate_to_date(self.end_date_edit.date()),
        )

    def _current_period(self) -> ExamPeriodViewModel | None:
        period_index = self.period_selector.currentData()
        if period_index is None:
            return None
        try:
            return self._periods[int(period_index)]
        except IndexError:
            return None

    def _set_enabled(self, enabled: bool) -> None:
        self.period_selector.setEnabled(enabled)
        self.start_date_edit.setEnabled(enabled)
        self.end_date_edit.setEnabled(enabled)

    def _build_instruction_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("calendarInstructionPanel")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self._instruction_icon_label = QLabel()
        self._instruction_icon_label.setObjectName("calendarInstructionIcon")
        self._instruction_icon_label.setFixedSize(24, 24)
        self._instruction_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pixmap = QPixmap(str(_INFO_ICON_PATH))
        if pixmap.isNull():
            self._instruction_icon_label.setText("i")
        else:
            self._instruction_icon_label.setPixmap(
                pixmap.scaled(
                    _INFO_ICON_SIZE,
                    _INFO_ICON_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        self._instruction_label = QLabel(_CALENDAR_EDIT_HINT)
        self._instruction_label.setObjectName("calendarInstructionLabel")
        self._instruction_label.setWordWrap(False)

        layout.addWidget(self._instruction_icon_label)
        layout.addWidget(self._instruction_label, 1)
        return panel


class CalendarView(QWidget):
    """
    Calendar-style screen that displays all loaded exam periods.

    Signals
    -------
    back_requested
        Emitted when the user clicks "Back to Input".
    """

    back_requested = pyqtSignal()
    day_clicked = pyqtSignal(int, object)
    period_dates_changed = pyqtSignal(int, object, object)

    def __init__(self, parent=None, show_back_button: bool = True) -> None:
        super().__init__(parent)
        self._show_back_button = show_back_button
        self.setObjectName("calendarView")
        self._build_ui()

    def load_exam_periods(
        self,
        periods: Sequence[ExamPeriodViewModel],
        selected_period_index: int | None = None,
    ) -> None:
        """Populate (or refresh) the calendar with the given view models."""
        self.period_date_editor.set_periods(periods, selected_period_index)
        self._calendar_periods.load_periods(periods)
        # Full reloads are for changed ranges or schedules; simple day toggles repaint in place.
        self._scroll_area.verticalScrollBar().setValue(0)

        if not periods:
            self._status_label.setText("No data")
            return

        total = len(periods)
        self._status_label.setText(
            f"{total} exam period{'s' if total != 1 else ''} loaded"
        )

    def update_day_status(self, period_index: int, day: date, is_excluded: bool) -> bool:
        return self._calendar_periods.update_day_status(period_index, day, is_excluded)

    def clear(self) -> None:
        self._calendar_periods.load_periods(())
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
        if self._show_back_button:
            header.addWidget(self._back_button)
        else:
            self._back_button.setVisible(False)
        root.addLayout(header)

        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("calendarStatusLabel")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self._status_label)

        self.period_date_editor = _PeriodDateRangeEditor()
        self.period_date_editor.period_dates_changed.connect(
            self.period_dates_changed.emit
        )
        root.addWidget(_calendar_card(self.period_date_editor))

        self._scroll_area = QScrollArea()
        self._scroll_area.setObjectName("calendarScroll")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._calendar_periods = CalendarPeriodList(
            "No exam periods loaded yet.",
            is_editable=True,
        )
        self._calendar_periods.setObjectName("calendarContent")
        # CalendarView exposes one screen-level signal instead of leaking the widget tree.
        self._calendar_periods.day_clicked.connect(self.day_clicked.emit)
        self._scroll_area.setWidget(self._calendar_periods)
        root.addWidget(self._scroll_area)


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


def _clip_cell_text(value: str, limit: int = 24) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _exam_cell_text(exam: ScheduledExamViewModel, *, compact: bool = False) -> str:
    if compact:
        return _clip_cell_text(exam.calendar_label, limit=20)
    # First line: course. Second line: compact program and requirement context.
    lines = [_clip_cell_text(exam.calendar_label)]
    if exam.calendar_detail:
        lines.append(_clip_cell_text(exam.calendar_detail, limit=30))
    return "\n".join(lines)


def _exam_tooltip(exam: ScheduledExamViewModel) -> str:
    # The tooltip keeps the full values when the calendar cell has clipped them.
    lines = [exam.calendar_label, exam.exam_date.isoformat()]
    if exam.instructor:
        lines.append(exam.instructor)
    if exam.program_ids:
        lines.append("Programs: " + ", ".join(str(program_id) for program_id in exam.program_ids))
    if exam.requirement_types:
        lines.append("Requirements: " + ", ".join(exam.requirement_types))
    return "\n".join(lines)


def _period_label(period: ExamPeriodViewModel) -> str:
    return (
        f"{period.semester_label} / {period.term_label} "
        f"({period.start_date:%d-%m-%Y} - {period.end_date:%d-%m-%Y})"
    )


def _date_edit(object_name: str) -> QDateEdit:
    edit = QDateEdit()
    edit.setObjectName(object_name)
    edit.setCalendarPopup(True)
    edit.setDisplayFormat("dd-MM-yyyy")
    edit.setMinimumWidth(_DATE_EDIT_WIDTH)
    edit.setMinimumHeight(_DATE_EDIT_HEIGHT)
    return edit


def _date_to_qdate(value: date) -> QDate:
    return QDate(value.year, value.month, value.day)


def _qdate_to_date(value: QDate) -> date:
    return date(value.year(), value.month(), value.day())

