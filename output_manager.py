import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
# Explicitly using models for Type Hinting
from models import ScheduledExam, Semester, Term


class TextOutputManager:
    """
    Handles the generation of the University Master Exam Schedule.
    Maintains a single consolidated text file as the source of truth.
    Adheres to SRP by focusing only on file I/O and formatting.
    """

    def __init__(self, base_directory: str = "outputs", filename: str = "master_schedule.txt"):
        """
        Initializes the manager with a fixed target file.
        Uses absolute paths to ensure reliability across environments.
        """
        self.base_directory = Path(base_directory).resolve()
        self.master_file_path = self.base_directory / filename

    def _ensure_dir_exists(self):
        """Self-healing: Creates the target directory if it is missing."""
        self.base_directory.mkdir(parents=True, exist_ok=True)

    def format_exam_line(self, exam: ScheduledExam) -> str:
        """Formats an exam object into the mandatory string: Name | Date | Instructor."""
        return f"{exam.course_name} | {exam.exam_date} | {exam.instructor}"

    def export(self, structured_data: Optional[Dict[Semester, Dict[Term, List[ScheduledExam]]]]) -> str:
        """
        Writes the hierarchical data to the master file.
        Overwrites existing content to maintain perfect sorting and order.
        """
        self._ensure_dir_exists()

        try:
            # Using 'w' to overwrite ensures the file is always perfectly sorted and clean
            with open(self.master_file_path, 'w', encoding='utf-8') as f:
                f.write("OFFICIAL UNIVERSITY MASTER EXAM SCHEDULE\n")
                f.write("=" * 60 + "\n\n")

                if not structured_data:
                    f.write("EMPTY SCHEDULE: No exams have been scheduled yet.\n")
                else:
                    for semester, terms in structured_data.items():
                        f.write(f"=== SEMESTER: {semester.value} ===\n")

                        if not terms:
                            f.write("  No exam terms defined for this semester\n")
                        else:
                            for term, exams in terms.items():
                                f.write(f"\n  [TERM: {term.value}]\n")
                                f.write("  " + "-" * 35 + "\n")

                                for exam in exams:
                                    f.write(f"  {self.format_exam_line(exam)}")

                                    f.write("\n" + "*" * 65 + "\n\n")

            return str(self.master_file_path)
        except Exception as e:
            print(f"CRITICAL EXPORT ERROR: {e}")
            return ""