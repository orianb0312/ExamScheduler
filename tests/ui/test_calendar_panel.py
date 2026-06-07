from __future__ import annotations

from datetime import date

import pytest
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import QLabel
from pytestqt.qtbot import QtBot

from src.models.enums import Semester, Term
from src.models.scheduling import ExamPeriod
from src.services.cli_run_service import CliRunConfig
from src.services.file_loading_service import LoadedSchedulerInput
from src.ui.calendar_view import OutputView
from src.ui.calendar_view_panel import CalendarView, _MonthGrid, _PeriodSection
from src.ui.main_window import MainWindow
from src.ui.view_models import ExamPeriodViewModel, ExclusionViewModel


@pytest.fixture()
def simple_period() -> ExamPeriodViewModel:
    return ExamPeriodViewModel(
        semester_label="Semester A",
        term_label="Moed A",
        start_date=date(2025, 1, 5),
        end_date=date(2025, 2, 20),
        exclusions=(ExclusionViewModel(start_date=date(2025, 1, 15), end_date=None),),
    )


def test_exam_period_view_model_logic(simple_period: ExamPeriodViewModel) -> None:
    assert simple_period.is_date_in_period(date(2025, 1, 5))
    assert not simple_period.is_date_in_period(date(2025, 2, 21))
    assert simple_period.is_date_excluded(date(2025, 1, 15))
    assert not simple_period.is_date_excluded(date(2025, 1, 10))


def test_month_grid_cell_background_colors(qtbot: QtBot, simple_period: ExamPeriodViewModel) -> None:
    grid = _MonthGrid(2025, 1, simple_period)
    qtbot.addWidget(grid)

    from src.ui.calendar_view_panel import _DayCell

    cells = {int(c.text()): c for c in grid.findChildren(_DayCell) if c.text().isdigit()}

    assert "#244d3a" in cells[10].styleSheet()
    assert "#5a2f3c" in cells[15].styleSheet()
    assert "#2b303a" in cells[1].styleSheet()


def test_period_section_header_and_legend(qtbot: QtBot, simple_period: ExamPeriodViewModel) -> None:
    section = _PeriodSection(simple_period)
    qtbot.addWidget(section)

    texts = [lbl.text() for lbl in section.findChildren(QLabel)]

    assert any("Semester A" in t and "Moed A" in t for t in texts)
    assert any("2025-01-05" in t and "2025-02-20" in t for t in texts)

    for expected_label in ("Available", "Excluded", "Outside period", "Today"):
        assert any(expected_label in t for t in texts)


def test_calendar_view_loading_and_layout(qtbot: QtBot, simple_period: ExamPeriodViewModel) -> None:
    view = CalendarView()
    qtbot.addWidget(view)

    view.load_exam_periods([simple_period])

    assert "1 exam period" in view._status_label.text()
    assert len(view.findChildren(_MonthGrid)) == 2


def test_main_window_keeps_calendar_and_output_screens_separate(tmp_path, qtbot: QtBot) -> None:
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    assert isinstance(window.calendar_view, CalendarView)
    assert isinstance(window.output_view, OutputView)
    assert window.calendar_view is not window.output_view


def test_calendar_button_opens_day_editor_and_updates_status(tmp_path, qtbot: QtBot) -> None:
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)
    loaded_data = LoadedSchedulerInput(
        courses=(),
        exam_periods=(
            ExamPeriod(
                semester=Semester.FALL,
                term=Term.ALEPH,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 3),
            ),
        ),
        programs=(),
    )

    window.input_panel.notify_data_loaded(loaded_data)
    window.input_panel.set_data_load_success(0, 1, 0)

    assert window.input_panel.view_calendar_button.isEnabled()

    qtbot.mouseClick(window.input_panel.view_calendar_button, Qt.MouseButton.LeftButton)

    assert window._stack.currentWidget() is window.calendar_view
    assert not window.calendar_view.day_editor.isHidden()
    assert window.calendar_view.day_editor.day_table.rowCount() == 3

    window.calendar_view.day_editor.day_table.selectRow(1)
    qtbot.mouseClick(
        window.calendar_view.day_editor.exclude_button,
        Qt.MouseButton.LeftButton,
    )
    assert window.calendar_view.day_editor.day_table.item(1, 1).text() == "Excluded"

    qtbot.mouseClick(
        window.calendar_view.day_editor.restore_button,
        Qt.MouseButton.LeftButton,
    )
    assert window.calendar_view.day_editor.day_table.item(1, 1).text() == "Available"


def test_calendar_date_fields_update_period_range(tmp_path, qtbot: QtBot) -> None:
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)
    loaded_data = LoadedSchedulerInput(
        courses=(),
        exam_periods=(
            ExamPeriod(
                semester=Semester.FALL,
                term=Term.ALEPH,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 3),
            ),
        ),
        programs=(),
    )

    window.input_panel.notify_data_loaded(loaded_data)
    window.input_panel.set_data_load_success(0, 1, 0)
    qtbot.mouseClick(window.input_panel.view_calendar_button, Qt.MouseButton.LeftButton)

    # Changing the calendar-screen date fields should update the shared scheduler state.
    window.calendar_view.day_editor.end_date_edit.setDate(QDate(2026, 1, 4))

    assert window.input_panel.exam_periods[0].end_date == date(2026, 1, 4)
    assert window.calendar_view.day_editor.day_table.rowCount() == 4

    window.calendar_view.day_editor.start_date_edit.setDate(QDate(2026, 1, 2))

    assert window.input_panel.exam_periods[0].start_date == date(2026, 1, 2)
    assert window.calendar_view.day_editor.day_table.rowCount() == 3


def test_finished_run_loads_generated_output_file_into_output_view(tmp_path, qtbot: QtBot) -> None:
    config_path = tmp_path / "config.json"
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    config_path.write_text(
        """
{
  "output_settings": {
    "base_directory": "outputs",
    "master_filename": "ui_schedule"
  }
}
""",
        encoding="utf-8",
    )
    (output_dir / "ui_schedule.txt").write_text(
        "OFFICIAL UNIVERSITY MASTER EXAM SCHEDULE\n"
        "Schedule #1\n"
        "Course A | 2026-01-01 | Dr. A\n"
        "Schedule #2\n"
        "Course B | 2026-01-02 | Dr. B\n",
        encoding="utf-8",
    )
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)
    window._active_run_config = CliRunConfig(
        project_root=tmp_path,
        mode="period",
        output_config=config_path,
    )

    window._handle_finished(0, "NormalExit")

    assert window.output_view.cache.system_count == 2
    assert "Course A" in window.output_view.system_view.toPlainText()

