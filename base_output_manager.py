from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional
from models import ScheduledExam, Semester, Term


class BaseOutputManager(ABC):
    """
    Abstract Base Class for all schedule exporters.
    """

    def __init__(self, base_directory: str = "outputs", filename: str = "master_schedule"):
        # Remove .txt if the user accidentally provided it in the filename
        clean_filename = filename.replace(".txt", "").replace(".pdf", "")
        self.base_directory = Path(base_directory).resolve()
        self.filename = clean_filename

    def _ensure_dir_exists(self):
        self.base_directory.mkdir(parents=True, exist_ok=True)

    def format_exam_line(self, exam: ScheduledExam) -> str:
        return f"{exam.course_name} | {exam.exam_date} | {exam.instructor}"

    @abstractmethod
    def get_full_path(self) -> Path:
        """Should return the full path including the correct extension."""
        pass

    @abstractmethod
    def export(self, structured_data: Optional[Dict[Semester, Dict[Term, List[ScheduledExam]]]]) -> str:
        pass