from enum import Enum
from dataclasses import dataclass
from datetime import date
from typing import List, Dict

class Semester(Enum):
    FALL = "FALL"
    SPRING = "SPRING"
    SUMMER = "SUMMER"

class Term(Enum):
    ALEPH = "ALEPH"
    BET = "BET"
    GIMEL = "GIMEL"

@dataclass
class ScheduledExam:
    course_name: str
    course_id: int
    semester: Semester
    term: Term
    exam_date: date