from dataclasses import dataclass
from datetime import date
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

    def __post_init__(self):
        """
        Input validation logic can be added here if needed in the future.
        """
        pass
