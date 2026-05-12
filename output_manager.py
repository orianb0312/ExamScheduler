import os
from typing import Dict, List
from models import ScheduledExam, Semester, Term


class TextOutputManager:
    """
    Handles the generation of a human-readable text file from structured exam data.
    Ensures compliance with formatting requirements (Name | Date | Instructor).
    """

    def __init__(self, file_path: str):
        self.file_path = file_path

    def format_exam_line(self, exam: ScheduledExam) -> str:
        """Formats a single exam into the mandatory string format."""
        return f"{exam.course_name} | {exam.exam_date} | {exam.instructor}"

    def export(self, structured_data: Dict[Semester, Dict[Term, List[ScheduledExam]]]) -> None:
        """
        Generates the compliant text file.
        Uses UTF-8 encoding to support international characters.
        """
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                # Header Section
                f.write("OFFICIAL EXAM SCHEDULE\n")
                f.write("=" * 25 + "\n\n")

                if not structured_data:
                    f.write("No exams scheduled.\n")
                    return

                # Hierarchical Traversal
                for semester, terms in structured_data.items():
                    f.write(f"=== SEMESTER: {semester.value} ===\n")

                    if not terms:
                        f.write("  (No terms defined for this semester)\n")

                    for term, exams in terms.items():
                        f.write(f"\n  [Term: {term.value}]\n")
                        f.write("  " + "-" * 15 + "\n")

                        for exam in exams:
                            line = self.format_exam_line(exam)
                            f.write(f"  {line}\n")

                    f.write("\n" + "*" * 40 + "\n\n")

           # print(f"File successfully produced: {os.path.abspath(self.file_path)}")

        except IOError as e:
            print(f"Error: Could not write to file. {e}")