from datetime import date

import pytest

from src.sorting.schedule_priority import (
    AVERAGE_COHORT_GAP,
    ELECTIVE_CONFLICTS,
    MANDATORY_MIN_GAP,
    MANDATORY_SPAN,
    MAX_DAILY_EXAMS,
    ScheduleQualityScorer,
    SchedulePrioritySorter,
    SortableCohort,
    SortableExam,
    parse_sort_priority_text,
)


def _exam(day: int, requirement: str = "Obligatory") -> SortableExam:
    return SortableExam(
        exam_date=date(2026, 1, day),
        cohorts=(
            SortableCohort(
                program_id=83101,
                year=1,
                requirement_type=requirement,
            ),
        ),
    )


def test_parse_sort_priority_text_accepts_aliases_and_headers() -> None:
    text = """
    $$$$
    sorting_priority
    3.5
    mandatory_gap
    """

    assert parse_sort_priority_text(text) == (
        MAX_DAILY_EXAMS,
        MANDATORY_MIN_GAP,
    )


def test_parse_sort_priority_text_rejects_duplicates_and_unknowns() -> None:
    with pytest.raises(ValueError, match="Duplicate sorting criterion"):
        parse_sort_priority_text("3.1\nmandatory_min_gap\n")

    with pytest.raises(ValueError, match="Unknown sorting criterion"):
        parse_sort_priority_text("made_up_sort\n")


def test_sorter_orders_by_mandatory_min_gap_descending() -> None:
    schedules = [
        (_exam(1), _exam(2)),
        (_exam(1), _exam(5)),
    ]

    ordered = SchedulePrioritySorter().sort(
        schedules,
        [MANDATORY_MIN_GAP],
        lambda schedule: schedule,
    )

    assert ordered == [schedules[1], schedules[0]]


def test_sorter_orders_by_elective_conflicts_descending() -> None:
    no_conflict = (_exam(1, "Elective"), _exam(2, "Elective"))
    one_conflict = (_exam(1, "Elective"), _exam(1, "Elective"))

    ordered = SchedulePrioritySorter().sort(
        [no_conflict, one_conflict],
        [ELECTIVE_CONFLICTS],
        lambda schedule: schedule,
    )

    assert ordered == [one_conflict, no_conflict]


def test_sorter_orders_by_average_cohort_gap_descending() -> None:
    smaller_average_gap = (_exam(1), _exam(3), _exam(5))
    larger_average_gap = (_exam(1), _exam(5), _exam(9))

    ordered = SchedulePrioritySorter().sort(
        [smaller_average_gap, larger_average_gap],
        [AVERAGE_COHORT_GAP],
        lambda schedule: schedule,
    )

    assert ordered == [larger_average_gap, smaller_average_gap]


def test_sorter_orders_by_mandatory_span_descending() -> None:
    short_span = (_exam(1), _exam(3))
    long_span = (_exam(1), _exam(8))

    ordered = SchedulePrioritySorter().sort(
        [short_span, long_span],
        [MANDATORY_SPAN],
        lambda schedule: schedule,
    )

    assert ordered == [long_span, short_span]


def test_sorter_orders_by_max_daily_exams_descending() -> None:
    one_exam_per_day = (_exam(1), _exam(2))
    two_exams_same_day = (_exam(1), _exam(1), _exam(2))

    ordered = SchedulePrioritySorter().sort(
        [one_exam_per_day, two_exams_same_day],
        [MAX_DAILY_EXAMS],
        lambda schedule: schedule,
    )

    assert ordered == [two_exams_same_day, one_exam_per_day]


def test_sorter_chains_priorities_lexicographically() -> None:
    weaker_secondary = (_exam(1), _exam(4), _exam(4))
    stronger_secondary = (_exam(1), _exam(1), _exam(8))

    ordered = SchedulePrioritySorter().sort(
        [weaker_secondary, stronger_secondary],
        [MANDATORY_MIN_GAP, AVERAGE_COHORT_GAP],
        lambda schedule: schedule,
    )

    assert ordered == [stronger_secondary, weaker_secondary]


def test_calendar_day_metrics_count_saturdays_and_holidays_by_date_delta() -> None:
    scorer = ScheduleQualityScorer()
    exams = (_exam(1), _exam(5))

    assert scorer.score(exams, MANDATORY_MIN_GAP) == 4
    assert scorer.score(exams, AVERAGE_COHORT_GAP) == 4
    assert scorer.score(exams, MANDATORY_SPAN) == 4
