"""View models used by the desktop calendar widgets."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class ExclusionViewModel:
    start_date: date
    end_date: date | None


@dataclass(frozen=True)
class ExamPeriodViewModel:
    semester_label: str
    term_label: str
    start_date: date
    end_date: date
    exclusions: tuple[ExclusionViewModel, ...] = field(default_factory=tuple)

    def is_date_in_period(self, current_date: date) -> bool:
        return self.start_date <= current_date <= self.end_date

    def is_date_excluded(self, current_date: date) -> bool:
        for exclusion in self.exclusions:
            if exclusion.end_date is None:
                if current_date == exclusion.start_date:
                    return True
                continue

            if exclusion.start_date <= current_date <= exclusion.end_date:
                return True

        return False
