from dataclasses import dataclass
from datetime import date
from pathlib import Path

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


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class RankingCase:
    # A tiny named schedule makes the expected order readable in the assertions.
    name: str
    exams: tuple[SortableExam, ...]


def _exam(
    day: int,
    requirement: str = "Obligatory",
    *,
    program_id: int = 83101,
    year: int = 1,
) -> SortableExam:
    return SortableExam(
        exam_date=date(2026, 1, day),
        cohorts=(
            SortableCohort(
                program_id=program_id,
                year=year,
                requirement_type=requirement,
            ),
        ),
    )


def _ranking_case(
    name: str,
    second_mandatory_day: int,
    extra_same_day_programs: tuple[int, ...],
) -> RankingCase:
    # The first two exams control Metric 3.1 for one mandatory cohort.
    exams = [
        _exam(1, program_id=83101),
        _exam(second_mandatory_day, program_id=83101),
    ]
    # Extra programs on day 1 raise Metric 3.5 without changing Metric 3.1.
    exams.extend(
        _exam(1, program_id=program_id)
        for program_id in extra_same_day_programs
    )
    return RankingCase(name=name, exams=tuple(exams))


RANKING_CASES = (
    _ranking_case("wide_gap_crowded", 7, (83102, 83103)),
    _ranking_case("wide_gap_medium", 7, (83102,)),
    _ranking_case("wide_gap_light", 7, ()),
    _ranking_case("middle_gap_crowded", 5, (83102, 83103)),
    _ranking_case("middle_gap_medium", 5, (83102,)),
    _ranking_case("tight_gap_heaviest", 3, (83102, 83103, 83104)),
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


def test_repository_v1_sorting_priority_file_is_valid() -> None:
    sorting_file = PROJECT_ROOT / "data" / "SortingPriority.txt"

    assert sorting_file.exists()
    assert parse_sort_priority_text(sorting_file.read_text(encoding="utf-8")) == (
        MANDATORY_MIN_GAP,
        AVERAGE_COHORT_GAP,
        ELECTIVE_CONFLICTS,
        MANDATORY_SPAN,
        MAX_DAILY_EXAMS,
    )


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


def test_ranking_combination_fixture_scores_match_documented_metrics() -> None:
    # This keeps the code fixture aligned with the prep table in the docs.
    scorer = SchedulePrioritySorter()

    actual_scores = {
        ranking_case.name: scorer.score_tuple(
            ranking_case.exams,
            [MANDATORY_MIN_GAP, MAX_DAILY_EXAMS],
        )
        for ranking_case in RANKING_CASES
    }

    assert actual_scores == {
        "wide_gap_crowded": (6.0, 3.0),
        "wide_gap_medium": (6.0, 2.0),
        "wide_gap_light": (6.0, 1.0),
        "middle_gap_crowded": (4.0, 3.0),
        "middle_gap_medium": (4.0, 2.0),
        "tight_gap_heaviest": (2.0, 4.0),
    }


@pytest.mark.parametrize(
    ("priority", "expected_order"),
    (
        (
            (MANDATORY_MIN_GAP, MAX_DAILY_EXAMS),
            (
                "wide_gap_crowded",
                "wide_gap_medium",
                "wide_gap_light",
                "middle_gap_crowded",
                "middle_gap_medium",
                "tight_gap_heaviest",
            ),
        ),
        (
            (MAX_DAILY_EXAMS, MANDATORY_MIN_GAP),
            (
                "tight_gap_heaviest",
                "wide_gap_crowded",
                "middle_gap_crowded",
                "wide_gap_medium",
                "middle_gap_medium",
                "wide_gap_light",
            ),
        ),
    ),
    ids=("metric_3_1_primary", "metric_3_5_primary"),
)
def test_ranking_combinations_follow_documented_lexicographic_order(
    priority: tuple[str, ...],
    expected_order: tuple[str, ...],
) -> None:
    # Swapping the primary metric must swap the first comparison, not blend scores.
    ordered = SchedulePrioritySorter().sort(
        RANKING_CASES,
        priority,
        lambda ranking_case: ranking_case.exams,
    )

    assert tuple(ranking_case.name for ranking_case in ordered) == expected_order


def test_calendar_day_metrics_count_saturdays_and_holidays_by_date_delta() -> None:
    scorer = ScheduleQualityScorer()
    exams = (_exam(1), _exam(5))

    assert scorer.score(exams, MANDATORY_MIN_GAP) == 4
    assert scorer.score(exams, AVERAGE_COHORT_GAP) == 4
    assert scorer.score(exams, MANDATORY_SPAN) == 4
