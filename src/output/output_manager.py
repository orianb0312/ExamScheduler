import json
from pathlib import Path
from typing import Dict, List, Optional
from src.output.output_models import ScheduledExam, Semester, Term
from src.output.i_output_formatter import IOutputFormatter
from src.output.text_formatter import TextFormatter


class OutputManager:
    """
    Writes formatted schedules to the output file configured for the project.
    """

    def __init__(self, formatter: IOutputFormatter, config_path: str = "config.json"):
        """
        Initializes the manager with a specific formatting strategy and configuration.
        """
        self.formatter = formatter
        self._load_config(config_path)

    def _load_config(self, config_path: str):
        """Loads output directory and filename settings from a JSON configuration file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                settings = config.get("output_settings", {})

                # Keep the output path absolute so tests and CLI runs agree.
                self.base_directory = Path(settings.get("base_directory", "outputs")).resolve()

                # Store the filename without extension; the formatter owns the suffix.
                raw_filename = settings.get("master_filename", "master_schedule")
                self.filename = raw_filename.split('.')[0]
        except (FileNotFoundError, json.JSONDecodeError):
            # Use the original defaults when config.json is missing or broken.
            self.base_directory = Path("outputs").resolve()
            self.filename = "master_schedule"

    def _ensure_dir_exists(self):
        """Creates the output directory path if it does not already exist."""
        self.base_directory.mkdir(parents=True, exist_ok=True)

    def get_full_path(self) -> Path:
        """Return the full output path with the formatter's extension."""
        return self.base_directory / f"{self.filename}{self.formatter.get_extension()}"

    def export(self, structured_data: Optional[Dict[Semester, Dict[Term, List[ScheduledExam]]]]) -> str:
        """
        Drives the export process: ensures directory exists, formats data, and writes to disk.

        Returns:
            str: The absolute path of the generated file.
        """
        self._ensure_dir_exists()
        full_path = self.get_full_path()

        content = self.formatter.format(structured_data)

        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return str(full_path)


class TextOutputManager(OutputManager):
    """
    Backward-compatible text output manager used by the schedulers and tests.
    """

    def __init__(self, config_path: str = "config.json"):
        super().__init__(TextFormatter(), config_path)

    def format_exam_line(self, exam: ScheduledExam) -> str:
        """Formats a single scheduled exam as a text output line."""
        return f"{exam.course_name} | {exam.exam_date} | {exam.instructor}"
