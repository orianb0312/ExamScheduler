from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from pytestqt.qtbot import QtBot

from src.process_protocol import LAZY_NEXT_COMMAND
from src.services.cli_run_service import CliRunConfig
from src.services.schedule_output_service import (
    ScheduleExamCohort,
    ScheduleExamDisplay,
    SchedulePeriodDisplay,
    ScheduleSystem,
)
from src.sorting.schedule_priority import MANDATORY_MIN_GAP
from src.ui.dashboard_view import ExamSchedulerDashboard
from src.ui.main_window import MainWindow, NO_DASHBOARD_SCHEDULE_MESSAGE


class _FakeProcessRunner(QObject):
    stdout_received = pyqtSignal(str)
    stderr_received = pyqtSignal(str)
    process_started = pyqtSignal()
    process_finished = pyqtSignal(int, str)
    process_error = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.started_config: CliRunConfig | None = None
        self.sent_lines: list[str] = []

    def start(self, config: CliRunConfig) -> None:
        self.started_config = config
        self.process_started.emit()

    def is_running(self) -> bool:
        return self.started_config is not None

    def cancel(self) -> None:
        self.started_config = None

    def send_input_line(self, line: str) -> None:
        self.sent_lines.append(line)


def _system() -> ScheduleSystem:
    cohort = ScheduleExamCohort(
        program_id=83101,
        year=1,
        requirement_type="Obligatory",
    )
    return ScheduleSystem(
        number=9,
        text="Complete System #9",
        periods=(
            SchedulePeriodDisplay(
                semester_label="FALL",
                term_label="Aleph",
                exams=(
                    ScheduleExamDisplay(
                        course_name="Algorithms",
                        exam_date=date(2026, 1, 5),
                        instructor="Dr. Ada",
                        cohorts=(cohort,),
                    ),
                    ScheduleExamDisplay(
                        course_name="Databases",
                        exam_date=date(2026, 1, 5),
                        instructor="Dr. Turing",
                        cohorts=(cohort,),
                    ),
                ),
            ),
        ),
    )


def _system_with_dates(number: int, dates: tuple[date, date]) -> ScheduleSystem:
    cohort = ScheduleExamCohort(
        program_id=83101,
        year=1,
        requirement_type="Obligatory",
    )
    return ScheduleSystem(
        number=number,
        text=f"Complete System #{number}",
        periods=(
            SchedulePeriodDisplay(
                semester_label="FALL",
                term_label="Aleph",
                exams=(
                    ScheduleExamDisplay(
                        course_name=f"Course {number}A",
                        exam_date=dates[0],
                        instructor="Dr. Ada",
                        cohorts=(cohort,),
                    ),
                    ScheduleExamDisplay(
                        course_name=f"Course {number}B",
                        exam_date=dates[1],
                        instructor="Dr. Ada",
                        cohorts=(cohort,),
                    ),
                ),
            ),
        ),
    )


