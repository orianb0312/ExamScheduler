from __future__ import annotations

from datetime import date

import pytest
from PyQt6.QtCore import QObject, QDate, Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton
from pytestqt.qtbot import QtBot

from src.models.enums import Semester, Term
from src.models.scheduling import ExamPeriod
from src.process_protocol import LAZY_STOP_COMMAND
from src.services.cli_run_service import CliRunConfig
from src.services.file_loading_service import LoadedSchedulerInput
from src.services.schedule_output_service import (
    ScheduleExamDisplay,
    SchedulePeriodDisplay,
    ScheduleSystem,
)
from src.ui.calendar_view import OutputView
from src.ui.calendar_view_panel import CalendarView, _DayCell, _MonthGrid, _PeriodSection
from src.ui.main_window import MainWindow, NO_EXAM_SCHEDULES_MESSAGE
from src.ui.view_models import (
    ExamPeriodViewModel,
    ExclusionViewModel,
    ScheduledExamViewModel,
)


@pytest.fixture()
def simple_period() -> ExamPeriodViewModel:
    """Fixture that provides a basic ExamPeriodViewModel with a single exclusion day."""
    return ExamPeriodViewModel(
        semester_label="Semester A",
        term_label="Moed A",
        start_date=date(2025, 1, 5),
        end_date=date(2025, 2, 20),
        exclusions=(ExclusionViewModel(start_date=date(2025, 1, 15), end_date=None),),
    )


class _FakeProcessRunner(QObject):
    stdout_received = pyqtSignal(str)
    stderr_received = pyqtSignal(str)
    process_started = pyqtSignal()
    process_finished = pyqtSignal(int, str)
    process_error = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.started_config: CliRunConfig | None = None
        self.running = False
        self.sent_lines: list[str] = []

    def start(self, config: CliRunConfig) -> None:
        # The fake proves the UI uses the runner boundary without starting main.py.
        self.started_config = config
        self.running = True
        self.process_started.emit()

    def is_running(self) -> bool:
        return self.running

    def cancel(self) -> None:
        self.running = False

    def send_input_line(self, line: str) -> None:
        self.sent_lines.append(line)


def test_exam_period_view_model_logic(simple_period: ExamPeriodViewModel) -> None:
    """Verify core date logic within ExamPeriodViewModel, including boundaries and exclusions."""
    # Date within the valid period range
    assert simple_period.is_date_in_period(date(2025, 1, 5))
    # Date outside the valid period range
    assert not simple_period.is_date_in_period(date(2025, 2, 21))
    # Date specifically marked as excluded
    assert simple_period.is_date_excluded(date(2025, 1, 15))
    # Regular active date (not excluded)
    assert not simple_period.is_date_excluded(date(2025, 1, 10))
    # Ensure no exams are scheduled on this date by default
    assert simple_period.exams_on(date(2025, 1, 10)) == ()


def test_month_grid_cell_background_colors(qtbot: QtBot, simple_period: ExamPeriodViewModel) -> None:
    """Verify that different day cell states (Available, Excluded, Outside) get correct stylesheets."""
    grid = _MonthGrid(2025, 1, simple_period)
    qtbot.addWidget(grid)

    # Map day numbers to their respective cell widgets
    cells = {int(c.text()): c for c in grid.findChildren(_DayCell) if c.text().isdigit()}

    assert "#244d3a" in cells[10].styleSheet()  # Available day style
    assert "#5a2f3c" in cells[15].styleSheet()  # Excluded day style
    assert "#2b303a" in cells[1].styleSheet()  # Day outside the exam period


def test_month_grid_displays_exam_inside_matching_day_cell(qtbot: QtBot) -> None:
    """Ensure that scheduled exams are properly drawn and displayed within the matching day cell widget."""
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

    # Check cell text content for the scheduled exam details
    assert "Algorithms (10001)" in cells[10].exam_text()
    assert "83101 | Obligatory" in cells[10].exam_text()
    assert any("Algorithms" in text for text in day_ten_labels)
    # Check that a day with no exams remains empty
    assert cells[11].exam_text() == ""


