import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
# Explicitly importing models for Type Hinting and Enum value access
from models import ScheduledExam, Semester, Term


class TextOutputManager:
    """
    Handles the formatting and physical export of exam schedules to text files.
    Features:
    - Automatic directory management (self-healing).
    - Unique timestamped filenames.
    - Type-safe data traversal.
    """

    def __init__(self, base_directory: str = "outputs"):
        """
        Initializes the manager with a target directory.
        Converts the path to an absolute path to avoid environment confusion.
        """
        self.base_directory = Path(base_directory).resolve()

    def _ensure_dir_exists(self):
        """Creates the base directory if it doesn't exist or was deleted."""
        self.base_directory.mkdir(parents=True, exist_ok=True)

    def _get_unique_filename(self, prefix: str) -> str:
        """Generates a unique filename using microsecond-precision timestamps."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return f"{prefix}_{timestamp}.txt"

    def format_exam_line(self, exam: ScheduledExam) -> str:
        """Formats a single exam object into the mandatory pattern."""
        return f"{exam.course_name} | {exam.exam_date} | {exam.instructor}"

    def export(self,
               structured_data: Optional[Dict[Semester, Dict[Term, List[ScheduledExam]]]],
               custom_name: Optional[str] = None) -> str:
        """
        Traverses the hierarchical data and writes it to a compliant text file.
        Returns the absolute path of the created file as a string.
        """
        # Ensure the output environment is ready before any file operation
        self._ensure_dir_exists()

        # Determine the filename (Custom or Auto-generated)
        filename = custom_name if custom_name else self._get_unique_filename("ExamSchedule")
        full_path = self.base_directory / filename

        try:
            # Using UTF-8 to ensure Hebrew/Special characters are preserved
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write("OFFICIAL UNIVERSITY EXAM SCHEDULE\n")
                f.write("=" * 45 + "\n\n")

                if not structured_data:
                    f.write("NOTIFICATION: No exam data was provided for this export.\n")
                else:
                    # Traversal using Semester and Term keys
                    for semester, terms in structured_data.items():
                        # Explicitly accessing .value from the Semester Enum
                        f.write(f"=== SEMESTER: {semester.value} ===\n")

                        if not terms:
                            f.write("  (No terms found for this semester)\n")

                        for term, exams in terms.items():
                            # Explicitly accessing .value from the Term Enum
                            f.write(f"\n  [TERM: {term.value}]\n")
                            f.write("  " + "-" * 30 + "\n")

                            for exam in exams:
                                # Delegate line formatting to the specialized helper
                                f.write(f"  {self.format_exam_line(exam)}\n")

                        f.write("\n" + "*" * 55 + "\n\n")

            return str(full_path)

        except Exception as e:
            # Catching and reporting system-level I/O errors
            print(f"CRITICAL FILE SYSTEM ERROR: {e}")
            return ""