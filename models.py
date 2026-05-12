from dataclasses import dataclass
from datetime import date
from enum import Enum

class Semester(Enum):
    """
    Represents the academic semesters in the Israeli university system.
    """
    FALL = "FALL"
    SPRING = "SPRING"
    SUMMER = "SUMMER"

class Term(Enum):
    """
    Represents the specific exam period (Moed).
    """
    ALEPH = "ALEPH"
    BET = "BET"
    GIMEL = "GIMEL"

@dataclass
class ScheduledExam:
    """
    Domain entity representing a specific exam placement.
    SOLID Principles: Encapsulates exam data without business logic.
    """
    course_name: str
    course_id: int
    semester: Semester
    term: Term
    exam_date: date
    # Default value "TBD" ensures compatibility with previous tests
    # and prevents TypeErrors when instructor is not provided.
    instructor: str = "TBD"

    def __post_init__(self):
        """
        Input validation logic can be added here if needed in the future.
        """
        pass