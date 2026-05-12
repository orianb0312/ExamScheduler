import unittest
import os
import shutil
from pathlib import Path
from datetime import date
from models import ScheduledExam, Semester, Term
from output_manager import TextOutputManager


class TestOutputManagerUltimate(unittest.TestCase):
    def setUp(self):
        """Sets up a dedicated test directory to keep production data safe."""
        self.test_dir = "test_master_output"
        self.master_name = "test_master_schedule.txt"
        self.manager = TextOutputManager(self.test_dir, self.master_name)
        self.master_path = Path(self.test_dir).resolve() / self.master_name

    def tearDown(self):
        """
        CLEANUP DISABLED BY DEFAULT:
        Comment out the code below to automatically delete test files.
        Keeping it active allows manual inspection of the 11-exam file.
        """
        # if self.master_path.parent.exists():
        #     shutil.rmtree(self.master_path.parent)
        pass

    # 1. Functional: Formatting logic
    def test_single_line_formatting(self):
        """Verify the exact string pattern for a single exam."""
        exam = ScheduledExam("TDD Basics", 100, Semester.FALL, Term.ALEPH, date(2026, 1, 1), "Dr. Tester")
        expected = "TDD Basics | 2026-01-01 | Dr. Tester"
        self.assertEqual(self.manager.format_exam_line(exam), expected)

    # 2. STRESS TEST: Large scale data (11 exams)
    def test_large_scale_master_export(self):
        """
        Verify that a full schedule with 11 entries is correctly rendered in English.
        Covers multiple semesters and terms.
        """
        full_academic_year = {
            Semester.FALL: {
                Term.ALEPH: [
                    ScheduledExam("Calculus 1", 101, Semester.FALL, Term.ALEPH, date(2026, 1, 5), "Prof. Smith"),
                    ScheduledExam("Digital Logic", 102, Semester.FALL, Term.ALEPH, date(2026, 1, 12), "Dr. White"),
                    ScheduledExam("Physics 1", 103, Semester.FALL, Term.ALEPH, date(2026, 1, 18), "Eng. Brown")
                ],
                Term.BET: [
                    ScheduledExam("Calculus 1", 101, Semester.FALL, Term.BET, date(2026, 2, 10), "Prof. Smith"),
                    ScheduledExam("Digital Logic", 102, Semester.FALL, Term.BET, date(2026, 2, 15), "Dr. White")
                ]
            },
            Semester.SPRING: {
                Term.ALEPH: [
                    ScheduledExam("Algorithms", 201, Semester.SPRING, Term.ALEPH, date(2026, 6, 10), "Dr. Levi"),
                    ScheduledExam("Operating Systems", 202, Semester.SPRING, Term.ALEPH, date(2026, 6, 17),
                                  "Prof. Tanenbaum"),
                    ScheduledExam("Computer Architecture", 203, Semester.SPRING, Term.ALEPH, date(2026, 6, 24),
                                  "Eng. Morris"),
                    ScheduledExam("Data Structures", 204, Semester.SPRING, Term.ALEPH, date(2026, 6, 28), "Prof. Avner")
                ],
                Term.BET: [
                    ScheduledExam("Algorithms", 201, Semester.SPRING, Term.BET, date(2026, 7, 20), "Dr. Levi")
                ]
            },
            Semester.SUMMER: {
                Term.ALEPH: [
                    ScheduledExam("Cyber Security", 301, Semester.SUMMER, Term.ALEPH, date(2026, 9, 1), "Dr. Mitnick"),
                    ScheduledExam("Web Development", 302, Semester.SUMMER, Term.ALEPH, date(2026, 9, 8),
                                  "Prof. Berners-Lee")
                ]
            }
        }

        path = self.manager.export(full_academic_year)

        self.assertTrue(os.path.exists(path))
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertGreaterEqual(content.count('|'), 11)
            self.assertIn("Data Structures | 2026-06-28 | Prof. Avner", content)
            self.assertIn("=== SEMESTER: SUMMER ===", content)

    # 3. Edge Case: None Input
    def test_none_input_handling(self):
        """Verify that passing None shows EMPTY SCHEDULE."""
        self.manager.export(None)
        with open(self.master_path, 'r', encoding='utf-8') as f:
            self.assertIn("EMPTY SCHEDULE", f.read())

    # 4. Edge Case: Empty Dictionary
    def test_empty_dict_handling(self):
        """Verify that passing {} shows EMPTY SCHEDULE."""
        self.manager.export({})
        with open(self.master_path, 'r', encoding='utf-8') as f:
            self.assertIn("EMPTY SCHEDULE", f.read())

    # 5. Structural Edge Case: Semester with no terms
    def test_semester_without_terms_header(self):
        """Verify the 'No exam terms' message appears correctly."""
        data = {Semester.SUMMER: {}}
        self.manager.export(data)
        with open(self.master_path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("=== SEMESTER: SUMMER ===", content)
            self.assertIn("No exam terms defined", content)

    # 6. Encoding Test: Special characters
    def test_unicode_support(self):
        """Verify support for special characters in English names."""
        data = {Semester.FALL: {Term.ALEPH: [
            ScheduledExam("Advanced C++ & AI-Logic", 9, Semester.FALL, Term.ALEPH, date(2026, 1, 1), "Dr. O'Neill")]}}
        self.manager.export(data)
        with open(self.master_path, 'r', encoding='utf-8') as f:
            self.assertIn("Dr. O'Neill", f.read())

    # 7. Extreme Case: Directory Recovery
    def test_directory_auto_recovery(self):
        """Verify manager recreates the folder if deleted mid-session."""
        self.manager.export({})
        if self.test_dir:
            shutil.rmtree(self.test_dir)
        self.manager.export({})
        self.assertTrue(self.master_path.exists())


if __name__ == '__main__':
    unittest.main()