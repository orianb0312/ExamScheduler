import unittest
import os
import shutil
from pathlib import Path
from datetime import date
from models import ScheduledExam, Semester, Term
from output_manager import TextOutputManager

class TestOutputManagerEnhanced(unittest.TestCase):
    def setUp(self):
        self.test_dir_name = "temp_test_outputs"
        self.manager = TextOutputManager(self.test_dir_name)
        self.test_dir_path = Path(self.test_dir_name).resolve()

    def tearDown(self):
        """Cleanup: Wipe the test directory after each run."""
        if self.test_dir_path.exists():
            shutil.rmtree(self.test_dir_path)

    # 1. Functional Test: Line Format
    def test_line_formatting_logic(self):
        exam = ScheduledExam("Cyber Security", 500, Semester.FALL, Term.ALEPH, date(2026, 2, 1), "Dr. Alice")
        self.assertEqual(self.manager.format_exam_line(exam), "Cyber Security | 2026-02-01 | Dr. Alice")

    # 2. Functional Test: Hierarchy Rendering
    def test_hierarchy_output(self):
        data = {Semester.FALL: {Term.ALEPH: [ScheduledExam("Logic", 1, Semester.FALL, Term.ALEPH, date(2026, 1, 1))]}}
        path = self.manager.export(data, "hierarchy.txt")
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("=== SEMESTER: FALL ===", content)
            self.assertIn("[TERM: ALEPH]", content)

    # 3. BUG FIX TEST: Directory Auto-Recreation (The one that failed before)
    def test_directory_auto_recreation(self):
        self.manager.export({}) # Create it
        shutil.rmtree(self.test_dir_path) # Nuke it
        self.assertFalse(self.test_dir_path.exists())
        self.manager.export({}) # Action should trigger recreation
        self.assertTrue(self.test_dir_path.exists())

    # 4. Edge Case: None Input
    def test_none_input_safety(self):
        path = self.manager.export(None)
        with open(path, 'r') as f:
            self.assertIn("No exam data was provided", f.read())

    # 5. Edge Case: Empty Dictionary {}
    def test_empty_dict_safety(self):
        path = self.manager.export({})
        with open(path, 'r') as f:
            self.assertIn("No exam data was provided", f.read())

    # 6. Edge Case: UTF-8 Support
    def test_unicode_support(self):
        data = {Semester.SPRING: {Term.BET: [ScheduledExam("אלגוריתמים", 10, Semester.SPRING, Term.BET, date(2026, 7, 1), "פרופ' ישראלי")]}}
        path = self.manager.export(data)
        with open(path, 'r', encoding='utf-8') as f:
            self.assertIn("פרופ' ישראלי", f.read())

    # 7. Performance/Collision Case: Rapid Exports
    def test_filename_uniqueness(self):
        p1 = self.manager.export({})
        p2 = self.manager.export({})
        self.assertNotEqual(p1, p2, "Filenames collided despite microsecond timestamp.")

if __name__ == '__main__':
    unittest.main()