def test_dashboard_tab_refreshes_for_best_schedule_so_far(
    tmp_path,
    qtbot: QtBot,
) -> None:
    runners: list[_FakeProcessRunner] = []

    def create_runner(parent) -> _FakeProcessRunner:
        runner = _FakeProcessRunner(parent)
        runners.append(runner)
        return runner

    window = MainWindow(
        project_root=tmp_path,
        process_runner_factory=create_runner,
    )
    qtbot.addWidget(window)
    window.input_panel.replace_program_list(["83101"])
    window.input_panel.program_selector.item(0).setCheckState(Qt.CheckState.Checked)

    assert not hasattr(window.output_view, "analytics_dashboard")
    assert window.input_panel.analytics_dashboard.total_card.value_label.text() == "No schedules"
    assert window.input_panel.analytics_dashboard.pagination_label.text() == "No schedules to display"
    assert window.input_panel.analytics_dashboard.previous_button.isEnabled()
    assert window.input_panel.analytics_dashboard.next_button.isEnabled()

    window.output_view.add_systems([_system()])
    window.input_panel.show_dashboard_page()

    dashboard = window.input_panel.analytics_dashboard
    assert isinstance(dashboard, ExamSchedulerDashboard)
    assert window.input_panel.is_dashboard_page_visible()
    assert dashboard.total_card.value_label.text() == "1"
    assert dashboard.fitness_card.value_label.text() == "Schedule #9"
    assert dashboard.gap_card.value_label.text() == "0 Days"
    assert dashboard.health_card.value_label.text() == "Schedule #9"
    assert dashboard.chart._dates == ["Jan 05"]
    assert dashboard.chart._values == [2]
    assert "Best schedule so far #9 contains 2 exams" in (
        dashboard.insights.winning_card.body_label.text()
    )
    assert "Most loaded cohort is program 83101" in (
        dashboard.insights.bottleneck_card.body_label.text()
    )
    assert dashboard.pagination_label.text() == "Displaying Chunk 1 | Schedules 1 - 1"
    assert dashboard.previous_button.isEnabled()
    assert "Generate Next 1,000" in dashboard.next_button.text()
    assert not dashboard.next_button.isEnabled()

    qtbot.mouseClick(dashboard.previous_button, Qt.MouseButton.LeftButton)
    assert window._stack.currentWidget() is window.input_panel
    assert window.input_panel.is_schedules_page_visible()

    window._stack.setCurrentWidget(window.input_panel)
    window.input_panel.show_dashboard_page()
    window._active_run_config = CliRunConfig(
        project_root=tmp_path,
        lazy_schedules=True,
    )
    window.output_view.set_more_available(True)
    window._refresh_analytics_dashboard()

    assert dashboard.next_button.isEnabled()

    qtbot.mouseClick(dashboard.next_button, Qt.MouseButton.LeftButton)

    assert runners[0].sent_lines == [LAZY_NEXT_COMMAND]
    assert window._stack.currentWidget() is window.input_panel
    assert window.input_panel.is_schedules_page_visible()
    assert window.output_view.status_label.text() == "Generating next 1,000 schedule systems..."

    dashboard.update_metrics("10", "91%", "4 Days", "RAM: 70MB | Safe")
    dashboard.update_insights("Winning", "Bottleneck")
    dashboard.set_pagination(2, 1001, 2000)

    assert dashboard.total_card.value_label.text() == "10"
    assert dashboard.insights.winning_card.body_label.text() == "Winning"
    assert dashboard.insights.bottleneck_card.body_label.text() == "Bottleneck"
    assert dashboard.pagination_label.text() == "Displaying Chunk 2 | Schedules 1,001 - 2,000"


def test_dashboard_actions_without_schedules_show_message(
    tmp_path,
    qtbot: QtBot,
) -> None:
    runners: list[_FakeProcessRunner] = []

    def create_runner(parent) -> _FakeProcessRunner:
        runner = _FakeProcessRunner(parent)
        runners.append(runner)
        return runner

    window = MainWindow(
        project_root=tmp_path,
        process_runner_factory=create_runner,
    )
    qtbot.addWidget(window)
    window.input_panel.show_dashboard_page()

    dashboard = window.input_panel.analytics_dashboard
    assert dashboard.previous_button.isEnabled()
    assert dashboard.next_button.isEnabled()

    qtbot.mouseClick(dashboard.previous_button, Qt.MouseButton.LeftButton)

    assert window.input_panel.is_dashboard_page_visible()
    assert not window.input_panel.is_schedules_page_visible()
    assert window._toast.message_label.text() == NO_DASHBOARD_SCHEDULE_MESSAGE

    window._toast.hide()
    qtbot.mouseClick(dashboard.next_button, Qt.MouseButton.LeftButton)

    assert runners[0].sent_lines == []
    assert window.input_panel.is_dashboard_page_visible()
    assert not window.input_panel.is_schedules_page_visible()
    assert window._toast.message_label.text() == NO_DASHBOARD_SCHEDULE_MESSAGE


