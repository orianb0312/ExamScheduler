"""Build Dashboard-tab analytics from the best generated schedule so far."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

from src.analytics.models import ScheduleAnalyticsReport
from src.analytics.schedule_analytics import (
    ScheduleAnalyticsEngine,
    analytics_exams_from_display_system,
)
from src.services.schedule_output_service import ScheduleSystem


SCHEDULES_PER_CHUNK = 1000


@dataclass(frozen=True)
class DashboardAnalyticsSnapshot:
    total_schedules: str
    fitness_score: str
    min_study_gap: str
    current_batch_score: str
    chart_dates: tuple[str, ...]
    chart_values: tuple[int, ...]
    winning_text: str
    bottleneck_text: str
    chunk_number: int
    start_index: int
    end_index: int


class DashboardAnalyticsService:
    """Convert deterministic schedule analytics into dashboard display strings."""

    def __init__(self, engine: ScheduleAnalyticsEngine | None = None) -> None:
        self._engine = engine or ScheduleAnalyticsEngine()

    def build_snapshot(
        self,
        schedule: ScheduleSystem | None,
        *,
        current_batch_schedule: ScheduleSystem | None = None,
        active_priorities: Sequence[str] = (),
        total_schedules: int | None = None,
        current_page: int = 0,
    ) -> DashboardAnalyticsSnapshot:
        if schedule is None:
            return _empty_snapshot()

        exams = analytics_exams_from_display_system(schedule)
        if not exams:
            chunk_number, start_index, end_index = _pagination_values(
                total_schedules,
                current_page,
            )
            return DashboardAnalyticsSnapshot(
                total_schedules=_format_count(total_schedules or 0),
                fitness_score=_schedule_label(schedule),
                min_study_gap="No exam dates",
                current_batch_score=_schedule_label(current_batch_schedule),
                chart_dates=(),
                chart_values=(),
                winning_text=(
                    "The best schedule so far has no dated exam rows available for "
                    "dashboard analytics."
                ),
                bottleneck_text="No bottleneck analysis can be calculated without dated exams.",
                chunk_number=chunk_number,
                start_index=start_index,
                end_index=end_index,
            )

        report = self._engine.analyze(
            exams,
            active_priorities,
            schedule_label=schedule.label,
            schedule_number=schedule.number,
        )
        current_batch_report = _report_for_schedule(
            self._engine,
            current_batch_schedule,
            active_priorities,
        )
        chunk_number, start_index, end_index = _pagination_values(
            total_schedules,
            current_page,
        )
        return DashboardAnalyticsSnapshot(
            total_schedules=_format_count(total_schedules or 1),
            fitness_score=_schedule_label(schedule),
            min_study_gap=_minimum_gap_text(report),
            current_batch_score=_schedule_label(current_batch_schedule),
            chart_dates=tuple(row.exam_date.strftime("%b %d") for row in report.daily_density),
            chart_values=tuple(row.exam_count for row in report.daily_density),
            winning_text=_winning_text(
                report,
                schedule,
                current_batch_report,
                current_batch_schedule,
            ),
            bottleneck_text=_bottleneck_text(report),
            chunk_number=chunk_number,
            start_index=start_index,
            end_index=end_index,
        )


def _empty_snapshot() -> DashboardAnalyticsSnapshot:
    return DashboardAnalyticsSnapshot(
        total_schedules="No schedules",
        fitness_score="No schedule",
        min_study_gap="No data",
        current_batch_score="No batch",
        chart_dates=(),
        chart_values=(),
        winning_text="Generate schedules to display calculated dashboard analytics.",
        bottleneck_text="No bottleneck analysis is available before schedules are generated.",
        chunk_number=0,
        start_index=0,
        end_index=0,
    )


def _pagination_values(
    total_schedules: int | None,
    current_page: int,
) -> tuple[int, int, int]:
    if current_page <= 0:
        return 0, 0, 0

    chunk_number = ((current_page - 1) // SCHEDULES_PER_CHUNK) + 1
    start_index = ((chunk_number - 1) * SCHEDULES_PER_CHUNK) + 1
    end_index = chunk_number * SCHEDULES_PER_CHUNK
    if total_schedules and total_schedules > 0:
        end_index = min(end_index, total_schedules)
    return chunk_number, start_index, end_index


def _fitness_text(report: ScheduleAnalyticsReport, schedule: ScheduleSystem) -> str:
    if report.metric_values:
        metric = report.metric_values[0]
        return f"{metric.title}: {_format_metric(metric.value)}"
    return f"Schedule #{schedule.number}"


def _schedule_label(schedule: ScheduleSystem | None) -> str:
    if schedule is None:
        return "No batch"
    return f"Schedule #{schedule.number}"


def _report_for_schedule(
    engine: ScheduleAnalyticsEngine,
    schedule: ScheduleSystem | None,
    active_priorities: Sequence[str],
) -> ScheduleAnalyticsReport | None:
    if schedule is None:
        return None
    exams = analytics_exams_from_display_system(schedule)
    if not exams:
        return None
    return engine.analyze(
        exams,
        active_priorities,
        schedule_label=schedule.label,
        schedule_number=schedule.number,
    )


def _minimum_gap_text(report: ScheduleAnalyticsReport) -> str:
    cohort_gaps = [
        row.min_gap_days
        for row in report.cohort_matrix
        if row.min_gap_days is not None
    ]
    if cohort_gaps:
        return f"{_format_metric(min(cohort_gaps))} Days"

    sorted_dates = sorted(exam.exam_date for exam in report.scheduled_exams)
    gaps = _date_gaps(sorted_dates)
    if gaps:
        return f"{_format_metric(min(gaps))} Days"
    return "No gap data"


def _winning_text(
    report: ScheduleAnalyticsReport,
    schedule: ScheduleSystem,
    current_batch_report: ScheduleAnalyticsReport | None,
    current_batch_schedule: ScheduleSystem | None,
) -> str:
    text = (
        f"Best schedule so far #{schedule.number} contains {report.exam_count} exams "
        f"across {len(report.daily_density)} exam dates. It wins on "
        f"{_fitness_text(report, schedule)}. "
        f"{_busiest_day_summary(report)} {_tightest_gap_summary(report)}"
    ).strip()
    if current_batch_report is None or current_batch_schedule is None:
        return text

    current_score = _fitness_text(current_batch_report, current_batch_schedule)
    if current_batch_schedule.number == schedule.number:
        return (
            f"{text} The latest batch also contains this global winner, so no "
            "earlier schedule is currently beating it."
        )
    return (
        f"{text} Current batch best is schedule #{current_batch_schedule.number} "
        f"with {current_score}, so the latest batch is useful but has not "
        "overtaken the best-so-far schedule."
    )


def _bottleneck_text(report: ScheduleAnalyticsReport) -> str:
    if report.bottlenecks:
        bottleneck = report.bottlenecks[0]
        extra = _loaded_cohort_summary(report)
        return (
            f"Main pressure point: {bottleneck.label} under "
            f"{bottleneck.priority_title}. {bottleneck.detail}. {extra}"
        )
    if len(report.cross_sectional_insights) > 1:
        return (
            f"No active-priority bottleneck crossed the threshold. "
            f"{report.cross_sectional_insights[1]} {_busiest_day_summary(report)}"
        )
    return (
        "No active-priority bottleneck crossed the deterministic thresholds. "
        f"{_busiest_day_summary(report)}"
    )


def _busiest_day_summary(report: ScheduleAnalyticsReport) -> str:
    busiest_day = max(
        report.daily_density,
        key=lambda row: (row.exam_count, row.cohort_collision_pairs),
        default=None,
    )
    if busiest_day is None:
        return "No daily-load signal is available."
    return (
        f"The busiest date is {busiest_day.exam_date.strftime('%b %d')} with "
        f"{busiest_day.exam_count} {_plural('exam', busiest_day.exam_count)} "
        f"and {busiest_day.cohort_collision_pairs} "
        f"{_plural('same-cohort collision pair', busiest_day.cohort_collision_pairs)}."
    )


def _tightest_gap_summary(report: ScheduleAnalyticsReport) -> str:
    tightest_gap = min(
        (
            row
            for row in report.cohort_matrix
            if row.min_gap_days is not None
        ),
        key=lambda row: row.min_gap_days or 0,
        default=None,
    )
    if tightest_gap is None:
        return "No cohort spacing risk was detected."
    return (
        f"The tightest student-facing spacing is program "
        f"{tightest_gap.program_id}, year {tightest_gap.year}: "
        f"{tightest_gap.min_gap_days} days."
    )


def _loaded_cohort_summary(report: ScheduleAnalyticsReport) -> str:
    loaded_cohort = max(
        report.cohort_matrix,
        key=lambda row: (row.exam_count, row.same_day_pairs, row.mandatory_count),
        default=None,
    )
    if loaded_cohort is None:
        return "No cohort load matrix is available."
    return (
        f"Most loaded cohort is program {loaded_cohort.program_id}, "
        f"year {loaded_cohort.year} with {loaded_cohort.exam_count} "
        f"{_plural('exam', loaded_cohort.exam_count)} "
        f"({loaded_cohort.mandatory_count} mandatory, "
        f"{loaded_cohort.elective_count} elective)."
    )


def _plural(noun: str, count: int) -> str:
    if count == 1:
        return noun
    return f"{noun}s"


def _date_gaps(values: Sequence[date]) -> list[int]:
    return [
        (right - left).days
        for left, right in zip(values, values[1:])
    ]


def _format_count(value: int) -> str:
    if value <= 0:
        return "No schedules"
    return f"{value:,}"


def _format_metric(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"
