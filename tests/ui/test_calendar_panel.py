"""
Consolidated test suite for CalendarView.
Covers view model logic, UI rendering colors, layout structure, and widget integration.

"""

from __future__ import annotations
from datetime import date
import pytest
from pytestqt.qtbot import QtBot
from PyQt6.QtWidgets import QLabel

from src.ui.calendar_view_panel import CalendarView, _MonthGrid, _PeriodSection
from src.ui.view_models import ExamPeriodViewModel, ExclusionViewModel


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def simple_period() -> ExamPeriodViewModel:
    """A two-month exam period (Jan-Feb 2025) with one excluded day (Jan 15)."""
    return ExamPeriodViewModel(
        semester_label="Semester A",
        term_label="Moed A",
        start_date=date(2025, 1, 5),
        end_date=date(2025, 2, 20),
        exclusions=(ExclusionViewModel(start_date=date(2025, 1, 15), end_date=None),),
    )


# ---------------------------------------------------------------------------
# Core Tests
# ---------------------------------------------------------------------------

def test_exam_period_view_model_logic(simple_period: ExamPeriodViewModel) -> None:
    """
    Pure logic test: Verify boundary conditions and exclusion checks
    within the ExamPeriodViewModel (no Qt widgets required).
    """
    assert simple_period.is_date_in_period(date(2025, 1, 5))       # Boundary: Start date (Inside)
    assert not simple_period.is_date_in_period(date(2025, 2, 21))  # Boundary: After period (Outside)
    assert simple_period.is_date_excluded(date(2025, 1, 15))       # Explicitly excluded day
    assert not simple_period.is_date_excluded(date(2025, 1, 10))   # Regular available day


def test_month_grid_cell_background_colors(qtbot: QtBot, simple_period: ExamPeriodViewModel) -> None:
    """
    UI Palette test: Verify that _MonthGrid applies the correct
    stylesheet background colors based on day status.
    """
    grid = _MonthGrid(2025, 1, simple_period)
    qtbot.addWidget(grid)

    from src.ui.calendar_view_panel import _DayCell
    # Extract all rendered DayCells that contain actual day numbers
    cells = {int(c.text()): c for c in grid.findChildren(_DayCell) if c.text().isdigit()}

    assert "#d4edda" in cells[10].styleSheet()  # Day 10: Available (Green / _COLOR_VALID)
    assert "#f8d7da" in cells[15].styleSheet()  # Day 15: Excluded (Red / _COLOR_EXCLUDED)
    assert "#f0f0f0" in cells[1].styleSheet()   # Day 1: Outside period (Grey / _COLOR_OUT_OF_PERIOD)


def test_period_section_header_and_legend(qtbot: QtBot, simple_period: ExamPeriodViewModel) -> None:
    """
    Layout content test: Verify that _PeriodSection correctly renders
    the semester metadata header and all 4 status indicators in the legend.
    """
    section = _PeriodSection(simple_period)
    qtbot.addWidget(section)

    texts = [lbl.text() for lbl in section.findChildren(QLabel)]

    # Assert Header text structure contains labels and critical date ranges
    assert any("Semester A" in t and "Moed A" in t for t in texts)
    assert any("2025-01-05" in t and "2025-02-20" in t for t in texts)

    # Assert all four visual indicator descriptions exist in the legend layout
    for expected_label in ("Available", "Excluded", "Outside period", "Today"):
        assert any(expected_label in t for t in texts)


def test_calendar_view_loading_and_layout(qtbot: QtBot, simple_period: ExamPeriodViewModel) -> None:
    """
    Integration layout test: Verify CalendarView correctly reflects
    the status text and spawns the correct number of months spanning the period.
    """
    view = CalendarView()
    qtbot.addWidget(view)

    # Act: Load a single period that spans across 2 months (January & February)
    view.load_exam_periods([simple_period])

    # Assert status bar updates dynamically and sub-grids are fully generated
    assert "1 exam period" in view._status_label.text()
    assert len(view.findChildren(_MonthGrid)) == 2

