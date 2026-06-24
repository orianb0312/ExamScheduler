"""Priority-based sorting for generated exam schedules."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from itertools import combinations
from typing import Callable, Iterable, Sequence, TypeVar


SORTING_RECORD_HEADER = "sorting_priority"
SORTING_RECORD_ALIASES = {SORTING_RECORD_HEADER, "sort_priority", "sort"}

MANDATORY_MIN_GAP = "mandatory_min_gap"
AVERAGE_COHORT_GAP = "average_cohort_gap"
ELECTIVE_CONFLICTS = "elective_conflicts"
MANDATORY_SPAN = "mandatory_span"
MAX_DAILY_EXAMS = "max_daily_exams"


@dataclass(frozen=True)
class SortCriterionDefinition:
    key: str
    title: str
    document_ref: str


SORT_CRITERION_DEFINITIONS: tuple[SortCriterionDefinition, ...] = (
    SortCriterionDefinition(
        key=MANDATORY_MIN_GAP,
        title="Mandatory min gap",
        document_ref="3.1",
    ),
    SortCriterionDefinition(
        key=AVERAGE_COHORT_GAP,
        title="Average cohort gap",
        document_ref="3.2",
    ),
    SortCriterionDefinition(
        key=ELECTIVE_CONFLICTS,
        title="Elective conflicts",
        document_ref="3.3",
    ),
    SortCriterionDefinition(
        key=MANDATORY_SPAN,
        title="Mandatory span",
        document_ref="3.4",
    ),
    SortCriterionDefinition(
        key=MAX_DAILY_EXAMS,
        title="Max daily exams",
        document_ref="3.5",
    ),
)

DEFAULT_SORT_PRIORITY: tuple[str, ...] = tuple(
    definition.key for definition in SORT_CRITERION_DEFINITIONS
)
SORT_CRITERIA_BY_KEY = {
    definition.key: definition for definition in SORT_CRITERION_DEFINITIONS
}

_ALIASES = {
    MANDATORY_MIN_GAP: MANDATORY_MIN_GAP,
    "3.1": MANDATORY_MIN_GAP,
    "min_mandatory_gap": MANDATORY_MIN_GAP,
    "min_days_between_mandatory": MANDATORY_MIN_GAP,
    "mandatory_gap": MANDATORY_MIN_GAP,
    AVERAGE_COHORT_GAP: AVERAGE_COHORT_GAP,
    "3.2": AVERAGE_COHORT_GAP,
    "average_gap": AVERAGE_COHORT_GAP,
    "avg_cohort_gap": AVERAGE_COHORT_GAP,
    "min_days_between_any": AVERAGE_COHORT_GAP,
    ELECTIVE_CONFLICTS: ELECTIVE_CONFLICTS,
    "3.3": ELECTIVE_CONFLICTS,
    "max_elective_conflicts": ELECTIVE_CONFLICTS,
    "elective_same_day_conflicts": ELECTIVE_CONFLICTS,
    MANDATORY_SPAN: MANDATORY_SPAN,
    "3.4": MANDATORY_SPAN,
    "mandatory_exam_span": MANDATORY_SPAN,
    "min_days_before_last_mandatory": MANDATORY_SPAN,
    MAX_DAILY_EXAMS: MAX_DAILY_EXAMS,
    "3.5": MAX_DAILY_EXAMS,
    "daily_exam_count": MAX_DAILY_EXAMS,
    "max_exams_per_day": MAX_DAILY_EXAMS,
}


@dataclass(frozen=True)
class SortableCohort:
    program_id: int
    year: int
    requirement_type: str


@dataclass(frozen=True)
class SortableExam:
    exam_date: date
    cohorts: tuple[SortableCohort, ...]


T = TypeVar("T")


class SchedulePrioritySorter:
    """Sort schedules by a user-chosen priority list of Part 3 criteria."""

    def __init__(self, scorer: "ScheduleQualityScorer | None" = None) -> None:
        self._scorer = scorer or ScheduleQualityScorer()

    def sort(
        self,
        schedules: Iterable[T],
        priority: Sequence[str],
        exam_extractor: Callable[[T], Iterable[SortableExam]],
    ) -> list[T]:
        clean_priority = normalize_sort_priority(priority)
        schedules_with_index = list(enumerate(schedules))
        if not clean_priority:
            return [schedule for _index, schedule in schedules_with_index]

        return [
            schedule
            for _index, schedule in sorted(
                schedules_with_index,
                key=lambda item: self._sort_key(item, clean_priority, exam_extractor),
            )
        ]

    def score_tuple(
        self,
        exams: Iterable[SortableExam],
        priority: Sequence[str],
    ) -> tuple[float, ...]:
        clean_priority = normalize_sort_priority(priority)
        exam_tuple = tuple(exams)
        return tuple(
            self._scorer.score(exam_tuple, criterion_key)
            for criterion_key in clean_priority
        )

    def _sort_key(
        self,
        item: tuple[int, T],
        priority: tuple[str, ...],
        exam_extractor: Callable[[T], Iterable[SortableExam]],
    ) -> tuple[float, ...]:
        original_index, schedule = item
        scores = self.score_tuple(exam_extractor(schedule), priority)
        # Every Part 3 sorting criterion is defined as descending. The original
        # order stays as the final tie-breaker so repeated sorts feel stable.
        return tuple(-score for score in scores) + (float(original_index),)


class ScheduleQualityScorer:
    """Calculate the five Part 3 sort metrics for one schedule system."""

    def score(self, exams: Sequence[SortableExam], criterion_key: str) -> float:
        normalized_key = normalize_sort_criterion_key(criterion_key)
        if normalized_key == MANDATORY_MIN_GAP:
            return float(self._mandatory_min_gap(exams))
        if normalized_key == AVERAGE_COHORT_GAP:
            return self._average_cohort_gap(exams)
        if normalized_key == ELECTIVE_CONFLICTS:
            return float(self._elective_conflicts(exams))
        if normalized_key == MANDATORY_SPAN:
            return float(self._mandatory_span(exams))
        if normalized_key == MAX_DAILY_EXAMS:
            return float(self._max_daily_exams(exams))
        raise ValueError(f"Unknown sorting criterion: '{criterion_key}'.")

    def _mandatory_min_gap(self, exams: Sequence[SortableExam]) -> int:
        gaps = [
            abs((left.exam_date - right.exam_date).days)
            for left, right in combinations(exams, 2)
            if _shared_mandatory_cohorts(left, right)
        ]
        return min(gaps) if gaps else 0

    def _average_cohort_gap(self, exams: Sequence[SortableExam]) -> float:
        gaps = []
        for left, right in combinations(exams, 2):
            shared_cohorts = _shared_cohort_keys(left, right)
            if not shared_cohorts:
                continue
            gap = abs((left.exam_date - right.exam_date).days)
            gaps.extend(gap for _cohort in shared_cohorts)

        if not gaps:
            return 0.0
        return sum(gaps) / len(gaps)

    def _elective_conflicts(self, exams: Sequence[SortableExam]) -> int:
        program_date_counts: Counter[tuple[int, date]] = Counter()
        for exam in exams:
            for program_id in _elective_programs(exam):
                program_date_counts[(program_id, exam.exam_date)] += 1

        return sum(
            count * (count - 1) // 2
            for count in program_date_counts.values()
            if count > 1
        )

    def _mandatory_span(self, exams: Sequence[SortableExam]) -> int:
        dates_by_cohort: dict[tuple[int, int], list[date]] = defaultdict(list)
        for exam in exams:
            for cohort in _mandatory_cohort_keys(exam):
                dates_by_cohort[cohort].append(exam.exam_date)

        spans = [
            (max(dates) - min(dates)).days
            for dates in dates_by_cohort.values()
            if len(dates) > 1
        ]
        return min(spans) if spans else 0

    def _max_daily_exams(self, exams: Sequence[SortableExam]) -> int:
        counts = Counter(exam.exam_date for exam in exams)
        return max(counts.values(), default=0)


def parse_sort_priority_text(text: str) -> tuple[str, ...]:
    """Parse a V1 text sorting file into criterion keys ordered by priority.

    Supported human-editable forms:
    - a plain ordered list, one criterion per line
    - comma-separated criteria
    - the same list under a ``sorting_priority`` header
    - optional ``$$$$`` separators, matching the rest of the V1 text files
    """
    tokens: list[str] = []
    for raw_line in text.lstrip("\ufeff").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line == "$$$$":
            continue

        if ":" in line or "=" in line:
            separator = ":" if ":" in line else "="
            left, right = [part.strip() for part in line.split(separator, 1)]
            if _normalize_token(left) in SORTING_RECORD_ALIASES:
                line = right

        if _normalize_token(line) in SORTING_RECORD_ALIASES:
            continue

        tokens.extend(part.strip() for part in line.split(",") if part.strip())

    if not tokens:
        raise ValueError("Sorting file is empty.")

    return normalize_sort_priority(tokens)


def format_sort_priority(priority: Sequence[str]) -> str:
    records = [SORTING_RECORD_HEADER, *normalize_sort_priority(priority)]
    return "$$$$\n" + "\n".join(records) + "\n"


def normalize_sort_priority(priority: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()

    for raw_key in priority:
        key = normalize_sort_criterion_key(raw_key)
        if key in seen:
            raise ValueError(f"Duplicate sorting criterion: '{key}'.")
        seen.add(key)
        normalized.append(key)

    return tuple(normalized)


def normalize_sort_criterion_key(raw_key: str) -> str:
    key = _normalize_token(str(raw_key))
    try:
        return _ALIASES[key]
    except KeyError as exc:
        valid = ", ".join(definition.key for definition in SORT_CRITERION_DEFINITIONS)
        raise ValueError(
            f"Unknown sorting criterion: '{raw_key}'. Valid options: {valid}."
        ) from exc


def sortable_exams_from_assignment(
    courses: Sequence[object],
    assignment_items: Iterable[tuple[int, date]],
) -> tuple[SortableExam, ...]:
    exams: list[SortableExam] = []
    for course_index, exam_date in assignment_items:
        course = courses[course_index]
        cohorts = tuple(
            SortableCohort(
                program_id=int(affiliation.program_id),
                year=int(affiliation.year),
                requirement_type=_enum_value(affiliation.requirement_type),
            )
            for affiliation in getattr(course, "affiliations", ())
        )
        exams.append(SortableExam(exam_date=exam_date, cohorts=cohorts))
    return tuple(exams)


def sortable_exams_from_display_system(system: object) -> tuple[SortableExam, ...]:
    exams: list[SortableExam] = []
    periods = getattr(system, "periods", ())
    if not isinstance(periods, (list, tuple)):
        return ()

    for period in periods:
        period_exams = getattr(period, "exams", ())
        if not isinstance(period_exams, (list, tuple)):
            continue
        for exam in period_exams:
            exam_date = getattr(exam, "exam_date", None)
            if exam_date is None:
                continue
            cohorts = tuple(
                SortableCohort(
                    program_id=int(cohort.program_id),
                    year=int(cohort.year),
                    requirement_type=str(cohort.requirement_type),
                )
                for cohort in getattr(exam, "cohorts", ())
            )
            exams.append(SortableExam(exam_date=exam_date, cohorts=cohorts))
    return tuple(exams)


def _shared_mandatory_cohorts(
    left: SortableExam,
    right: SortableExam,
) -> set[tuple[int, int]]:
    return _mandatory_cohort_keys(left) & _mandatory_cohort_keys(right)


def _shared_cohort_keys(
    left: SortableExam,
    right: SortableExam,
) -> set[tuple[int, int]]:
    return _cohort_keys(left) & _cohort_keys(right)


def _cohort_keys(exam: SortableExam) -> set[tuple[int, int]]:
    return {(cohort.program_id, cohort.year) for cohort in exam.cohorts}


def _mandatory_cohort_keys(exam: SortableExam) -> set[tuple[int, int]]:
    return {
        (cohort.program_id, cohort.year)
        for cohort in exam.cohorts
        if _requirement_is(cohort.requirement_type, "obligatory")
    }


def _elective_programs(exam: SortableExam) -> set[int]:
    return {
        cohort.program_id
        for cohort in exam.cohorts
        if _requirement_is(cohort.requirement_type, "elective")
    }


def _requirement_is(value: str, expected: str) -> bool:
    return str(value).casefold() == expected


def _enum_value(value: object) -> str:
    raw_value = getattr(value, "value", value)
    return "" if raw_value is None else str(raw_value)


def _normalize_token(value: str) -> str:
    return value.strip().casefold().replace("-", "_").replace(" ", "_")
