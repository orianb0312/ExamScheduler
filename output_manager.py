from typing import Dict, List
from models import ScheduledExam, Semester, Term


class TextOutputManager:
    """
    Handles the conversion of structured exam data into a readable text file.
    SRP: Responsible only for output formatting and file I/O.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path

    def format_exam_line(self, exam: ScheduledExam) -> str:
        """
        Formats a single exam entry into the mandatory string format.
        Format: Course Name | YYYY-MM-DD | Instructor
        """
        return f"{exam.course_name} | {exam.exam_date} | {exam.instructor}"

    def export(self, structured_data: Dict[Semester, Dict[Term, List[ScheduledExam]]]) -> None:
        """
        Writes the hierarchical schedule into the text file with clear separators.
        """
        with open(self.file_path, 'w', encoding='utf-8') as f:
            f.write("OFFICIAL EXAM SCHEDULE\n")
            f.write("======================\n\n")

            for semester, terms in structured_data.items():
                f.write(f"=== SEMESTER: {semester.value} ===\n")

                for term, exams in terms.items():
                    f.write(f"\n  --- Term: {term.value} ---\n")

                    for exam in exams:
                        line = self.format_exam_line(exam)
                        f.write(f"  {line}\n")

                f.write("\n" + "=" * 30 + "\n\n")

        print(f"Success: Schedule exported to {self.file_path}")