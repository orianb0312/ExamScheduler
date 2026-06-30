from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QPoint, Qt
from pytestqt.qtbot import QtBot

from src.services.schedule_output_service import (
    ScheduleExamCohort,
    ScheduleExamDisplay,
    SchedulePeriodDisplay,
    ScheduleSystem,
)
from src.services.scheduler_input_state import SchedulerInputState
from src.sorting.schedule_priority import (
    AVERAGE_COHORT_GAP,
    MANDATORY_MIN_GAP,
    MAX_DAILY_EXAMS,
)
from src.ui.calendar_view import OutputView
from src.ui.sorting_priority_widget import SortingPriorityWidget


def _system(
    number: int,
    exams: tuple[ScheduleExamDisplay, ...],
) -> ScheduleSystem:
    return ScheduleSystem(
        number=number,
        text=f"Complete System #{number}",
        periods=(
            SchedulePeriodDisplay(
                semester_label="FALL",
                term_label="Aleph",
                exams=exams,
            ),
        ),
    )


def _exam(
    name: str,
    exam_date: date,
    cohort: ScheduleExamCohort,
) -> ScheduleExamDisplay:
    return ScheduleExamDisplay(
        course_name=name,
        exam_date=exam_date,
        instructor="Dr. Sort",
        cohorts=(cohort,),
    )


def test_output_view_reorders_cached_schedules_when_priority_changes(
    tmp_path,
    qtbot: QtBot,
) -> None:
    threshold_state = SchedulerInputState(tmp_path)
    threshold_state.set_constraints({"max_exams_per_day": 2})

    first_cohort = ScheduleExamCohort(
        program_id=83101,
        year=1,
        requirement_type="Obligatory",
    )
    second_cohort = ScheduleExamCohort(
        program_id=83102,
        year=1,
        requirement_type="Obligatory",
    )

    crowded_same_day = _system(
        1,
        (
            _exam("One", date(2026, 1, 1), first_cohort),
            _exam("Two", date(2026, 1, 1), second_cohort),
        ),
    )
    wide_mandatory_gap = _system(
        2,
        (
            _exam("Three", date(2026, 1, 1), first_cohort),
            _exam("Four", date(2026, 1, 4), first_cohort),
        ),
    )

    view = OutputView()
    qtbot.addWidget(view)
    view.add_systems([crowded_same_day, wide_mandatory_gap])

    assert view.sorting_priority_widget.priority == ()
    assert view.cache.get_page(1)[0].number == 1

    view.sorting_priority_widget.set_priority([MANDATORY_MIN_GAP])

    assert view.cache.get_page(1)[0].number == 2

    view.sorting_priority_widget.set_priority([])

    assert view.cache.get_page(1)[0].number == 1

    view.sorting_priority_widget.set_priority([MAX_DAILY_EXAMS])

    assert view.cache.get_page(1)[0].number == 1
    assert threshold_state.constraints == {"max_exams_per_day": 2}


def test_output_view_applies_high_page_sort_from_cached_scores(qtbot: QtBot) -> None:
    cohort = ScheduleExamCohort(
        program_id=83101,
        year=1,
        requirement_type="Obligatory",
    )
    narrow_gap = _system(
        1,
        (
            _exam("One", date(2026, 1, 1), cohort),
            _exam("Two", date(2026, 1, 2), cohort),
        ),
    )
    medium_gap = _system(
        2,
        (
            _exam("Three", date(2026, 1, 1), cohort),
            _exam("Four", date(2026, 1, 4), cohort),
        ),
    )
    wide_gap = _system(
        3,
        (
            _exam("Five", date(2026, 1, 1), cohort),
            _exam("Six", date(2026, 1, 10), cohort),
        ),
    )

    view = OutputView()
    qtbot.addWidget(view)
    view.add_systems([narrow_gap, medium_gap, wide_gap])
    view.pagination_bar.set_current_page(3)

    def fail_score_recalculation(*_args, **_kwargs):
        raise AssertionError("runtime sorting should reuse cached schedule scores")

    view._schedule_sorter.score_tuple = fail_score_recalculation

    view.sorting_priority_widget.set_priority([MANDATORY_MIN_GAP])

    assert view.pagination_bar.current_page == 1
    assert view.cache.get_page(1)[0] is wide_gap


