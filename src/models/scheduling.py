"""Scheduling-period domain objects and exam-date validation helpers."""

from datetime import date
from dataclasses import dataclass, field
from typing import List, Optional

from src.models.academic import Course
from src.models.enums import Semester, Term


@dataclass
class DateExclusion:
    """Single date or date range where exams cannot be scheduled."""

    start_date: date
    end_date: Optional[date] = None

    def is_date_excluded(self, check_date: date):
        """Return True when the date falls inside this blocked range."""
        if self.end_date:
            return self.start_date <= check_date <= self.end_date

        return self.start_date == check_date


@dataclass
class ExamPeriod:
    """Available exam window for one semester and term from the dates file."""

    semester: Semester
    term: Term
    start_date: date
    end_date: date
    exclusions: List[DateExclusion] = field(default_factory=list)

    def add_exclusion(self, exclusion: DateExclusion) -> None:
        """Adds an excluded date or date range to the period."""
        self.exclusions.append(exclusion)

    def is_date_valid(self, check_date: date) -> bool:
        """
        Validates if a given date is strictly within the exam period bounds
        and is not blocked by any exclusions (Holidays/Saturdays).
        """
        if not (self.start_date <= check_date <= self.end_date):
            return False

        for exclusion in self.exclusions:
            if exclusion.is_date_excluded(check_date):
                return False

        return True


def filter_exam_courses(courses: List[Course]) -> List[Course]:
    """Return only courses whose evaluation strategy requires exam scheduling."""
    return [course for course in courses if course.needs_exam_slot()]
