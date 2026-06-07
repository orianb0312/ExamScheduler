from datetime import date

import pytest

from src.models.enums import Semester, Term
from src.models.scheduling import DateExclusion, ExamPeriod
from src.services.day_status_service import exclude_day, format_exam_periods, restore_day


def _period(exclusions=None) -> ExamPeriod:
    return ExamPeriod(
        semester=Semester.FALL,
        term=Term.ALEPH,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 5),
        exclusions=list(exclusions or []),
    )


def test_exclude_day_removes_day_from_available_dates():
    period = _period()

    exclude_day(period, date(2026, 1, 3))

    assert period.is_date_valid(date(2026, 1, 2))
    assert not period.is_date_valid(date(2026, 1, 3))


def test_restore_day_returns_single_excluded_day_to_available_dates():
    period = _period([DateExclusion(start_date=date(2026, 1, 3))])

    restore_day(period, date(2026, 1, 3))

    assert period.is_date_valid(date(2026, 1, 3))
    assert period.exclusions == []


def test_restore_day_splits_range_exclusion_around_restored_day():
    period = _period([
        DateExclusion(
            start_date=date(2026, 1, 2),
            end_date=date(2026, 1, 4),
        )
    ])

    restore_day(period, date(2026, 1, 3))

    assert not period.is_date_valid(date(2026, 1, 2))
    assert period.is_date_valid(date(2026, 1, 3))
    assert not period.is_date_valid(date(2026, 1, 4))
    assert period.exclusions == [
        DateExclusion(start_date=date(2026, 1, 2)),
        DateExclusion(start_date=date(2026, 1, 4)),
    ]


def test_exclude_or_restore_rejects_days_outside_period():
    period = _period()

    with pytest.raises(ValueError, match="outside the selected exam period"):
        exclude_day(period, date(2025, 12, 31))

    with pytest.raises(ValueError, match="outside the selected exam period"):
        restore_day(period, date(2026, 1, 6))


def test_format_exam_periods_writes_current_exclusion_state():
    period = _period([
        DateExclusion(start_date=date(2026, 1, 2)),
        DateExclusion(start_date=date(2026, 1, 4), end_date=date(2026, 1, 5)),
    ])

    assert format_exam_periods([period]) == (
        "$$$$\n"
        "FALL,Aleph\n"
        "01-01-2026, 05-01-2026\n"
        "- 02-01-2026\n"
        "- 04-01-2026, 05-01-2026\n"
    )
