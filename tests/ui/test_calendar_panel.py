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
from src.services.schedule_output_service import (
    ScheduleExamDisplay,
    SchedulePeriodDisplay,
    ScheduleSystem,
)
from src.ui.calendar_view import OutputView
from src.ui.calendar_view_panel import CalendarView, _DayCell, _MonthGrid, _PeriodSection
from src.ui.main_window import MainWindow
from src.ui.view_models import (
    ExamPeriodViewModel,
    ExclusionViewModel,
    ScheduledExamViewModel,
)


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
    assert simple_period.exams_on(date(2025, 1, 10)) == ()


def test_month_grid_cell_background_colors(qtbot: QtBot, simple_period: ExamPeriodViewModel) -> None:
    grid = _MonthGrid(2025, 1, simple_period)
    qtbot.addWidget(grid)

    cells = {int(c.text()): c for c in grid.findChildren(_DayCell) if c.text().isdigit()}

    assert "#244d3a" in cells[10].styleSheet()
    assert "#5a2f3c" in cells[15].styleSheet()
    assert "#2b303a" in cells[1].styleSheet()


def test_month_grid_displays_exam_inside_matching_day_cell(qtbot: QtBot) -> None:
    period = ExamPeriodViewModel(
        semester_label="FALL",
        term_label="Aleph",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        scheduled_exams=(
            ScheduledExamViewModel(
                course_name="Algorithms",
                course_id=10001,
                exam_date=date(2026, 1, 10),
                instructor="Dr. Ada",
                program_ids=(83101,),
                requirement_types=("Obligatory",),
            ),
        ),
    )
    grid = _MonthGrid(2026, 1, period)
    qtbot.addWidget(grid)

    cells = {int(c.text()): c for c in grid.findChildren(_DayCell) if c.text().isdigit()}
    day_ten_labels = [label.text() for label in cells[10].findChildren(QLabel)]

    assert "Algorithms (10001)" in cells[10].exam_text()
    assert "83101 | Obligatory" in cells[10].exam_text()
    assert any("Algorithms" in text for text in day_ten_labels)
    assert cells[11].exam_text() == ""


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


def test_output_view_selected_schedule_follows_visible_page(qtbot: QtBot) -> None:
    view = OutputView()
    qtbot.addWidget(view)

    view.add_systems([
        ScheduleSystem(number=1, text="Schedule #1"),
        ScheduleSystem(number=2, text="Schedule #2"),
    ])

    assert view.selected_schedule is not None
    assert view.selected_schedule.number == 1

    qtbot.mouseClick(view.pagination_bar.next_button, Qt.MouseButton.LeftButton)

    assert view.selected_schedule is not None
    assert view.selected_schedule.number == 2


def test_output_view_label_uses_known_total_count(qtbot: QtBot) -> None:
    view = OutputView()
    qtbot.addWidget(view)
    view.set_schedule_total(12)

    view.add_systems([
        ScheduleSystem(number=1, text="Schedule #1"),
        ScheduleSystem(number=2, text="Schedule #2"),
    ])

    assert view.schedule_label.text() == "Schedule 1 of 12"

    qtbot.mouseClick(view.pagination_bar.next_button, Qt.MouseButton.LeftButton)

    assert view.schedule_label.text() == "Schedule 2 of 12"


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


def test_calendar_refreshes_when_selected_schedule_changes(tmp_path, qtbot: QtBot) -> None:
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)
    loaded_data = LoadedSchedulerInput(
        courses=(),
        exam_periods=(
            ExamPeriod(
                semester=Semester.FALL,
                term=Term.ALEPH,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 5),
            ),
        ),
        programs=(),
    )

    window.input_panel.notify_data_loaded(loaded_data)
    window.input_panel.set_data_load_success(0, 1, 0)
    window._set_selected_schedule(
        _schedule_with_exam("Algorithms", 10001, date(2026, 1, 2))
    )
    window._show_calendar_screen()

    first_cells = _calendar_cells_by_day(window.calendar_view)
    assert len(window.calendar_view.findChildren(_DayCell)) == 31
    assert "Algorithms (10001)" in first_cells[2].exam_text()

    window._set_selected_schedule(
        _schedule_with_exam("Databases", 10002, date(2026, 1, 3))
    )

    refreshed_cells = _calendar_cells_by_day(window.calendar_view)
    assert len(window.calendar_view.findChildren(_DayCell)) == 31
    assert refreshed_cells[2].exam_text() == ""
    assert "Databases (10002)" in refreshed_cells[3].exam_text()