def test_period_section_header_and_legend(qtbot: QtBot, simple_period: ExamPeriodViewModel) -> None:
    """Check that the period view component properly displays header information and calendar legends."""
    section = _PeriodSection(simple_period)
    qtbot.addWidget(section)

    texts = [lbl.text() for lbl in section.findChildren(QLabel)]

    # Verify header descriptors
    assert any("Semester A" in t and "Moed A" in t for t in texts)
    assert any("2025-01-05" in t and "2025-02-20" in t for t in texts)

    # Verify color legend labels are present
    for expected_label in ("Available", "Excluded", "Outside period", "Today"):
        assert any(expected_label in t for t in texts)


def test_calendar_view_loading_and_layout(qtbot: QtBot, simple_period: ExamPeriodViewModel) -> None:
    """Verify that CalendarView correctly initialises and handles layout rendering for loaded periods."""
    view = CalendarView()
    qtbot.addWidget(view)

    view.load_exam_periods([simple_period])

    # Check status bar text updates and grids are generated (Jan + Feb 2025 = 2 month grids)
    assert "1 exam period" in view._status_label.text()
    assert len(view.findChildren(_MonthGrid)) == 2


def test_main_window_keeps_calendar_and_output_screens_separate(tmp_path, qtbot: QtBot) -> None:
    """Ensure MainWindow manages separate instances for editing (CalendarView) and viewing (OutputView)."""
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    assert isinstance(window.calendar_view, CalendarView)
    assert isinstance(window.output_view, OutputView)
    assert window.calendar_view is not window.output_view


def test_generate_schedules_starts_process_runner_boundary(tmp_path, qtbot: QtBot) -> None:
    created_runners: list[_FakeProcessRunner] = []

    def create_runner(parent) -> _FakeProcessRunner:
        runner = _FakeProcessRunner(parent)
        created_runners.append(runner)
        return runner

    window = MainWindow(
        project_root=tmp_path,
        process_runner_factory=create_runner,
    )
    qtbot.addWidget(window)
    window.input_panel.replace_program_list(["83101"])
    window.input_panel.program_selector.item(0).setCheckState(Qt.CheckState.Checked)

    qtbot.mouseClick(window.input_panel.run_button, Qt.MouseButton.LeftButton)

    runner = created_runners[0]
    assert runner.started_config is not None
    assert runner.started_config.lazy_schedules is True
    assert window._stack.currentWidget() is window.input_panel
    assert not window.input_panel.run_button.isEnabled()
    assert window.input_panel.program_selector.isEnabled()


def test_back_from_output_stays_on_input_after_lazy_process_finishes(
    tmp_path,
    qtbot: QtBot,
) -> None:
    created_runners: list[_FakeProcessRunner] = []

    def create_runner(parent) -> _FakeProcessRunner:
        runner = _FakeProcessRunner(parent)
        created_runners.append(runner)
        return runner

    window = MainWindow(
        project_root=tmp_path,
        process_runner_factory=create_runner,
    )
    qtbot.addWidget(window)
    window.input_panel.replace_program_list(["83101"])
    window.input_panel.program_selector.item(0).setCheckState(Qt.CheckState.Checked)

    qtbot.mouseClick(window.input_panel.run_button, Qt.MouseButton.LeftButton)
    runner = created_runners[0]
    window.output_view.add_systems([
        _schedule_with_exam("Algorithms", 10001, date(2026, 1, 2))
    ])
    window._show_output_screen()

    qtbot.mouseClick(window.output_view.back_button, Qt.MouseButton.LeftButton)
    runner.running = False
    window._handle_finished(0, "NormalExit")

    assert runner.sent_lines == [LAZY_STOP_COMMAND]
    assert window._stack.currentWidget() is window.input_panel


def test_output_view_selected_schedule_follows_visible_page(qtbot: QtBot) -> None:
    """Test pagination within OutputView to ensure switching pages changes the selected schedule object."""
    view = OutputView()
    qtbot.addWidget(view)

    view.add_systems([
        ScheduleSystem(number=1, text="Schedule #1"),
        ScheduleSystem(number=2, text="Schedule #2"),
    ])

    # Initial state should point to the first schedule
    assert view.selected_schedule is not None
    assert view.selected_schedule.number == 1

    # Simulate UI click on the 'Next' page button
    qtbot.mouseClick(view.pagination_bar.next_button, Qt.MouseButton.LeftButton)

    # Selected schedule should update to the next system
    assert view.selected_schedule is not None
    assert view.selected_schedule.number == 2


