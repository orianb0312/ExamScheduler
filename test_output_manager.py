import unittest
import os
from datetime import date
from models import ScheduledExam, Semester, Term
from output_manager import TextOutputManager


class TestOutputManager(unittest.TestCase):
    def setUp(self):
        self.output_path = "test_schedule.txt"
        self.manager = TextOutputManager(self.output_path)

        # Sample structured data (normally provided by ScheduleSorter)
        self.structured_data = {
            Semester.FALL: {
                Term.ALEPH: [
                    ScheduledExam("Logic", 103, Semester.FALL, Term.ALEPH, date(2026, 1, 5), "Dr. Smith"),
                    ScheduledExam("Physics", 104, Semester.FALL, Term.ALEPH, date(2026, 1, 10), "Prof. Brown")
                ]
            }
        }

    def test_line_formatting(self):
        """Verify the specific string format: Course | Date | Instructor."""
        exam = self.standard_exam = ScheduledExam("OOP", 101, Semester.FALL, Term.ALEPH, date(2026, 2, 1), "Eng. Doe")
        formatted = self.manager.format_exam_line(exam)
        expected = "OOP | 2026-02-01 | Eng. Doe"
        self.assertEqual(formatted, expected)

    def test_file_creation_and_content(self):
        """Verify that the file is created and contains the hierarchical headers."""
        self.manager.export(self.structured_data)

        self.assertTrue(os.path.exists(self.output_path))

        with open(self.output_path, 'r') as f:
            content = f.read()
            self.assertIn("=== SEMESTER: FALL ===", content)
            self.assertIn("--- Term: ALEPH ---", content)
            self.assertIn("Logic | 2026-01-05 | Dr. Smith", content)

    def tearDown(self):
        """Clean up the test file after running."""
        if os.path.exists(self.output_path):
            os.remove(self.output_path)


if __name__ == '__main__':
    unittest.main()