def test_calendar_label_without_course_id() -> None:
    exam = ScheduledExamViewModel(
        course_name="Philosophy",
        exam_date=date(2026, 1, 10),
        instructor="Dr. B",
        course_id=None,
    )
    assert exam.calendar_label == "Philosophy"

def test_exam_cell_text_clips_long_course_name(qtbot: QtBot) -> None:
    period = ExamPeriodViewModel(
        semester_label="FALL",
        term_label="Aleph",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        scheduled_exams=(
            ScheduledExamViewModel(
                course_name="Introduction to Advanced Algorithms",
                course_id=99999,
                exam_date=date(2026, 1, 5),
                instructor="Dr. C",
            ),
        ),
    )
    grid = _MonthGrid(2026, 1, period)
    qtbot.addWidget(grid)

    cells = {int(c.text()): c for c in grid.findChildren(_DayCell) if c.text().isdigit()}
    text = cells[5].exam_text()

    assert len(text.splitlines()[0]) <= 24
    assert "..." in text

def test_exam_cell_text_compact_when_multiple_exams(qtbot: QtBot) -> None:
    period = ExamPeriodViewModel(
        semester_label="FALL",
        term_label="Aleph",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        scheduled_exams=(
            ScheduledExamViewModel(
                course_name="Algorithms",
                course_id=10001,
                exam_date=date(2026, 1, 5),
                instructor="Dr. A",
                program_ids=(83101,),
                requirement_types=("Obligatory",),
            ),
            ScheduledExamViewModel(
                course_name="Databases",
                course_id=10002,
                exam_date=date(2026, 1, 5),
                instructor="Dr. B",
            ),
        ),
    )
    grid = _MonthGrid(2026, 1, period)
    qtbot.addWidget(grid)

    cells = {int(c.text()): c for c in grid.findChildren(_DayCell) if c.text().isdigit()}
    text = cells[5].exam_text()
    lines = text.splitlines()

    assert len(lines) == 2
    assert all(len(line) <= 20 for line in lines)
    assert "83101" not in text

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
        "=== SEMESTER: FALL ===\n"
        "  [TERM: Aleph]\n"
        "Course A | 2026-01-01 | Dr. A\n"
        "Schedule #2\n"
        "=== SEMESTER: FALL ===\n"
        "  [TERM: Aleph]\n"
        "Course B | 2026-01-02 | Dr. B\n",
        encoding="utf-8",
    )
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)
    window.input_panel.notify_data_loaded(
        LoadedSchedulerInput(
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
    )
    window._active_run_config = CliRunConfig(
        project_root=tmp_path,
        mode="period",
        output_config=config_path,
    )

    window._handle_finished(0, "NormalExit")

    assert window.output_view.cache.system_count == 2
    assert window.output_view.schedule_label.text() == "Schedule 1 of 2"

    first_schedule_cells = _calendar_cells_by_day(window.output_view)
    assert len(window.output_view.findChildren(_DayCell)) == 31
    assert "Course A" in first_schedule_cells[1].exam_text()
    assert first_schedule_cells[2].exam_text() == ""

    qtbot.mouseClick(window.output_view.pagination_bar.next_button, Qt.MouseButton.LeftButton)

    second_schedule_cells = _calendar_cells_by_day(window.output_view)
    assert len(window.output_view.findChildren(_DayCell)) == 31
    assert second_schedule_cells[1].exam_text() == ""
    assert "Course B" in second_schedule_cells[2].exam_text()


def _calendar_cells_by_day(view) -> dict[int, _DayCell]:
    return {
        int(cell.text()): cell
        for cell in view.findChildren(_DayCell)
        if cell.text().isdigit()
    }


def _schedule_with_exam(course_name: str, course_id: int, exam_date: date) -> ScheduleSystem:
    exam = ScheduleExamDisplay(
        course_name=course_name,
        course_id=course_id,
        exam_date=exam_date,
        instructor="Dr. Ada",
        program_ids=(83101,),
        requirement_types=("Obligatory",),
    )
    return ScheduleSystem(
        number=1,
        text=f"Schedule #1\n{course_name} | {exam_date.isoformat()} | Dr. Ada",
        periods=(
            SchedulePeriodDisplay(
                semester_label="FALL",
                term_label="Aleph",
                exams=(exam,),
            ),
        ),
    )

