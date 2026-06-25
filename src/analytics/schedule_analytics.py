"""Rule-based analytics for generated exam schedules."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from itertools import combinations
from typing import Iterable, Sequence

from src.analytics.models import (
    AnalyticsCohort,
    AnalyticsExam,
    BottleneckDiagnostic,
    CohortMatrixRow,
    DailyDensityRow,
    MetricValue,
    ScheduleAnalyticsReport,
)
from src.sorting.schedule_priority import (
    AVERAGE_COHORT_GAP,
    ELECTIVE_CONFLICTS,
    MANDATORY_MIN_GAP,
    MANDATORY_SPAN,
    MAX_DAILY_EXAMS,
    SORT_CRITERIA_BY_KEY,
    ScheduleQualityScorer,
    SortableCohort,
    SortableExam,
    normalize_sort_priority,
)


class ScheduleAnalyticsEngine:
    """Build deterministic schedule diagnostics from active Part 3 priorities."""

    def __init__(self, scorer: ScheduleQualityScorer | None = None) -> None:
        self._scorer = scorer or ScheduleQualityScorer()

    def analyze(
        self,
        exams: Iterable[AnalyticsExam],
        active_priorities: Sequence[str],
        *,
        schedule_label: str = "Schedule",
        schedule_number: int | None = None,
    ) -> ScheduleAnalyticsReport:
        clean_exams = tuple(exam for exam in exams if exam.exam_date is not None)
        clean_priorities = normalize_sort_priority(active_priorities)
        sortable_exams = _to_sortable_exams(clean_exams)

        # Every number below is derived from the schedule rows and active priorities.
        metric_values = tuple(
            self._metric_value(sortable_exams, key, index)
            for index, key in enumerate(clean_priorities, start=1)
        )
        daily_density = _daily_density_rows(clean_exams)
        cohort_matrix = _cohort_matrix_rows(clean_exams)
        bottlenecks = _bottleneck_rows(
            clean_priorities,
            daily_density,
            cohort_matrix,
            clean_exams,
        )
        cross_sectional_insights = _cross_sectional_insight_lines(
            clean_priorities,
            daily_density,
            cohort_matrix,
            bottlenecks,
        )
        functional_justification = _functional_justification_lines(metric_values)

        return ScheduleAnalyticsReport(
            schedule_label=schedule_label,
            schedule_number=schedule_number,
            active_priorities=clean_priorities,
            exam_count=len(clean_exams),
            metric_values=metric_values,
            daily_density=daily_density,
            cohort_matrix=cohort_matrix,
            bottlenecks=bottlenecks,
            diagnostics=_diagnostic_lines(
                len(clean_exams),
                metric_values,
                daily_density,
                cohort_matrix,
                bottlenecks,
            ),
            scheduled_exams=clean_exams,
            cross_sectional_insights=cross_sectional_insights,
            functional_justification=functional_justification,
        )

    def _metric_value(
        self,
        sortable_exams: tuple[SortableExam, ...],
        key: str,
        priority_position: int,
    ) -> MetricValue:
        definition = SORT_CRITERIA_BY_KEY[key]
        return MetricValue(
            key=key,
            title=definition.title,
            document_ref=definition.document_ref,
            priority_position=priority_position,
            value=float(self._scorer.score(sortable_exams, key)),
        )


def analytics_exams_from_assignment(
    courses: Sequence[object],
    assignment_items: Iterable[tuple[int, date]],
    *,
    semester_label: str = "",
    term_label: str = "",
) -> tuple[AnalyticsExam, ...]:
    """Convert scheduler assignments into report-ready exam rows."""

    exams: list[AnalyticsExam] = []
    for course_index, exam_date in assignment_items:
        course = courses[course_index]
        exams.append(
            AnalyticsExam(
                course_name=str(getattr(course, "name", "")),
                course_id=_optional_int(getattr(course, "course_id", None)),
                instructor=str(getattr(course, "instructor", "")),
                exam_date=exam_date,
                semester_label=semester_label,
                term_label=term_label,
                cohorts=tuple(
                    AnalyticsCohort(
                        program_id=int(affiliation.program_id),
                        year=int(affiliation.year),
                        requirement_type=_enum_value(affiliation.requirement_type),
                    )
                    for affiliation in getattr(course, "affiliations", ())
                ),
            )
        )
    return tuple(exams)


def analytics_exams_from_display_system(system: object) -> tuple[AnalyticsExam, ...]:
    """Convert a UI/service schedule system into report-ready exam rows."""

    exams: list[AnalyticsExam] = []
    for period in getattr(system, "periods", ()):
        semester_label = str(getattr(period, "semester_label", ""))
        term_label = str(getattr(period, "term_label", ""))
        for exam in getattr(period, "exams", ()):
            exam_date = getattr(exam, "exam_date", None)
            if exam_date is None:
                continue
            exams.append(
                AnalyticsExam(
                    course_name=str(getattr(exam, "course_name", "")),
                    course_id=_optional_int(getattr(exam, "course_id", None)),
                    instructor=str(getattr(exam, "instructor", "")),
                    exam_date=exam_date,
                    semester_label=semester_label,
                    term_label=term_label,
                    cohorts=_display_exam_cohorts(exam),
                )
            )
    return tuple(exams)


def _daily_density_rows(
    exams: tuple[AnalyticsExam, ...],
) -> tuple[DailyDensityRow, ...]:
    total_exams = len(exams)
    date_counts = Counter(exam.exam_date for exam in exams)
    cohort_date_counts: Counter[tuple[int, int, date]] = Counter()

    # Count same-cohort pressure per program/year/date, then collapse it by date.
    for exam in exams:
        for cohort_key in _cohort_keys(exam):
            cohort_date_counts[(cohort_key[0], cohort_key[1], exam.exam_date)] += 1

    collision_pairs_by_date: Counter[date] = Counter()
    for (_program_id, _year, exam_date), count in cohort_date_counts.items():
        if count > 1:
            collision_pairs_by_date[exam_date] += _pair_count(count)

    return tuple(
        DailyDensityRow(
            exam_date=exam_date,
            exam_count=date_counts[exam_date],
            density_share=(
                date_counts[exam_date] / total_exams if total_exams else 0.0
            ),
            cohort_collision_pairs=collision_pairs_by_date[exam_date],
        )
        for exam_date in sorted(date_counts)
    )


def _cohort_matrix_rows(
    exams: tuple[AnalyticsExam, ...],
) -> tuple[CohortMatrixRow, ...]:
    # Program/year rows make cross-sectional bottlenecks visible without UI logic.
    grouped: dict[tuple[int, int], list[tuple[date, str]]] = defaultdict(list)
    for exam in exams:
        seen_in_exam: set[tuple[int, int, str]] = set()
        for cohort in exam.cohorts:
            requirement_type = _enum_value(cohort.requirement_type)
            unique_key = (cohort.program_id, cohort.year, requirement_type)
            if unique_key in seen_in_exam:
                continue
            seen_in_exam.add(unique_key)
            grouped[(cohort.program_id, cohort.year)].append(
                (exam.exam_date, requirement_type)
            )

    rows: list[CohortMatrixRow] = []
    for (program_id, year), entries in sorted(grouped.items()):
        dates = sorted(exam_date for exam_date, _requirement in entries)
        mandatory_dates = sorted(
            exam_date
            for exam_date, requirement in entries
            if _requirement_is(requirement, "obligatory")
        )
        gaps = _date_gaps(dates)
        mandatory_gaps = _date_gaps(mandatory_dates)
        date_counts = Counter(dates)
        rows.append(
            CohortMatrixRow(
                program_id=program_id,
                year=year,
                exam_count=len(entries),
                mandatory_count=sum(
                    1
                    for _exam_date, requirement in entries
                    if _requirement_is(requirement, "obligatory")
                ),
                elective_count=sum(
                    1
                    for _exam_date, requirement in entries
                    if _requirement_is(requirement, "elective")
                ),
                first_exam_date=dates[0] if dates else None,
                last_exam_date=dates[-1] if dates else None,
                span_days=(dates[-1] - dates[0]).days if len(dates) > 1 else None,
                min_gap_days=min(gaps) if gaps else None,
                average_gap_days=(sum(gaps) / len(gaps)) if gaps else None,
                same_day_pairs=sum(
                    _pair_count(count) for count in date_counts.values() if count > 1
                ),
                first_mandatory_date=mandatory_dates[0] if mandatory_dates else None,
                last_mandatory_date=mandatory_dates[-1] if mandatory_dates else None,
                mandatory_span_days=(
                    (mandatory_dates[-1] - mandatory_dates[0]).days
                    if len(mandatory_dates) > 1
                    else None
                ),
                mandatory_min_gap_days=(
                    min(mandatory_gaps) if mandatory_gaps else None
                ),
            )
        )

    return tuple(rows)


def _bottleneck_rows(
    active_priorities: tuple[str, ...],
    daily_density: tuple[DailyDensityRow, ...],
    cohort_matrix: tuple[CohortMatrixRow, ...],
    exams: tuple[AnalyticsExam, ...],
) -> tuple[BottleneckDiagnostic, ...]:
    rows: list[BottleneckDiagnostic] = []

    # Only active priorities create bottleneck rows; inactive criteria stay silent.
    for priority_position, key in enumerate(active_priorities, start=1):
        definition = SORT_CRITERIA_BY_KEY[key]
        if key == MAX_DAILY_EXAMS:
            rows.extend(
                BottleneckDiagnostic(
                    priority_key=key,
                    priority_title=definition.title,
                    priority_position=priority_position,
                    category="daily_density",
                    label=row.exam_date.isoformat(),
                    metric_value=float(row.exam_count),
                    pressure_score=float(row.exam_count),
                    detail=(
                        f"{row.exam_count} exams on one date; "
                        f"{row.cohort_collision_pairs} same-cohort pairs"
                    ),
                )
                for row in daily_density
                if row.exam_count > 0
            )
        elif key == ELECTIVE_CONFLICTS:
            rows.extend(
                _elective_conflict_bottlenecks(
                    key,
                    definition.title,
                    priority_position,
                    exams,
                )
            )
        elif key == MANDATORY_MIN_GAP:
            rows.extend(
                _small_gap_bottlenecks(
                    key,
                    definition.title,
                    priority_position,
                    cohort_matrix,
                    mandatory_only=True,
                    category="mandatory_gap",
                )
            )
        elif key == AVERAGE_COHORT_GAP:
            rows.extend(
                _small_gap_bottlenecks(
                    key,
                    definition.title,
                    priority_position,
                    cohort_matrix,
                    mandatory_only=False,
                    category="average_cohort_gap",
                )
            )
        elif key == MANDATORY_SPAN:
            rows.extend(
                _mandatory_span_bottlenecks(
                    key,
                    definition.title,
                    priority_position,
                    cohort_matrix,
                )
            )

    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row.priority_position,
                -row.pressure_score,
                row.category,
                row.label,
            ),
        )
    )


def _elective_conflict_bottlenecks(
    key: str,
    title: str,
    priority_position: int,
    exams: tuple[AnalyticsExam, ...],
) -> list[BottleneckDiagnostic]:
    elective_counts: Counter[tuple[int, date]] = Counter()
    for exam in exams:
        for program_id in _elective_programs(exam):
            elective_counts[(program_id, exam.exam_date)] += 1

    rows: list[BottleneckDiagnostic] = []
    for (program_id, exam_date), count in sorted(elective_counts.items()):
        if count <= 1:
            continue
        pair_count = _pair_count(count)
        rows.append(
            BottleneckDiagnostic(
                priority_key=key,
                priority_title=title,
                priority_position=priority_position,
                category="elective_conflict",
                label=f"Program {program_id} on {exam_date.isoformat()}",
                metric_value=float(pair_count),
                pressure_score=float(pair_count),
                detail=f"{count} elective exams create {pair_count} same-day pairs",
            )
        )
    return rows


def _small_gap_bottlenecks(
    key: str,
    title: str,
    priority_position: int,
    cohort_matrix: tuple[CohortMatrixRow, ...],
    *,
    mandatory_only: bool,
    category: str,
) -> list[BottleneckDiagnostic]:
    rows: list[BottleneckDiagnostic] = []
    for row in cohort_matrix:
        if mandatory_only and row.mandatory_count < 2:
            continue
        if not mandatory_only and row.exam_count < 2:
            continue

        metric_value = (
            row.mandatory_min_gap_days if mandatory_only else row.average_gap_days
        )
        if metric_value is None:
            continue

        rows.append(
            BottleneckDiagnostic(
                priority_key=key,
                priority_title=title,
                priority_position=priority_position,
                category=category,
                label=f"Program {row.program_id}, year {row.year}",
                metric_value=float(metric_value),
                pressure_score=_inverse_pressure(float(metric_value)),
                detail=(
                    f"{row.exam_count} exams; min gap {row.min_gap_days}; "
                    f"mandatory min gap {row.mandatory_min_gap_days}; "
                    f"average gap {_format_optional_float(row.average_gap_days)}"
                ),
            )
        )
    return rows


def _mandatory_span_bottlenecks(
    key: str,
    title: str,
    priority_position: int,
    cohort_matrix: tuple[CohortMatrixRow, ...],
) -> list[BottleneckDiagnostic]:
    rows: list[BottleneckDiagnostic] = []
    for row in cohort_matrix:
        if row.mandatory_count < 2 or row.mandatory_span_days is None:
            continue
        rows.append(
            BottleneckDiagnostic(
                priority_key=key,
                priority_title=title,
                priority_position=priority_position,
                category="mandatory_span",
                label=f"Program {row.program_id}, year {row.year}",
                metric_value=float(row.mandatory_span_days),
                pressure_score=_inverse_pressure(float(row.mandatory_span_days)),
                detail=(
                    f"{row.mandatory_count} mandatory exams from "
                    f"{_format_date(row.first_mandatory_date)} to "
                    f"{_format_date(row.last_mandatory_date)}"
                ),
            )
        )
    return rows


def _diagnostic_lines(
    exam_count: int,
    metric_values: tuple[MetricValue, ...],
    daily_density: tuple[DailyDensityRow, ...],
    cohort_matrix: tuple[CohortMatrixRow, ...],
    bottlenecks: tuple[BottleneckDiagnostic, ...],
) -> tuple[str, ...]:
    active_priority_text = (
        ", ".join(metric.key for metric in metric_values)
        if metric_values
        else "none"
    )
    busiest_day = max(daily_density, key=lambda row: row.exam_count, default=None)
    most_loaded_cohort = max(
        cohort_matrix,
        key=lambda row: (row.exam_count, row.same_day_pairs),
        default=None,
    )

    lines = [
        "Calculation mode: deterministic rules",
        f"Exam count: {exam_count}",
        f"Active priorities: {active_priority_text}",
        f"Metric rows: {len(metric_values)}",
        f"Daily density rows: {len(daily_density)}",
        f"Cohort matrix rows: {len(cohort_matrix)}",
        f"Bottleneck rows: {len(bottlenecks)}",
    ]
    if busiest_day is not None:
        lines.append(
            "Busiest date: "
            f"{busiest_day.exam_date.isoformat()} "
            f"({busiest_day.exam_count} exams)"
        )
    if most_loaded_cohort is not None:
        lines.append(
            "Most loaded cohort: "
            f"program {most_loaded_cohort.program_id}, "
            f"year {most_loaded_cohort.year} "
            f"({most_loaded_cohort.exam_count} exams)"
        )

    return tuple(lines)


def _cross_sectional_insight_lines(
    active_priorities: tuple[str, ...],
    daily_density: tuple[DailyDensityRow, ...],
    cohort_matrix: tuple[CohortMatrixRow, ...],
    bottlenecks: tuple[BottleneckDiagnostic, ...],
) -> tuple[str, ...]:
    # The wording is human-readable, but the selection rules are still fixed code.
    lines: list[str] = []

    busiest_day = max(
        daily_density,
        key=lambda row: (row.exam_count, row.cohort_collision_pairs),
        default=None,
    )
    if busiest_day is None:
        lines.append("No dated exams were available for density analysis.")
    else:
        lines.append(
            "Busiest date is "
            f"{busiest_day.exam_date.isoformat()} with "
            f"{busiest_day.exam_count} exams "
            f"({_format_ratio(busiest_day.density_share)} of the schedule) "
            f"and {busiest_day.cohort_collision_pairs} same-cohort pairs."
        )

    loaded_cohort = max(
        cohort_matrix,
        key=lambda row: (row.exam_count, row.same_day_pairs, row.mandatory_count),
        default=None,
    )
    if loaded_cohort is None:
        lines.append("No program/year cohort matrix rows were produced.")
    else:
        lines.append(
            "Most loaded cohort is program "
            f"{loaded_cohort.program_id}, year {loaded_cohort.year}: "
            f"{loaded_cohort.exam_count} exams, "
            f"{loaded_cohort.mandatory_count} mandatory, "
            f"{loaded_cohort.elective_count} elective, "
            f"{loaded_cohort.same_day_pairs} same-day pairs."
        )

    tightest_gap = min(
        (
            row
            for row in cohort_matrix
            if row.min_gap_days is not None
        ),
        key=lambda row: row.min_gap_days or 0,
        default=None,
    )
    if tightest_gap is not None:
        lines.append(
            "Tightest cohort spacing is program "
            f"{tightest_gap.program_id}, year {tightest_gap.year}: "
            f"{tightest_gap.min_gap_days} days between affected exams."
        )

    if not active_priorities:
        lines.append(
            "No active sorting priorities were selected, so priority bottleneck "
            "rows remain intentionally empty."
        )
    elif bottlenecks:
        top_bottleneck = bottlenecks[0]
        lines.append(
            "Top active-priority bottleneck is "
            f"{top_bottleneck.priority_key} at {top_bottleneck.label}: "
            f"value {_format_metric(top_bottleneck.metric_value)}, "
            f"pressure {_format_metric(top_bottleneck.pressure_score)}."
        )
    else:
        lines.append(
            "Active priorities were evaluated and no bottleneck rows crossed "
            "the deterministic reporting thresholds."
        )

    return tuple(lines)


def _functional_justification_lines(
    metric_values: tuple[MetricValue, ...],
) -> tuple[str, ...]:
    # This mirrors the deterministic scheduler ranking: priority order, then input order.
    if not metric_values:
        return (
            "No functional ranking justification was generated because no "
            "Part 3 sorting priorities are active.",
        )

    ranking_vector = ", ".join(
        _format_metric(metric.value) for metric in metric_values
    )
    lines = [
        "Schedules are compared lexicographically in the selected priority "
        "order; each active Part 3 metric is maximized before the next "
        "priority is considered.",
        f"Ranking vector for this schedule: ({ranking_vector}).",
    ]

    for metric in metric_values:
        lines.append(
            f"Priority {metric.priority_position}: {metric.title} "
            f"({metric.document_ref}) produced value "
            f"{_format_metric(metric.value)}."
        )

    lines.append(
        "If all active metric values match, the scheduler keeps the original "
        "generator order as the final deterministic tie-breaker."
    )
    return tuple(lines)


def _to_sortable_exams(exams: tuple[AnalyticsExam, ...]) -> tuple[SortableExam, ...]:
    return tuple(
        SortableExam(
            exam_date=exam.exam_date,
            cohorts=tuple(
                SortableCohort(
                    program_id=cohort.program_id,
                    year=cohort.year,
                    requirement_type=cohort.requirement_type,
                )
                for cohort in exam.cohorts
            ),
        )
        for exam in exams
    )


def _display_exam_cohorts(exam: object) -> tuple[AnalyticsCohort, ...]:
    cohorts = tuple(
        AnalyticsCohort(
            program_id=int(cohort.program_id),
            year=int(cohort.year),
            requirement_type=_enum_value(cohort.requirement_type),
        )
        for cohort in getattr(exam, "cohorts", ())
    )
    if cohorts:
        return cohorts

    program_ids = tuple(getattr(exam, "program_ids", ()) or ())
    requirement_types = tuple(getattr(exam, "requirement_types", ()) or ("",))
    fallback: list[AnalyticsCohort] = []
    for program_id in program_ids:
        for requirement_type in requirement_types:
            fallback.append(
                AnalyticsCohort(
                    program_id=int(program_id),
                    year=0,
                    requirement_type=str(requirement_type),
                )
            )
    return tuple(fallback)


def _cohort_keys(exam: AnalyticsExam) -> set[tuple[int, int]]:
    return {(cohort.program_id, cohort.year) for cohort in exam.cohorts}


def _elective_programs(exam: AnalyticsExam) -> set[int]:
    return {
        cohort.program_id
        for cohort in exam.cohorts
        if _requirement_is(cohort.requirement_type, "elective")
    }


def _date_gaps(dates: Sequence[date]) -> list[int]:
    return [
        abs((left - right).days)
        for left, right in combinations(dates, 2)
    ]


def _pair_count(count: int) -> int:
    return count * (count - 1) // 2


def _inverse_pressure(value: float) -> float:
    return 1.0 / (1.0 + max(0.0, value))


def _requirement_is(value: str, expected: str) -> bool:
    return str(value).casefold() == expected


def _enum_value(value: object) -> str:
    raw_value = getattr(value, "value", value)
    return "" if raw_value is None else str(raw_value)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _format_date(value: date | None) -> str:
    return value.isoformat() if value is not None else "none"


def _format_optional_float(value: float | None) -> str:
    if value is None:
        return "none"
    return f"{value:.2f}"


def _format_ratio(value: float) -> str:
    return f"{value * 100:.1f}%"


def _format_metric(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")
