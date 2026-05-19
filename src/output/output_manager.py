import json
from pathlib import Path
from typing import Dict, List, Optional
from src.output.output_models import ScheduledExam, Semester, Term
from src.output.i_output_formatter import IOutputFormatter


class OutputManager:
    """
    Context class that manages file I/O operations.
    Delegates the actual string formatting to the injected IOutputFormatter strategy.
    Demonstrates Dependency Inversion (DIP) and Single Responsibility (SRP) principles.
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

                # Resolve absolute path for safety
                self.base_directory = Path(settings.get("base_directory", "outputs")).resolve()

                # Extract raw filename without extension to allow the formatter to append its own
                raw_filename = settings.get("master_filename", "master_schedule")
                self.filename = raw_filename.split('.')[0]
        except (FileNotFoundError, json.JSONDecodeError):
            # Fallback to default values if config is missing, broken, or unreadable
            self.base_directory = Path("outputs").resolve()
            self.filename = "master_schedule"

    def _ensure_dir_exists(self):
        """Creates the output directory path if it does not already exist."""
        self.base_directory.mkdir(parents=True, exist_ok=True)

    def get_full_path(self) -> Path:
        """Constructs the full absolute path, dynamically appending the formatter's extension."""
        return self.base_directory / f"{self.filename}{self.formatter.get_extension()}"

    def export(self, structured_data: Optional[Dict[Semester, Dict[Term, List[ScheduledExam]]]]) -> str:
        """
        Drives the export process: ensures directory exists, formats data, and writes to disk.

        Returns:
            str: The absolute path of the generated file.
        """
        self._ensure_dir_exists()
        full_path = self.get_full_path()

        # Dependency Inversion: Formatting logic is fully delegated to the injected strategy
        content = self.formatter.format(structured_data)

        # Write the formatted string to the file system using UTF-8 encoding
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return str(full_path)