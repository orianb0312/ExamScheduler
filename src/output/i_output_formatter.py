from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from src.output.output_models import ScheduledExam, Semester, Term


class IOutputFormatter(ABC):
    """
    Strategy Interface for formatting output data.
    Defines the contract for all concrete formatters (e.g., TextFormatter, JsonFormatter).
    """

    @abstractmethod
    def format(self, structured_data: Optional[Dict[Semester, Dict[Term, List[ScheduledExam]]]]) -> str:
        """
        Transforms structured schedule data into a formatted string.

        Args:
            structured_data: A nested dictionary containing the scheduled exams
                             grouped by semester and term.

        Returns:
            str: The fully formatted string ready to be written to a file.
        """
        pass

    @abstractmethod
    def get_extension(self) -> str:
        """
        Returns the specific file extension for this format.

        Returns:
            str: The file extension (e.g., '.txt', '.json').
        """
        pass