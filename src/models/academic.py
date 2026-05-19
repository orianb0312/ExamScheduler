from dataclasses import dataclass, field
from typing import List
from abc import ABC, abstractmethod
from src.models.enums import Semester, RequirementType


# --- Evaluation Strategy Pattern ---

class Evaluation(ABC):
    """
    Abstract base class representing the course evaluation method.
    Filters courses that do not require physical exam scheduling.
    """

    @abstractmethod
    def requires_scheduling(self) -> bool:
        pass


class Exam(Evaluation):
    # Exam needs a slot in the exam timetable.
    def requires_scheduling(self) -> bool:
        return True


class Project(Evaluation):
    # No central exam hall date.
    def requires_scheduling(self) -> bool:
        return False


class Attendance(Evaluation):
    # Same as project, nothing to put on the grid.
    def requires_scheduling(self) -> bool:
        return False


# --- Academic Entities ---

@dataclass
class ProgramAffiliation:
    """
    Maps a course to a specific study program, including year and semester.
    A single course may have multiple affiliations.
    """
    program_id: int
    year: int
    semester: Semester
    requirement_type: RequirementType


@dataclass
class Course:
    # Represents an engineering faculty course.
    course_id: int  # 5-digit unique identifier
    name: str
    instructor: str
    evaluation: Evaluation
    affiliations: List[ProgramAffiliation] = field(default_factory=list)

    def __hash__(self):
        return hash(self.course_id)

    def __eq__(self, other):
        if not isinstance(other, Course):
            return False
        return self.course_id == other.course_id

    def add_affiliation(self, affiliation: ProgramAffiliation) -> None:
        # Appends a program affiliation to the course.
        self.affiliations.append(affiliation)
        

    def needs_exam_slot(self) -> bool:
        # Returns True only if the evaluation method requires an exam slot.
        return self.evaluation.requires_scheduling()