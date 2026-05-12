import unittest
import os
from datetime import date
from models import ScheduledExam, Semester, Term
from output_manager import TextOutputManager

class TestOutputManager(unittest.TestCase):
    def setUp(self):
        self.test_file = "test_output.txt"
        self.manager = TextOutputManager(self.test_file)

    def tearDown(self):
        """Clean up the generated test file after each test."""
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_standard_export(self):
        """Verify standard formatting for multiple entries."""
        data = {
            Semester.FALL: {
                Term.ALEPH: [
                    ScheduledExam("Logic", 101, Semester.FALL, Term.ALEPH, date(2026, 1, 1), "Dr. Smith")
                ]
            }
        }
        self.manager.export(data)
        with open(self.test_file, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("Logic | 2026-01-01 | Dr. Smith", content)

    def test_empty_data_export(self):
        """Edge Case: Verify that empty data produces only the header."""
        self.manager.export({})
        with open(self.test_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Should only contain header and some decoration
            self.assertTrue(len(lines) < 10)
            self.assertIn("OFFICIAL EXAM SCHEDULE", lines[0])

    def test_utf8_and_special_chars(self):
        """Edge Case: Verify support for UTF-8 characters (e.g., Hebrew or symbols)."""
        data = {
            Semester.SPRING: {
                Term.BET: [
                    ScheduledExam("מבני נתונים", 202, Semester.SPRING, Term.BET, date(2026, 7, 5), "פרופ' כהן")
                ]
            }
        }
        self.manager.export(data)
        with open(self.test_file, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("מבני נתונים | 2026-07-05 | פרופ' כהן", content)

    def test_missing_term_levels(self):
        """Edge Case: Verify that a semester with no exams is handled without crash."""
        data = { Semester.SUMMER: {} }
        self.manager.export(data)
        with open(self.test_file, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("SUMMER", content)

if __name__ == '__main__':
    unittest.main()