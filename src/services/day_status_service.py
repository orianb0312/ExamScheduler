"""Helpers for excluding and restoring individual exam-period days."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

from src.models.scheduling import DateExclusion, ExamPeriod


def copy_exam_period(period: ExamPeriod) -> ExamPeriod:
    return ExamPeriod(
        semester=period.semester,
        term=period.term,
        start_date=period.start_date,
        end_date=period.end_date,
        exclusions=[
            DateExclusion(
                start_date=exclusion.start_date,
                end_date=exclusion.end_date,
            )
            for exclusion in period.exclusions
        ],
    )


def exclude_day(period: ExamPeriod, day: date) -> None:
    _require_day_inside_period(period, day)
    if not period.is_date_valid(day):
        return
    period.exclusions.append(DateExclusion(start_date=day))
    period.exclusions.sort(key=_exclusion_sort_key)


def restore_day(period: ExamPeriod, day: date) -> None:
    _require_day_inside_period(period, day)
    period.exclusions = _restore_day_in_exclusions(period.exclusions, day)


def update_period_dates(period: ExamPeriod, start_date: date, end_date: date) -> None:
    if start_date > end_date:
        raise ValueError("Start date must be on or before end date.")

    period.start_date = start_date
    period.end_date = end_date


def iter_period_days(period: ExamPeriod) -> Iterable[date]:
    current = period.start_date
    while current <= period.end_date:
        yield current
        current += timedelta(days=1)


def format_exam_periods(periods: Iterable[ExamPeriod]) -> str:
    records = []
    for period in periods:
        lines = [
            f"{_enum_value(period.semester)},{_enum_value(period.term)}",
            f"{_format_date(period.start_date)}, {_format_date(period.end_date)}",
        ]
        for exclusion in sorted(period.exclusions, key=_exclusion_sort_key):
            lines.append(f"- {_format_exclusion(exclusion)}")
        records.append("\n".join(lines))

    if not records:
        return ""
    return "\n".join(f"$$$$\n{record}" for record in records) + "\n"


def _restore_day_in_exclusions(
    exclusions: list[DateExclusion],
    day: date,
) -> list[DateExclusion]:
    updated: list[DateExclusion] = []
    for exclusion in exclusions:
        exclusion_end = exclusion.end_date or exclusion.start_date
        if not (exclusion.start_date <= day <= exclusion_end):
            updated.append(exclusion)
            continue

        if exclusion.start_date < day:
            updated.append(_make_exclusion(exclusion.start_date, day - timedelta(days=1)))
        if day < exclusion_end:
            updated.append(_make_exclusion(day + timedelta(days=1), exclusion_end))

    return sorted(updated, key=_exclusion_sort_key)


def _make_exclusion(start_date: date, end_date: date) -> DateExclusion:
    if start_date == end_date:
        return DateExclusion(start_date=start_date)
    return DateExclusion(start_date=start_date, end_date=end_date)


def _format_exclusion(exclusion: DateExclusion) -> str:
    if exclusion.end_date:
        return f"{_format_date(exclusion.start_date)}, {_format_date(exclusion.end_date)}"
    return _format_date(exclusion.start_date)


def _format_date(value: date) -> str:
    return value.strftime("%d-%m-%Y")


def _enum_value(value) -> str:
    return str(getattr(value, "value", value))


def _require_day_inside_period(period: ExamPeriod, day: date) -> None:
    if not (period.start_date <= day <= period.end_date):
        raise ValueError(f"Day {day} is outside the selected exam period.")


def _exclusion_sort_key(exclusion: DateExclusion) -> tuple[date, date]:
    return exclusion.start_date, exclusion.end_date or exclusion.start_date