def test_sorting_priority_widget_can_disable_and_enable_criteria(qtbot: QtBot) -> None:
    widget = SortingPriorityWidget()
    qtbot.addWidget(widget)

    assert widget.priority == ()
    assert widget.enabled_count_label.text() == "0 active"

    widget.set_priority([MAX_DAILY_EXAMS])

    assert widget.priority == (MAX_DAILY_EXAMS,)
    assert widget.enabled_count_label.text() == "1 active"

    first_card = widget.cards[0]
    first_card.set_active(False)

    assert widget.priority == ()
    assert widget.enabled_count_label.text() == "0 active"

    second_card = widget.cards[1]
    second_card.set_active(True)

    assert widget.priority == (MANDATORY_MIN_GAP,)
    assert widget.enabled_count_label.text() == "1 active"


def test_sorting_priority_widget_keeps_inactive_cards_below_active_cards(
    qtbot: QtBot,
) -> None:
    widget = SortingPriorityWidget()
    qtbot.addWidget(widget)
    widget.set_priority([MANDATORY_MIN_GAP, AVERAGE_COHORT_GAP])

    disabled_card = widget.cards[2]
    widget._move_card_up(disabled_card)

    assert widget.cards[0].key == MANDATORY_MIN_GAP
    assert widget.cards[1].key == AVERAGE_COHORT_GAP
    assert disabled_card in widget.cards[2:]

    widget.cards[0].set_active(False)

    assert widget.cards[0].key == AVERAGE_COHORT_GAP
    assert MANDATORY_MIN_GAP in [card.key for card in widget.cards[1:]]
    assert widget.priority == (AVERAGE_COHORT_GAP,)


def test_sort_toggle_is_clickable_across_full_width(qtbot: QtBot) -> None:
    widget = SortingPriorityWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.wait(20)

    toggle = widget.cards[0].toggle
    toggle.setChecked(False)

    qtbot.mouseClick(
        toggle,
        Qt.MouseButton.LeftButton,
        pos=QPoint(toggle.width() - 4, toggle.height() // 2),
    )

    assert toggle.isChecked()


def test_sorting_priority_widget_drag_reorders_without_losing_cards(
    qtbot: QtBot,
) -> None:
    widget = SortingPriorityWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.wait(20)

    dragged_card = widget.cards[0]
    last_card = widget.cards[-1]
    widget._start_drag(dragged_card)
    widget._drag_card(
        dragged_card,
        last_card.mapToGlobal(last_card.rect().center()),
    )
    widget._finish_drag(dragged_card)

    assert len(widget.cards) == 5
    assert widget.cards[-1].key == MANDATORY_MIN_GAP
    assert dragged_card.isVisible()
    assert all(card.isVisible() for card in widget.cards)


def test_sort_options_panel_slides_over_dashboard_without_relayout(qtbot: QtBot) -> None:
    view = OutputView()
    qtbot.addWidget(view)
    view.resize(900, 620)
    view.show()
    qtbot.wait(20)

    before_geometry = view.pagination_bar.geometry()

    assert not view.sorting_priority_widget.isVisible()

    qtbot.mouseClick(view.sort_options_button, Qt.MouseButton.LeftButton)
    qtbot.wait(320)

    assert view.sorting_priority_widget.isVisible()
    assert view.sorting_priority_widget.height() == view.height()
    assert (
        view.sorting_priority_widget.x()
        == view.width() - view._current_sort_panel_width()
    )
    assert view.pagination_bar.geometry() == before_geometry


def test_sort_options_panel_can_be_closed_from_sidebar(qtbot: QtBot) -> None:
    view = OutputView()
    qtbot.addWidget(view)
    view.resize(900, 620)
    view.show()
    qtbot.wait(20)

    qtbot.mouseClick(view.sort_options_button, Qt.MouseButton.LeftButton)
    qtbot.wait(320)

    assert view.sorting_priority_widget.isVisible()

    qtbot.mouseClick(
        view.sorting_priority_widget.close_button,
        Qt.MouseButton.LeftButton,
    )
    qtbot.wait(320)

    assert not view.sorting_priority_widget.isVisible()