def test_dashboard_uses_best_schedule_so_far_without_extra_sort_or_full_copy(
    tmp_path,
    qtbot: QtBot,
) -> None:
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    worse_schedule = _system_with_dates(
        1,
        (date(2026, 1, 1), date(2026, 1, 2)),
    )
    better_schedule = _system_with_dates(
        2,
        (date(2026, 1, 1), date(2026, 1, 10)),
    )
    window.output_view.add_systems([worse_schedule, better_schedule])
    window.output_view.sorting_priority_widget.set_priority([MANDATORY_MIN_GAP])
    window.output_view.pagination_bar.set_current_page(2)

    def fail_sort(*_args, **_kwargs):
        raise AssertionError("Dashboard refresh must not re-sort schedules.")

    def fail_full_copy():
        raise AssertionError("Dashboard refresh must not copy all schedules.")

    window.output_view._schedule_sorter.sort = fail_sort
    window.output_view.cache.all_systems = fail_full_copy

    window._refresh_analytics_dashboard()

    dashboard = window.input_panel.analytics_dashboard
    assert dashboard.fitness_card.value_label.text() == "Schedule #2"
    assert dashboard.health_card.value_label.text() == "Schedule #2"
    assert "Best schedule so far #2 contains 2 exams" in (
        dashboard.insights.winning_card.body_label.text()
    )
    assert "Mandatory min gap: 9" in dashboard.insights.winning_card.body_label.text()

    with qtbot.waitSignal(window.output_view.selected_schedule_changed):
        qtbot.mouseClick(dashboard.previous_button, Qt.MouseButton.LeftButton)

    assert window.output_view.selected_schedule is better_schedule


def test_dashboard_best_schedule_uses_default_priority_when_sort_panel_is_empty(
    tmp_path,
    qtbot: QtBot,
) -> None:
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    first_schedule = _system_with_dates(
        1,
        (date(2026, 1, 1), date(2026, 1, 2)),
    )
    better_schedule = _system_with_dates(
        2,
        (date(2026, 1, 1), date(2026, 1, 10)),
    )

    assert window.output_view.sorting_priority_widget.priority == ()

    window.output_view.add_systems([first_schedule])
    window.output_view.add_systems([better_schedule])
    window._refresh_analytics_dashboard()

    dashboard = window.input_panel.analytics_dashboard
    assert window.output_view.best_schedule_so_far is better_schedule
    assert dashboard.fitness_card.value_label.text() == "Schedule #2"
    assert dashboard.health_card.value_label.text() == "Schedule #2"
    assert "Best schedule so far #2 contains 2 exams" in (
        dashboard.insights.winning_card.body_label.text()
    )
    assert "Mandatory min gap: 9" in dashboard.insights.winning_card.body_label.text()


def test_dashboard_keeps_best_schedule_so_far_across_generated_iterations(
    tmp_path,
    qtbot: QtBot,
) -> None:
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)
    window.output_view.sorting_priority_widget.set_priority([MANDATORY_MIN_GAP])

    first_iteration_best = _system_with_dates(
        1,
        (date(2026, 1, 1), date(2026, 1, 10)),
    )
    second_iteration_worse = _system_with_dates(
        2,
        (date(2026, 1, 1), date(2026, 1, 5)),
    )
    third_iteration_better = _system_with_dates(
        3,
        (date(2026, 1, 1), date(2026, 1, 12)),
    )

    window.output_view.add_systems([first_iteration_best])
    assert window.output_view.best_schedule_so_far is first_iteration_best

    def fail_rebuild(*_args, **_kwargs):
        raise AssertionError("New batches must update the rolling best incrementally.")

    window.output_view._best_schedule_tracker.rebuild = fail_rebuild
    window.output_view.start_new_generated_batch()
    window.output_view.add_systems([second_iteration_worse])
    assert window.output_view.best_schedule_so_far is first_iteration_best
    assert window.output_view.current_batch_best_schedule is second_iteration_worse

    window._refresh_analytics_dashboard()
    dashboard = window.input_panel.analytics_dashboard
    assert dashboard.fitness_card.value_label.text() == "Schedule #1"
    assert dashboard.health_card.value_label.text() == "Schedule #2"
    assert "Current batch best is schedule #2" in (
        dashboard.insights.winning_card.body_label.text()
    )

    window.output_view.start_new_generated_batch()
    window.output_view.add_systems([third_iteration_better])
    assert window.output_view.best_schedule_so_far is third_iteration_better
    assert window.output_view.current_batch_best_schedule is third_iteration_better

    window._refresh_analytics_dashboard()

    dashboard = window.input_panel.analytics_dashboard
    assert dashboard.fitness_card.value_label.text() == "Schedule #3"
    assert dashboard.health_card.value_label.text() == "Schedule #3"
    winning_text = dashboard.insights.winning_card.body_label.text()
    assert "Best schedule so far #3 contains 2 exams" in winning_text
    assert "Mandatory min gap: 11" in winning_text
    assert "- Previous overall best was schedule #1." in winning_text
    assert "- New overall best is schedule #3." in winning_text
    assert "- Mandatory min gap improved from 9 to 11." in winning_text
