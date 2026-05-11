import unittest
from datetime import date
from src.core.models import ScheduledExam, Semester, Term
from src.logic.schedule_sorter import ScheduleSorter


class TestScheduleSorter(unittest.TestCase):
    def setUp(self):
        self.sorter = ScheduleSorter()

        # Mock data for testing groupings and sorting
        self.raw_exams = [
            ScheduledExam("Data Structures", 101, Semester.SPRING, Term.BET, date(2026, 7, 10)),
            ScheduledExam("Calculus A", 102, Semester.FALL, Term.ALEPH, date(2026, 1, 15)),
            ScheduledExam("Logic", 103, Semester.FALL, Term.BET, date(2026, 2, 20)),
            ScheduledExam("Physics 1", 104, Semester.FALL, Term.ALEPH, date(2026, 1, 5)),
            # Additional cases for Semester/Term coverage
            ScheduledExam("Web Apps", 105, Semester.SUMMER, Term.ALEPH, date(2026, 9, 1)),
            ScheduledExam("Algorithms", 106, Semester.SPRING, Term.GIMEL, date(2026, 8, 20)),
            # Case for secondary sorting (same date as Calculus A)
            ScheduledExam("Database", 107, Semester.FALL, Term.ALEPH, date(2026, 1, 15))
        ]

    def test_grouping_by_semester(self):
        """Verify grouping includes FALL, SPRING, and SUMMER semesters."""
        result = self.sorter.categorize(self.raw_exams)
        self.assertIn(Semester.FALL, result)
        self.assertIn(Semester.SPRING, result)
        self.assertIn(Semester.SUMMER, result)

    def test_grouping_by_term(self):
        """Verify grouping includes ALEPH, BET, and GIMEL terms."""
        result = self.sorter.categorize(self.raw_exams)
        self.assertIn(Term.ALEPH, result[Semester.FALL])
        self.assertIn(Term.BET, result[Semester.FALL])
        self.assertIn(Term.GIMEL, result[Semester.SPRING])

    def test_chronological_order_and_tie_break(self):
        """Verify chronological order and alphabetical tie-breaker for same-day exams."""
        result = self.sorter.categorize(self.raw_exams)
        fall_aleph = result[Semester.FALL][Term.ALEPH]

        # 1. Earliest date (Jan 5)
        self.assertEqual(fall_aleph[0].course_name, "Physics 1")
        # 2. Same date (Jan 15), sorted alphabetically: Calculus A before Database
        self.assertEqual(fall_aleph[1].course_name, "Calculus A")
        self.assertEqual(fall_aleph[2].course_name, "Database")

    def test_empty_list_handling(self):
        """Edge case: Verify that an empty input list returns an empty dict."""
        result = self.sorter.categorize([])
        self.assertEqual(result, {})

    def test_single_exam_entry(self):
        """Edge case: Verify that a single exam is correctly categorized in the hierarchy."""
        single = [ScheduledExam("Bio-Informatics", 999, Semester.FALL, Term.ALEPH, date(2026, 1, 1))]
        result = self.sorter.categorize(single)
        self.assertEqual(len(result[Semester.FALL][Term.ALEPH]), 1)
        self.assertEqual(result[Semester.FALL][Term.ALEPH][0].course_name, "Bio-Informatics")


if __name__ == '__main__':
    unittest.main()