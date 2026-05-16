from collections import defaultdict
from typing import List, Dict, Optional
from output_models import ScheduledExam, Semester, Term

class ScheduleSorter:
    """
    Logic for organizing exams into a hierarchical view.
    SRP: Handles only the data transformation and sorting strategy.
    """

    def categorize(self, exams: Optional[List[ScheduledExam]]) -> Dict[Semester, Dict[Term, List[ScheduledExam]]]:
        """
        Groups exams by Semester -> Term and sorts them by date and name (Case-Insensitive).
        Handles None or empty inputs gracefully.
        """
        if exams is None or not exams:
            return {}

        hierarchical_view = defaultdict(lambda: defaultdict(list))

        # Primary sort: exam_date
        # Secondary sort: course_name.lower() to ensure Case-Insensitive alphabetical order
        sorted_exams = sorted(exams, key=lambda x: (x.exam_date, x.course_name.lower()))

        for exam in sorted_exams:
            hierarchical_view[exam.semester][exam.term].append(exam)

        return {sem: dict(terms) for sem, terms in hierarchical_view.items()}