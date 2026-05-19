from dataclasses import dataclass, field
from typing import List, Optional
from datetime import date
from src.models.enums import Semester, Term
from src.models.academic import Course


@dataclass
class DateExclusion:
    """
    Represents a single date or a range of dates where exams cannot be scheduled.
    Handles 'Excluded' records like Saturdays or holidays (e.g., Purim).
    """
    start_date: date
    end_date: Optional[date] = None

    def is_date_excluded(self, check_date: date):
        """
            Checks if a specific date falls within this exclusion period.
            Returns True if the date is blocked.
        """
        if self.end_date:
            return self.start_date <= check_date <= self.end_date

        return self.start_date == check_date


@dataclass
class ExamPeriod:
    """
        Represents the available window for scheduling exams for a specific semester and Moed.
        Corresponds to the 'Exam Period' file structure in the requirements.
    """
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
        # 1. Boundary Check
        if not (self.start_date <= check_date <= self.end_date):
            return False

        # 2. Exclusion Check (Crucial for satisfying Appendix A requirements)
        for exclusion in self.exclusions:
            if exclusion.is_date_excluded(check_date):
                return False

        return True


def filter_exam_courses(courses: List[Course]) -> List[Course]:
    """ Return only courses that require exam scheduling"""
    return [course for course in courses if course.needs_exam_slot()]