def test_output_view_label_uses_known_total_count(qtbot: QtBot) -> None:
    """Verify that the summary tracker label tracks pagination indices relative to a hard total count."""
    view = OutputView()
    qtbot.addWidget(view)
    view.set_schedule_total(12)

    view.add_systems([
        ScheduleSystem(number=1, text="Schedule #1"),
        ScheduleSystem(number=2, text="Schedule #2"),
    ])

    assert view.schedule_label.text() == "1 of 12 schedules"

    # Click next page and verify counter changes
    qtbot.mouseClick(view.pagination_bar.next_button, Qt.MouseButton.LeftButton)
    assert view.schedule_label.text() == "2 of 12 schedules"


def test_output_view_label_compacts_large_total_count(qtbot: QtBot) -> None:
    view = OutputView()
    qtbot.addWidget(view)
    view.set_schedule_total(4_900_450)

    view.add_systems([
        ScheduleSystem(number=1, text="Schedule #1"),
        ScheduleSystem(number=2, text="Schedule #2"),
        ScheduleSystem(number=3, text="Schedule #3"),
        ScheduleSystem(number=4, text="Schedule #4"),
    ])

    for _ in range(3):
        qtbot.mouseClick(view.pagination_bar.next_button, Qt.MouseButton.LeftButton)

    assert view.schedule_label.text() == "4 of 4.9M schedules"


def test_output_view_page_ruler_click_selects_schedule(qtbot: QtBot) -> None:
    view = OutputView()
    qtbot.addWidget(view)

    view.add_systems([
        ScheduleSystem(number=number, text=f"Schedule #{number}")
        for number in range(1, 13)
    ])

    assert _page_ruler_texts(view) == ["1", "2", "3", "12"]
    assert view.pagination_bar.leading_ellipsis_label.isHidden()
    assert not view.pagination_bar.ellipsis_label.isHidden()

    qtbot.mouseClick(_page_ruler_buttons(view)[2], Qt.MouseButton.LeftButton)

    assert view.pagination_bar.current_page == 3
    assert view.selected_schedule is not None
    assert view.selected_schedule.number == 3
    assert view.schedule_label.text() == "3 of 12 schedules"
    assert _page_ruler_texts(view) == ["1", "3", "4", "5", "12"]
    assert not view.pagination_bar.leading_ellipsis_label.isHidden()


def test_output_view_page_ruler_slides_on_next_clicks(qtbot: QtBot) -> None:
    view = OutputView()
    qtbot.addWidget(view)

    view.add_systems([
        ScheduleSystem(number=number, text=f"Schedule #{number}")
        for number in range(1, 13)
    ])

    for _ in range(3):
        qtbot.mouseClick(view.pagination_bar.next_button, Qt.MouseButton.LeftButton)

    assert view.pagination_bar.current_page == 4
    assert _page_ruler_texts(view) == ["1", "4", "5", "6", "12"]
    assert not view.pagination_bar.leading_ellipsis_label.isHidden()
    assert not view.pagination_bar.ellipsis_label.isHidden()
    assert view.schedule_label.text() == "4 of 12 schedules"

    for _ in range(7):
        qtbot.mouseClick(view.pagination_bar.next_button, Qt.MouseButton.LeftButton)

    assert view.pagination_bar.current_page == 11
    assert _page_ruler_texts(view) == ["1", "11", "12"]
    assert not view.pagination_bar.leading_ellipsis_label.isHidden()
    assert view.pagination_bar.ellipsis_label.isHidden()


def test_output_view_page_ruler_keeps_last_generated_page_visible(qtbot: QtBot) -> None:
    view = OutputView()
    qtbot.addWidget(view)

    view.add_systems([
        ScheduleSystem(number=number, text=f"Schedule #{number}")
        for number in range(1, 1001)
    ])
    view.set_more_available(True)

    qtbot.mouseClick(view.pagination_bar.last_page_button, Qt.MouseButton.LeftButton)

    assert view.pagination_bar.current_page == 1000
    assert _page_ruler_texts(view) == ["1", "1000", "1001", "1002", "1999"]
    assert not view.pagination_bar.leading_ellipsis_label.isHidden()
    assert not view.pagination_bar.ellipsis_label.isHidden()


