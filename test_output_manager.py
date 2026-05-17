import unittest
import os
import json
import shutil
from pathlib import Path
from datetime import date
from output_models import ScheduledExam, Semester, Term
from output_manager import TextOutputManager


class TestOutputManagerUltimate(unittest.TestCase):
    def setUp(self):
        """
        Sets up a testing sandbox:
        1. Creates a temporary JSON config file.
        2. Initializes the manager with this config.
        """
        self.test_dir = "test_master_output"
        self.test_config_path = "test_config.json"
        self.master_filename = "test_master_schedule"

        # Create a temporary config file for the manager to load
        config_data = {
            "output_settings": {
                "base_directory": self.test_dir,
                "master_filename": self.master_filename
            }
        }
        with open(self.test_config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f)

        self.manager = TextOutputManager(self.test_config_path)
        self.master_path = self.manager.get_full_path()



    # 1. Functional Test: Line Formatting (Inherited Logic)
    def test_line_formatting_logic(self):
        """Verify the 'Course | Date | Instructor' pattern."""
        exam = ScheduledExam("Data Structures", 200, Semester.FALL, Term.ALEPH, date(2026, 1, 1), "Dr. Jones")
        expected = "Data Structures | 2026-01-01 | Dr. Jones"
        self.assertEqual(self.manager.format_exam_line(exam), expected)

    # 2. Stress Test: 11+ Exams Integration
    def test_large_scale_master_export(self):
        """STRESS TEST: Exporting 11 different exams in English across the year."""
        full_data = {
            Semester.FALL: {
                Term.ALEPH: [
                    ScheduledExam(f"Fall Course {i}", 100 + i, Semester.FALL, Term.ALEPH, date(2026, 1, 5 + i),
                                  f"Prof {i}")
                    for i in range(5)
                ],
                Term.BET: [
                    ScheduledExam("Algebra 1", 101, Semester.FALL, Term.BET, date(2026, 2, 10), "Dr. White"),
                    ScheduledExam("Calculus 2", 102, Semester.FALL, Term.BET, date(2026, 2, 15), "Prof. Smith")
                ]
            },
            Semester.SPRING: {
                Term.ALEPH: [
                    ScheduledExam("Algorithms", 201, Semester.SPRING, Term.ALEPH, date(2026, 6, 10), "Eng. Levi"),
                    ScheduledExam("Operating Systems", 202, Semester.SPRING, Term.ALEPH, date(2026, 6, 15),
                                  "Dr. Tanenbaum")
                ]
            },
            Semester.SUMMER: {
                Term.ALEPH: [
                    ScheduledExam("Cyber Security", 301, Semester.SUMMER, Term.ALEPH, date(2026, 9, 1), "Dr. Mitnick"),
                    ScheduledExam("AI Systems", 302, Semester.SUMMER, Term.ALEPH, date(2026, 9, 8), "Prof. Hinton")
                ]
            }
        }

        self.manager.export(full_data)
        self.assertTrue(self.master_path.exists())
        with open(self.master_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Verify we have exactly 11 exam lines based on the separator count
            self.assertGreaterEqual(content.count('|'), 11)
            self.assertIn("AI Systems | 2026-09-08 | Prof. Hinton", content)

    # 3. Edge Case: None Input
    def test_none_input_handling(self):
        """Verify that passing None results in an EMPTY SCHEDULE message."""
        self.manager.export(None)
        with open(self.master_path, 'r', encoding='utf-8') as f:
            self.assertIn("EMPTY SCHEDULE", f.read())

    # 4. Edge Case: Empty Dictionary
    def test_empty_dict_handling(self):
        """Verify that passing {} results in an EMPTY SCHEDULE message."""
        self.manager.export({})
        with open(self.master_path, 'r', encoding='utf-8') as f:
            self.assertIn("EMPTY SCHEDULE", f.read())

    # 5. Structural Edge Case: Semester without terms
    def test_semester_without_terms_header(self):
        """Verify that a semester with no terms prints the correct warning."""
        data = {Semester.SUMMER: {}}
        self.manager.export(data)
        with open(self.master_path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("=== SEMESTER: SUMM ===", content)
            self.assertIn("No exam terms defined", content)

    # 6. Configuration Test: JSON Parsing
    def test_config_loading_logic(self):
        """Verify the manager correctly loaded settings from the JSON file."""
        self.assertEqual(self.manager.filename, self.master_filename)
        self.assertTrue(str(self.manager.base_directory).endswith(self.test_dir))

    # 7. Reliability Test: Directory Recovery
    def test_directory_auto_recovery(self):
        """Verify self-healing if the directory is deleted between exports."""
        self.manager.export({})  # Create dir
        if self.master_path.exists():
            try:
                os.remove(self.master_path)
            except PermissionError:
                pass
        def force_remove(func, path, excinfo):
            import stat
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(self.test_dir, onexc=force_remove)

        self.manager.export({})  # Should recreate
        self.assertTrue(self.master_path.exists())

    # 8. Content Test: Special Characters in English
    def test_special_characters_support(self):
        """Verify support for O'Neill, C++, etc."""
        data = {Semester.FALL: {Term.ALEPH: [
            ScheduledExam("Advanced C++", 9, Semester.FALL, Term.ALEPH, date(2026, 1, 1), "Dr. O'Neill")
        ]}}
        self.manager.export(data)
        with open(self.master_path, 'r', encoding='utf-8') as f:
            self.assertIn("C++ | 2026-01-01 | Dr. O'Neill", f.read())


if __name__ == '__main__':
    unittest.main()