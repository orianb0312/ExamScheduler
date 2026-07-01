"""Plain data objects used by deterministic schedule analytics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class AnalyticsCohort:
    """A program/year slice that may be affected by an exam."""

    program_id: int
    year: int
    requirement_type: str


@dataclass(frozen=True)
class AnalyticsExam:
    """One scheduled exam with the course and cohort details needed for reports."""

    course_name: str
    exam_date: date
    instructor: str = ""
    course_id: int | None = None
    semester_label: str = ""
    term_label: str = ""
    cohorts: tuple[AnalyticsCohort, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MetricValue:
    """One active Part 3 sorting metric calculated for a schedule."""

    key: str
    title: str
    document_ref: str
    priority_position: int
    value: float


@dataclass(frozen=True)
class DailyDensityRow:
    """How crowded one exam date is inside the schedule."""

    exam_date: date
    exam_count: int
    density_share: float
    cohort_collision_pairs: int


@dataclass(frozen=True)
class CohortMatrixRow:
    """Cross-section of one program/year cohort across all scheduled exams."""

    program_id: int
    year: int
    exam_count: int
    mandatory_count: int
    elective_count: int
    first_exam_date: date | None
    last_exam_date: date | None
    span_days: int | None
    min_gap_days: int | None
    average_gap_days: float | None
    same_day_pairs: int
    first_mandatory_date: date | None
    last_mandatory_date: date | None
    mandatory_span_days: int | None
    mandatory_min_gap_days: int | None


@dataclass(frozen=True)
class BottleneckDiagnostic:
    """A deterministic warning row derived from an active priority metric."""

    priority_key: str
    priority_title: str
    priority_position: int
    category: str
    label: str
    metric_value: float
    pressure_score: float
    detail: str


@dataclass(frozen=True)
class ScheduleAnalyticsReport:
    """Complete analytics payload for one generated schedule."""

    schedule_label: str
    schedule_number: int | None
    active_priorities: tuple[str, ...]
    exam_count: int
    metric_values: tuple[MetricValue, ...]
    daily_density: tuple[DailyDensityRow, ...]
    cohort_matrix: tuple[CohortMatrixRow, ...]
    bottlenecks: tuple[BottleneckDiagnostic, ...]
    diagnostics: tuple[str, ...]
    scheduled_exams: tuple[AnalyticsExam, ...] = field(default_factory=tuple)
    cross_sectional_insights: tuple[str, ...] = field(default_factory=tuple)
    functional_justification: tuple[str, ...] = field(default_factory=tuple)
    calculation_mode: str = "deterministic_rules"
