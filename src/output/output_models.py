from dataclasses import dataclass
from datetime import date, time
from typing import Optional
from src.models.enums import Semester, Term


@dataclass
class ScheduledExam:
    """A single exam placement after scheduling."""
    course_name: str
    course_id: int
    semester: Semester
    term: Term
    exam_date: date
    # Some older tests build exams without an instructor, so keep a safe default.
    instructor: str = "TBD"
    # New optional fields for V4 extension to support specific hours without breaking backward compatibility
    start_time: Optional[time] = None
    end_time: Optional[time] = None

    def __post_init__(self):
        """
        Input validation logic can be added here if needed in the future.
        """
        pass
