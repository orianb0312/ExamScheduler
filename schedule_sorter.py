from collections import defaultdict
from typing import List, Dict
# Assuming models are imported from your existing structure
from src.core.models import ScheduledExam, Semester, Term

class ScheduleSorter:
    """
    Responsible for organizing exams into a mandatory hierarchical view.
    SOLID - SRP: This class has only one reason to change: changes in sorting/grouping logic.
    """

    def categorize(self, exams: List[ScheduledExam]) -> Dict[Semester, Dict[Term, List[ScheduledExam]]]:
        """
        Organizes a list of exams into a nested dictionary:
        Semester -> Term -> List[Exams]
        Exams are sorted primarily by date and secondarily by course name.
        """
        if not exams:
            return {}

        # Hierarchical structure: Semester -> Term -> List of Exams
        hierarchical_view = defaultdict(lambda: defaultdict(list))

        # Sort by date first, then by course_name as a secondary tie-breaker for same-day exams
        sorted_exams = sorted(exams, key=lambda x: (x.exam_date, x.course_name))

        for exam in sorted_exams:
            hierarchical_view[exam.semester][exam.term].append(exam)

        # Convert defaultdict back to standard dict for consistency
        return {sem: dict(terms) for sem, terms in hierarchical_view.items()}