import unittest
from datetime import date
from src.output.output_models import ScheduledExam, Semester, Term
from schedule_sorter import ScheduleSorter


class TestScheduleSorter(unittest.TestCase):
    def setUp(self):
        """Initialize the sorter and standard test data."""
        self.sorter = ScheduleSorter()
        self.standard_exams = [
            ScheduledExam("Data Structures", 101, Semester.SPRING, Term.BET, date(2026, 7, 10)),
            ScheduledExam("Calculus A", 102, Semester.FALL, Term.ALEPH, date(2026, 1, 15)),
            ScheduledExam("Logic", 103, Semester.FALL, Term.BET, date(2026, 2, 20)),
            ScheduledExam("Physics 1", 104, Semester.FALL, Term.ALEPH, date(2026, 1, 5)),
            ScheduledExam("Web Apps", 105, Semester.SUMMER, Term.ALEPH, date(2026, 9, 1)),
            ScheduledExam("Algorithms", 106, Semester.SPRING, Term.GIMEL, date(2026, 8, 20)),
            ScheduledExam("Database", 107, Semester.FALL, Term.ALEPH, date(2026, 1, 15))
        ]

    # --- SECTION 1: Standard Functional Tests ---

    def test_grouping_logic(self):
        """Verify grouping by Semester and Term including Summer and Gimel."""
        result = self.sorter.categorize(self.standard_exams)
        self.assertIn(Semester.SUMMER, result)
        self.assertIn(Term.GIMEL, result[Semester.SPRING])

    def test_sorting_order(self):
        """Verify chronological order and alphabetical tie-breaker."""
        result = self.sorter.categorize(self.standard_exams)
        fall_aleph = result[Semester.FALL][Term.ALEPH]
        self.assertEqual(fall_aleph[0].course_name, "Physics 1")  # Jan 5
        self.assertEqual(fall_aleph[1].course_name, "Calculus A")  # Jan 15 (C before D)
        self.assertEqual(fall_aleph[2].course_name, "Database")

    def test_case_insensitive_sorting(self):
        """Verify that sorting ignores case (e.g., 'algorithms' should come before 'Calculus')."""
        case_test_data = [
            ScheduledExam("Calculus", 1, Semester.FALL, Term.ALEPH, date(2026, 1, 1)),
            ScheduledExam("algorithms", 2, Semester.FALL, Term.ALEPH, date(2026, 1, 1))
        ]
        result = self.sorter.categorize(case_test_data)
        fall_aleph = result[Semester.FALL][Term.ALEPH]

        # In case-sensitive sort, 'Calculus' (C) comes before 'algorithms' (a).
        # In our case-insensitive sort, 'algorithms' (a) comes before 'Calculus' (C).
        self.assertEqual(fall_aleph[0].course_name, "algorithms")
        self.assertEqual(fall_aleph[1].course_name, "Calculus")

    # --- SECTION 2: Extreme & Edge Case Tests ---

    def test_null_and_empty_inputs(self):
        """Verify handling of None and empty lists."""
        self.assertEqual(self.sorter.categorize(None), {})
        self.assertEqual(self.sorter.categorize([]), {})

    def test_invalid_data_values(self):
        """Verify handling of zero/negative IDs and empty strings."""
        extreme_data = [
            ScheduledExam("", 0, Semester.FALL, Term.ALEPH, date(2026, 1, 1)),
            ScheduledExam("Valid", -1, Semester.FALL, Term.ALEPH, date(2026, 1, 1))
        ]
        result = self.sorter.categorize(extreme_data)
        self.assertEqual(result[Semester.FALL][Term.ALEPH][0].course_name, "")

    def test_boundary_dates(self):
        """Verify handling of extreme dates (Year 1 and Year 9999)."""
        boundary_exams = [
            ScheduledExam("Future", 1, Semester.FALL, Term.ALEPH, date(9999, 12, 31)),
            ScheduledExam("Past", 2, Semester.FALL, Term.ALEPH, date(1, 1, 1))
        ]
        result = self.sorter.categorize(boundary_exams)
        self.assertEqual(result[Semester.FALL][Term.ALEPH][0].course_name, "Past")

    def test_duplicate_objects(self):
        """Verify that identical objects are preserved in the list."""
        exam = ScheduledExam("Logic", 103, Semester.FALL, Term.ALEPH, date(2026, 1, 1))
        result = self.sorter.categorize([exam, exam])
        self.assertEqual(len(result[Semester.FALL][Term.ALEPH]), 2)

    # --- SECTION 3: Performance Tests ---

    def test_large_input_scaling(self):
        """Verify performance with a large dataset (1000 items)."""
        large_list = [
            ScheduledExam(f"C{i}", i, Semester.FALL, Term.ALEPH, date(2026, 1, 1))
            for i in range(1000)
        ]
        result = self.sorter.categorize(large_list)
        self.assertEqual(len(result[Semester.FALL][Term.ALEPH]), 1000)


if __name__ == '__main__':
    unittest.main()
