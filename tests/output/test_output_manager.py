import unittest
import json
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

# Adjust imports according to your project structure
from src.output.output_manager import OutputManager
from src.output.text_formatter import TextFormatter
from src.output.i_output_formatter import IOutputFormatter


# --- Dummy Classes to simulate Enums and Data Models safely in tests ---
class DummySemester:
    def __init__(self, val): self.value = val


class DummyTerm:
    def __init__(self, val): self.value = val


class DummyExam:
    def __init__(self, course, date, instructor):
        self.course_name = course
        self.exam_date = date
        self.instructor = instructor


class TestTextFormatter(unittest.TestCase):
    """
    Test suite for TextFormatter (4 Tests).
    Validates text generation and edge cases for the new Strategy pattern.
    """

    def setUp(self):
        self.formatter = TextFormatter()

    def test_1_get_extension_returns_txt(self):
        """Test that the formatter enforces the correct .txt extension."""
        self.assertEqual(self.formatter.get_extension(), ".txt")

    def test_2_format_empty_or_none_schedule(self):
        """Edge Case: Formatting when the schedule is None or empty."""
        result_empty = self.formatter.format({})
        result_none = self.formatter.format(None)

        self.assertIn("EMPTY SCHEDULE: No exams have been scheduled yet.", result_empty)
        self.assertIn("EMPTY SCHEDULE", result_none)

    def test_3_format_semester_with_empty_terms(self):
        """Edge Case: Formatting a semester that has no scheduled terms."""
        sem = DummySemester("Semester A")
        dummy_data = {sem: {}}  # No terms inside

        result = self.formatter.format(dummy_data)
        self.assertIn("=== SEMESTER: Semester A ===", result)
        self.assertIn("No exam terms defined for this semester", result)

    def test_4_format_populated_schedule(self):
        """Test formatting a standard, fully populated schedule."""
        sem = DummySemester("A")
        term = DummyTerm("Moed A")
        exam = DummyExam("Data Structures", "2026-06-15", "Dr. Smith")

        dummy_data = {sem: {term: [exam]}}
        result = self.formatter.format(dummy_data)

        self.assertIn("OFFICIAL UNIVERSITY MASTER EXAM SCHEDULE", result)
        self.assertIn("=== SEMESTER: A ===", result)
        self.assertIn("[TERM: Moed A]", result)
        self.assertIn("Data Structures | 2026-06-15 | Dr. Smith", result)


class TestOutputManager(unittest.TestCase):
    """
    Test suite for OutputManager (4 Tests).
    Validates config loading, directory creation, and Dependency Inversion.
    """

    def setUp(self):
        # Create a mock formatter for Dependency Injection
        self.mock_formatter = MagicMock(spec=IOutputFormatter)
        self.mock_formatter.get_extension.return_value = ".out"
        self.mock_formatter.format.return_value = "MOCKED_TEXT"

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_5_fallback_to_defaults_on_missing_config(self, mock_file):
        """Edge Case: Manager should use default paths if config.json is missing."""
        manager = OutputManager(formatter=self.mock_formatter, config_path="missing.json")

        expected_dir = Path("outputs").resolve()
        self.assertEqual(manager.base_directory, expected_dir)
        self.assertEqual(manager.filename, "master_schedule")

        # Ensure the mock formatter's extension was appended
        expected_path = expected_dir / "master_schedule.out"
        self.assertEqual(manager.get_full_path(), expected_path)

    def test_6_load_valid_config_overrides_defaults(self):
        """Test that a valid config JSON updates the output paths correctly."""
        valid_json = json.dumps({
            "output_settings": {
                "base_directory": "custom_exports",
                "master_filename": "final_results.json"  # Manager should strip '.json'
            }
        })

        with patch("builtins.open", mock_open(read_data=valid_json)):
            manager = OutputManager(formatter=self.mock_formatter, config_path="dummy.json")

        expected_dir = Path("custom_exports").resolve()
        self.assertEqual(manager.base_directory, expected_dir)
        self.assertEqual(manager.filename, "final_results")  # Extension stripped
        self.assertEqual(manager.get_full_path(), expected_dir / "final_results.out")

    @patch("pathlib.Path.mkdir")
    @patch("builtins.open", mock_open())
    def test_7_export_creates_directory_if_missing(self, mock_mkdir):
        """Test that the export method ensures the target directory exists."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            manager = OutputManager(formatter=self.mock_formatter, config_path="missing.json")

        # Temporarily mock the open function again for the actual write process
        with patch("builtins.open", mock_open()):
            manager.export({})

        # Verify mkdir was called with correct parameters
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("pathlib.Path.mkdir")
    def test_8_export_delegates_to_formatter_and_writes(self, mock_mkdir):
        """
        Integration Test: Ensures OutputManager delegates formatting to the
        Strategy interface and writes the exact returned string to disk.
        """
        with patch("builtins.open", side_effect=FileNotFoundError):
            manager = OutputManager(formatter=self.mock_formatter, config_path="missing.json")

        m_open = mock_open()
        with patch("builtins.open", m_open):
            dummy_data = {"test": "data"}

            # Execute
            result_path = manager.export(dummy_data)

            # 1. Verify formatter was called (Delegation)
            self.mock_formatter.format.assert_called_once_with(dummy_data)

            # 2. Verify file was written with the formatter's exact output
            expected_path = Path("outputs").resolve() / "master_schedule.out"
            m_open.assert_called_once_with(expected_path, 'w', encoding='utf-8')
            m_open().write.assert_called_once_with("MOCKED_TEXT")

            # 3. Verify return path
            self.assertEqual(result_path, str(expected_path))


if __name__ == '__main__':
    unittest.main()