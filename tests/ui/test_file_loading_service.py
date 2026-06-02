from pathlib import Path

import pytest
from PyQt6.QtCore import Qt

from src.services.file_loading_service import FileLoadingError, FileLoadingService
from src.ui.main_window import MainWindow


COURSES_TEXT = """$$$$
Calculus 1
10001
Dr. Ada Lovelace
83101,1,FALL,Obligatory
83102,1,FALL,Obligatory
Exam
$$$$
Software Project
10002
Dr. Grace Hopper
83101,3,SPRI,Elective
Project
"""


EXAM_DATES_TEXT = """$$$$
FALL,Aleph
01-01-2026, 10-01-2026
03-01-2026 Saturday
$$$$
SPRI,Bet
11-06-2026, 20-06-2026
13-06-2026 Saturday
"""


def _write_input_files(tmp_path: Path) -> tuple[Path, Path]:
    courses_file = tmp_path / "courses.txt"
    exam_dates_file = tmp_path / "exam_dates.txt"
    courses_file.write_text(COURSES_TEXT, encoding="utf-8")
    exam_dates_file.write_text(EXAM_DATES_TEXT, encoding="utf-8")
    return courses_file, exam_dates_file


def test_service_parses_selected_files_and_stores_result_in_memory(tmp_path):
    courses_file, exam_dates_file = _write_input_files(tmp_path)
    service = FileLoadingService()

    loaded_data = service.load_selected_files(courses_file, exam_dates_file)

    assert service.loaded_data is loaded_data
    assert loaded_data.course_count == 2
    assert loaded_data.exam_period_count == 2
    assert [program.program_id for program in loaded_data.programs] == [83101, 83102]
    assert loaded_data.courses[0].name == "Calculus 1"
    assert loaded_data.exam_periods[0].term.value == "Aleph"


def test_service_reports_missing_files_clearly(tmp_path):
    courses_file, _exam_dates_file = _write_input_files(tmp_path)
    missing_dates_file = tmp_path / "missing_dates.txt"

    with pytest.raises(FileLoadingError, match="Exam dates file does not exist"):
        FileLoadingService().load_selected_files(courses_file, missing_dates_file)


def test_main_window_loads_file_loader_selection_into_memory(tmp_path, qtbot):
    courses_file, exam_dates_file = _write_input_files(tmp_path)
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    window.input_panel.file_loader.set_courses_path(str(courses_file))
    window.input_panel.file_loader.set_exam_dates_path(str(exam_dates_file))
    qtbot.mouseClick(
        window.input_panel.file_loader.load_button,
        Qt.MouseButton.LeftButton,
    )

    assert window.loaded_input_data is not None
    assert window.loaded_input_data.course_count == 2
    assert "Loaded 2 courses" in window.input_panel.file_loader.error_label.text()

