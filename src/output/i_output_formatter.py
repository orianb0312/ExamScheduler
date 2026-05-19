from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from src.output.output_models import ScheduledExam, Semester, Term


class IOutputFormatter(ABC):
    """Strategy Interface for formatting output data."""

    @abstractmethod
    def format(self, structured_data: Optional[Dict[Semester, Dict[Term, List[ScheduledExam]]]]) -> str:
        """Transforms structured schedule data into a formatted string."""
        pass

    @abstractmethod
    def get_extension(self) -> str:
        """Returns the specific file extension for this format (e.g., '.txt')."""
        pass