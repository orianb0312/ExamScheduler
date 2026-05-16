from dataclasses import dataclass
from datetime import date
from enum import Enum

class Semester(Enum):
    FALL = "FALL"
    SPRING = "SPRI"  # Adjusted from SPRING to SPRI to match source enums
    SUMMER = "SUMM"  # Adjusted from SUMMER to SUMM

class Term(Enum):
    ALEPH = "Aleph"  # Adjusted from ALEPH to Aleph
    BET = "Bet"      # Adjusted from BET to Bet
    GIMEL = "Gimel"  # Adjusted from GIMEL to Gimel

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