def test_output_view_page_ruler_updates_lookahead_on_each_page_skip(qtbot: QtBot) -> None:
    view = OutputView()
    qtbot.addWidget(view)

    view.add_systems([
        ScheduleSystem(number=number, text=f"Schedule #{number}")
        for number in range(1, 1001)
    ])
    view.set_more_available(True)

    assert _page_ruler_texts(view) == ["1", "2", "3", "1000"]
    assert view.pagination_bar.leading_ellipsis_label.isHidden()

    qtbot.mouseClick(view.pagination_bar.next_button, Qt.MouseButton.LeftButton)

    assert view.pagination_bar.current_page == 2
    assert _page_ruler_texts(view) == ["1", "2", "3", "4", "1001"]
    assert view.pagination_bar.leading_ellipsis_label.isHidden()


def test_output_view_page_ruler_keeps_large_numbers_readable(qtbot: QtBot) -> None:
    view = OutputView()
    qtbot.addWidget(view)

    view.add_systems([
        ScheduleSystem(number=number, text=f"Schedule #{number}")
        for number in range(1, 2004)
    ])
    view.pagination_bar.set_current_page(1003)

    assert _page_ruler_texts(view) == ["1", "1003", "1004", "1005", "2003"]
    assert not view.pagination_bar.leading_ellipsis_label.isHidden()
    assert not view.pagination_bar.ellipsis_label.isHidden()
    for button in _page_ruler_buttons(view):
        assert button.minimumWidth() >= button.fontMetrics().horizontalAdvance(button.text())


def test_calendar_button_opens_day_editor_and_updates_status(tmp_path, qtbot: QtBot) -> None:
    """Test the complete UI workflow of loading data, launching day editor, and toggling exclusions."""
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

    # Click view calendar to switch view screens
    qtbot.mouseClick(window.input_panel.view_calendar_button, Qt.MouseButton.LeftButton)

    # Verify correct stack navigation and side editor activation
    assert window._stack.currentWidget() is window.calendar_view
    assert not window.calendar_view.day_editor.isHidden()
    assert window.calendar_view.day_editor.day_table.rowCount() == 3

    # Select a row and simulate hitting the 'Exclude' button
    window.calendar_view.day_editor.day_table.selectRow(1)
    qtbot.mouseClick(
        window.calendar_view.day_editor.exclude_button,
        Qt.MouseButton.LeftButton,
    )
    assert window.calendar_view.day_editor.day_table.item(1, 1).text() == "Excluded"

    # Simulate hitting the 'Restore' button to reverse the exclusion
    qtbot.mouseClick(
        window.calendar_view.day_editor.restore_button,
        Qt.MouseButton.LeftButton,
    )
    assert window.calendar_view.day_editor.day_table.item(1, 1).text() == "Available"


def test_calendar_date_fields_update_period_range(tmp_path, qtbot: QtBot) -> None:
    """Verify that shifting start or end date widgets reactively reshapes data structures and tables."""
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

    # Push forward the starting boundary date
    window.calendar_view.day_editor.start_date_edit.setDate(QDate(2026, 1, 2))

    assert window.input_panel.exam_periods[0].start_date == date(2026, 1, 2)
    assert window.calendar_view.day_editor.day_table.rowCount() == 3


def test_calendar_refreshes_when_selected_schedule_changes(tmp_path, qtbot: QtBot) -> None:
    """Ensure that switching current schedules forces a complete re-render of calendar cells."""
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

    # Load first mock schedule configuration
    window._set_selected_schedule(
        _schedule_with_exam("Algorithms", 10001, date(2026, 1, 2))
    )
    window._show_calendar_screen()

    first_cells = _calendar_cells_by_day(window.calendar_view)
    assert len(window.calendar_view.findChildren(_DayCell)) == 31
    assert "Algorithms (10001)" in first_cells[2].exam_text()

    # Swap to second schedule configuration containing different courses/dates
    window._set_selected_schedule(
        _schedule_with_exam("Databases", 10002, date(2026, 1, 3))
    )

    # UI must refresh and display the updated dataset accurately
    refreshed_cells = _calendar_cells_by_day(window.calendar_view)
    assert len(window.calendar_view.findChildren(_DayCell)) == 31
    assert refreshed_cells[2].exam_text() == ""
    assert "Databases (10002)" in refreshed_cells[3].exam_text()


