import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional
from output_models import ScheduledExam, Semester, Term


class BaseOutputManager(ABC):
    """
    Abstract Base Class that loads settings from JSON.
    Provides shared logic for directory management and formatting.
    """

    def __init__(self, config_path: str = "config.json"):
        self._load_config(config_path)

    def _load_config(self, config_path: str):
        """Loads directory and filename settings from the JSON config."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                settings = config.get("output_settings", {})

                self.base_directory = Path(settings.get("base_directory", "outputs")).resolve()
                # Clean filename from any accidental extensions
                raw_filename = settings.get("master_filename", "master_schedule")
                self.filename = raw_filename.replace(".txt", "").replace(".json", "")
        except (FileNotFoundError, json.JSONDecodeError):
            # Fallback to defaults if config is missing or broken
            self.base_directory = Path("outputs").resolve()
            self.filename = "master_schedule"

    def _ensure_dir_exists(self):
        self.base_directory.mkdir(parents=True, exist_ok=True)

    def format_exam_line(self, exam: ScheduledExam) -> str:
        return f"{exam.course_name} | {exam.exam_date} | {exam.instructor}"

    @abstractmethod
    def get_full_path(self) -> Path:
        """Must return the path with the specific subclass extension."""
        pass

    @abstractmethod
    def export(self, structured_data: Optional[Dict[Semester, Dict[Term, List[ScheduledExam]]]]) -> str:
        """Main export logic to be implemented by subclasses."""
        pass