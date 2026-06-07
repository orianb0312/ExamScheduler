from datetime import date

from PyQt6.QtCore import QDate, Qt

from src.models.enums import Semester, Term
from src.models.scheduling import DateExclusion, ExamPeriod
from src.ui.exam_calendar_day_panel import (
    CALENDAR_DAY_TABLE_MIN_HEIGHT,
    ExamCalendarDayPanel,
)


def _period() -> ExamPeriod:
    return ExamPeriod(
        semester=Semester.FALL,
        term=Term.ALEPH,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 3),
        exclusions=[DateExclusion(start_date=date(2026, 1, 2))],
    )


def _table_statuses(panel: ExamCalendarDayPanel) -> list[str]:
    return [
        panel.day_table.item(row, 1).text()
        for row in range(panel.day_table.rowCount())
    ]


def test_panel_displays_days_and_existing_exclusions(qtbot):
    panel = ExamCalendarDayPanel()
    qtbot.addWidget(panel)

    panel.set_periods([_period()])

    assert panel.period_selector.count() == 1
    assert panel.start_date_edit.date() == QDate(2026, 1, 1)
    assert panel.end_date_edit.date() == QDate(2026, 1, 3)
    assert panel.day_table.rowCount() == 3
    assert panel.day_table.minimumHeight() == CALENDAR_DAY_TABLE_MIN_HEIGHT
    assert _table_statuses(panel) == ["Available", "Excluded", "Available"]


def test_panel_emits_exclude_for_selected_available_day(qtbot):
    panel = ExamCalendarDayPanel()
    qtbot.addWidget(panel)
    panel.set_periods([_period()])
    panel.day_table.selectRow(0)

    with qtbot.waitSignal(panel.exclude_day_requested, timeout=1000) as blocker:
        qtbot.mouseClick(panel.exclude_button, Qt.MouseButton.LeftButton)

    assert blocker.args == [0, date(2026, 1, 1)]


def test_panel_emits_restore_for_selected_excluded_day(qtbot):
    panel = ExamCalendarDayPanel()
    qtbot.addWidget(panel)
    panel.set_periods([_period()])
    panel.day_table.selectRow(1)

    with qtbot.waitSignal(panel.restore_day_requested, timeout=1000) as blocker:
        qtbot.mouseClick(panel.restore_button, Qt.MouseButton.LeftButton)

    assert blocker.args == [0, date(2026, 1, 2)]


def test_panel_emits_period_dates_when_date_field_changes(qtbot):
    panel = ExamCalendarDayPanel()
    qtbot.addWidget(panel)
    panel.set_periods([_period()])

    with qtbot.waitSignal(panel.period_dates_changed, timeout=1000) as blocker:
        panel.start_date_edit.setDate(QDate(2026, 1, 2))

    assert blocker.args == [
        0,
        date(2026, 1, 2),
        date(2026, 1, 3),
    ]
