from enum import Enum

class Semester(Enum):
    FALL = "FALL"
    SPRING = "SPRI"
    SUMMER = "SUMM"

class Term(Enum):
    ALEPH = "Aleph"
    BET = "Bet"
    GIMEL = "Gimel"

class RequirementType(Enum):
    OBLIGATORY = "Obligatory"
    ELECTIVE = "Elective"