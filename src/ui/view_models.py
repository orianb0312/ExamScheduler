"""View models for the standalone desktop UI.

"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class ExclusionViewModel:
    """A single excluded date or range, ready for display."""

    start_date: date
    end_date: date | None


@dataclass(frozen=True)
class ExamPeriodViewModel:
    """Flat, UI-facing representation of a single ExamPeriod."""

    semester_label: str
    term_label: str
    start_date: date
    end_date: date
    exclusions: tuple[ExclusionViewModel, ...] = field(default_factory=tuple)

    def is_date_in_period(self, d: date) -> bool:
        """Return True if the date falls within the period boundaries."""
        return self.start_date <= d <= self.end_date

    def is_date_excluded(self, d: date) -> bool:
        """Return True if the date is covered by any exclusion."""
        for exclusion in self.exclusions:
            if exclusion.end_date is not None:
                if exclusion.start_date <= d <= exclusion.end_date:
                    return True
            elif exclusion.start_date == d:
                return True
        return False