def test_calendar_label_without_course_id() -> None:
    """Verify string formatting fallback for ScheduledExamViewModel when course_id missing."""
    exam = ScheduledExamViewModel(
        course_name="Philosophy",
        exam_date=date(2026, 1, 10),
        instructor="Dr. B",
        course_id=None,
    )
    assert exam.calendar_label == "Philosophy"


def test_exam_cell_text_clips_long_course_name(qtbot: QtBot) -> None:
    """Ensure text rendering wraps cleanly or truncates with ellipses if titles cross max length."""
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
    """Test that cell text automatically optimizes layout density when multi-exams land on same slot."""
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

    # Layout should drop secondary meta tags to maintain row sizing constraints
    assert len(lines) == 2
    assert all(len(line) <= 20 for line in lines)
    assert "83101" not in text


def test_finished_run_loads_generated_output_file_into_output_view(tmp_path, qtbot: QtBot) -> None:
    """Integration test validating that post-processing reads config and correctly builds outputs inside OutputView."""
    # Write mock configurations and results directly to temp path filesystem
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

    # Trigger process finalization callback
    window._handle_finished(0, "NormalExit")

    # Assert systems parsed successfully
    assert window.output_view.cache.system_count == 2
    assert window.output_view.schedule_label.text() == "1 of 2 schedules"

    first_schedule_cells = _calendar_cells_by_day(window.output_view)
    assert len(window.output_view.findChildren(_DayCell)) == 31
    assert "Course A" in first_schedule_cells[1].exam_text()
    assert first_schedule_cells[2].exam_text() == ""

    # Switch views and evaluate second generated calendar instance
    qtbot.mouseClick(window.output_view.pagination_bar.next_button, Qt.MouseButton.LeftButton)

    second_schedule_cells = _calendar_cells_by_day(window.output_view)
    assert len(window.output_view.findChildren(_DayCell)) == 31
    assert second_schedule_cells[1].exam_text() == ""
    assert "Course B" in second_schedule_cells[2].exam_text()


def test_finished_run_with_only_empty_systems_shows_no_schedule_message(
    tmp_path,
    qtbot: QtBot,
) -> None:
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
        mode="auto",
        stream_schedules=True,
        lazy_schedules=True,
    )

    window._handle_stdout(
        "Complete systems: 1\n"
        "Complete System #1\n"
        "=== SEMESTER: FALL ===\n"
        "  [TERM: Aleph]\n"
    )
    window._handle_finished(0, "NormalExit")

    assert window.output_view.cache.system_count == 0
    assert window.output_view.selected_schedule is None
    assert window._stack.currentWidget() is window.input_panel
    assert not window._toast.isHidden()
    assert window._toast.message_label.text() == NO_EXAM_SCHEDULES_MESSAGE
    assert not _calendar_cells_by_day(window.output_view)

    window._toast.close_button.click()
    qtbot.waitUntil(window._toast.isHidden, timeout=1000)


def _calendar_cells_by_day(view) -> dict[int, _DayCell]:
    """Helper method to filter day cells containing active text entries."""
    return {
        int(cell.text()): cell
        for cell in view.findChildren(_DayCell)
        if cell.text().isdigit()
    }


def _page_ruler_buttons(view: OutputView) -> list[QPushButton]:
    return [
        button
        for button in [
            *view.pagination_bar._page_buttons,
            view.pagination_bar.last_page_button,
        ]
        if not button.isHidden()
    ]


def _page_ruler_texts(view: OutputView) -> list[str]:
    return [button.text() for button in _page_ruler_buttons(view)]


def _schedule_with_exam(course_name: str, course_id: int, exam_date: date) -> ScheduleSystem:
    """Helper factory method to programmatically build mock ScheduleSystem configurations."""
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


def test_failed_run_sets_output_error_status(tmp_path, qtbot: QtBot) -> None:
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    window._handle_finished(2, "CrashExit")

    assert "Scheduler process exited with code 2" in window.output_view.status_label.text()

