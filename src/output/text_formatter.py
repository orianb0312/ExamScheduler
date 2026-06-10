from typing import Dict, List, Optional
from src.output.output_models import ScheduledExam, Semester, Term
from src.output.i_output_formatter import IOutputFormatter


class TextFormatter(IOutputFormatter):
    """
    Plain text formatter for the university master schedule file.
    """

    def get_extension(self) -> str:
        """Returns the standard text file extension."""
        return ".txt"

    def format(self, structured_data: Optional[Dict[Semester, Dict[Term, List[ScheduledExam]]]]) -> str:
        """Formats the schedule dictionary into a structured plain text string."""
        lines = ["OFFICIAL UNIVERSITY MASTER EXAM SCHEDULE", "=" * 65, ""]

        if not structured_data:
            lines.append("EMPTY SCHEDULE: No exams have been scheduled yet.")
            return "\n".join(lines)

        for semester, terms in structured_data.items():
            lines.append(f"=== SEMESTER: {semester.value} ===")

            if not terms:
                lines.append("  No exam terms defined for this semester")
            else:
                for term, exams in terms.items():
                    lines.append(f"\n  [TERM: {term.value}]")
                    lines.append("  " + "-" * 40)
                    for exam in exams:
                        lines.append(f"  {exam.course_name} | {exam.exam_date} | {exam.instructor}")

            # Keep semesters visually separated in the text file.
            lines.append("\n" + "*" * 70 + "\n")

        return "\n".join(lines)
