from typing import Dict, List, Optional
from pathlib import Path
from output_models import ScheduledExam, Semester, Term
from base_output_manager import BaseOutputManager


class TextOutputManager(BaseOutputManager):
    """
    Concrete implementation for Plain Text (.txt) files using JSON config.
    """

    def get_full_path(self) -> Path:
        return self.base_directory / f"{self.filename}.txt"

    def export(self, structured_data: Optional[Dict[Semester, Dict[Term, List[ScheduledExam]]]]) -> str:
        self._ensure_dir_exists()
        full_path = self.get_full_path()

        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write("OFFICIAL UNIVERSITY MASTER EXAM SCHEDULE\n")
                f.write("=" * 65 + "\n\n")

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
                                f.write("  " + "-" * 40 + "\n")
                                for exam in exams:
                                    f.write(f"  {self.format_exam_line(exam)}\n")
                        f.write("\n" + "*" * 70 + "\n\n")

            return str(full_path)
        except Exception as e:
            print(f"EXPORT ERROR: {e}")
            return ""