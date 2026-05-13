import unittest
import os
import shutil
from pathlib import Path
from datetime import date
from models import ScheduledExam, Semester, Term
from output_manager import TextOutputManager

class TestOutputManagerUltimate(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_master_output"
        # We pass the name without extension to avoid double .txt.txt
        self.manager = TextOutputManager(self.test_dir, "test_master_schedule")
        # Ask the manager for the actual path it uses
        self.master_path = self.manager.get_full_path()

    def tearDown(self):
        if self.master_path.parent.exists():
            shutil.rmtree(self.master_path.parent)

    def test_large_scale_master_export(self):
        """STRESS TEST: 11 Exams across the year."""
        data = {
            Semester.FALL: {
                Term.ALEPH: [ScheduledExam(f"C{i}", i, Semester.FALL, Term.ALEPH, date(2026, 1, i+1), f"P{i}") for i in range(6)],
                Term.BET: [ScheduledExam(f"R{i}", i, Semester.FALL, Term.BET, date(2026, 2, i+1), f"P{i}") for i in range(2)]
            },
            Semester.SPRING: {
                Term.ALEPH: [ScheduledExam(f"S{i}", i, Semester.SPRING, Term.ALEPH, date(2026, 6, i+1), f"D{i}") for i in range(3)]
            }
        }
        self.manager.export(data)
        with open(self.master_path, 'r', encoding='utf-8') as f:
            self.assertGreaterEqual(f.read().count('|'), 11)

    def test_none_input_handling(self):
        self.manager.export(None)
        with open(self.master_path, 'r', encoding='utf-8') as f:
            self.assertIn("EMPTY SCHEDULE", f.read())

    def test_semester_without_terms_header(self):
        self.manager.export({Semester.SUMMER: {}})
        with open(self.master_path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("=== SEMESTER: SUMMER ===", content)
            self.assertIn("No exam terms defined", content)

    def test_directory_auto_recovery(self):
        self.manager.export({})
        shutil.rmtree(self.test_dir)
        self.manager.export({})
        self.assertTrue(self.master_path.exists())

    def test_line_formatting_logic(self):
        exam = ScheduledExam("Logic", 1, Semester.FALL, Term.ALEPH, date(2026, 1, 1), "Dr. X")
        self.assertEqual(self.manager.format_exam_line(exam), "Logic | 2026-01-01 | Dr. X")

if __name__ == '__main__':
    unittest.main()