from pathlib import Path

import pytest
from PyQt6.QtCore import Qt

from src.services.file_loading_service import DataLoadMode, FileLoadingError, FileLoadingService
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


REPLACEMENT_COURSES_TEXT = """$$$$
Algorithms
20001
Dr. Edsger Dijkstra
83108,2,SUMM,Obligatory
Exam
"""


REPLACEMENT_EXAM_DATES_TEXT = """$$$$
SUMM,Gimel
01-09-2026, 10-09-2026
05-09-2026 Saturday
"""


SUPPLEMENTAL_COURSES_TEXT = """$$$$
Calculus 1 - Changed Copy
10001
Dr. Someone Else
83109,4,FALL,Elective
Exam
$$$$
Operating Systems
10003
Dr. Barbara Liskov
83108,2,FALL,Obligatory
Exam
"""


SUPPLEMENTAL_EXAM_DATES_TEXT = """$$$$
FALL,Aleph
20-01-2026, 30-01-2026
24-01-2026 Saturday
$$$$
SUMM,Gimel
01-09-2026, 10-09-2026
05-09-2026 Saturday
"""


def _write_input_files(
    tmp_path: Path,
    courses_text: str = COURSES_TEXT,
    exam_dates_text: str = EXAM_DATES_TEXT,
    suffix: str = "",
) -> tuple[Path, Path]:
    courses_file = tmp_path / f"courses{suffix}.txt"
    exam_dates_file = tmp_path / f"exam_dates{suffix}.txt"
    courses_file.write_text(courses_text, encoding="utf-8")
    exam_dates_file.write_text(exam_dates_text, encoding="utf-8")
    return courses_file, exam_dates_file


def test_service_parses_selected_files_and_stores_result_in_memory(tmp_path):
    courses_file, exam_dates_file = _write_input_files(tmp_path)
    service = FileLoadingService()

    result = service.load_selected_files(courses_file, exam_dates_file)
    loaded_data = result.loaded_data

    assert service.loaded_data is loaded_data
    assert result.course_mode == DataLoadMode.REPLACE
    assert result.exam_dates_mode == DataLoadMode.REPLACE
    assert loaded_data.course_count == 2
    assert loaded_data.exam_period_count == 2
    assert [program.program_id for program in loaded_data.programs] == [83101, 83102]
    assert loaded_data.courses[0].name == "Calculus 1"
    assert loaded_data.exam_periods[0].term.value == "Aleph"
    assert "Replaced loaded data with 2 courses" in result.message


def test_replace_mode_keeps_only_new_courses_and_exam_dates(tmp_path):
    initial_courses_file, initial_dates_file = _write_input_files(tmp_path)
    new_courses_file, new_dates_file = _write_input_files(
        tmp_path,
        REPLACEMENT_COURSES_TEXT,
        REPLACEMENT_EXAM_DATES_TEXT,
        suffix="_replacement",
    )
    service = FileLoadingService()
    service.load_selected_files(initial_courses_file, initial_dates_file)

    result = service.load_selected_files(
        new_courses_file,
        new_dates_file,
        DataLoadMode.REPLACE,
        DataLoadMode.REPLACE,
    )
    loaded_data = result.loaded_data

    assert [course.course_id for course in loaded_data.courses] == [20001]
    assert [(period.semester.value, period.term.value) for period in loaded_data.exam_periods] == [
        ("SUMM", "Gimel")
    ]
    assert [program.program_id for program in loaded_data.programs] == [83108]
    assert service.loaded_data is loaded_data


def test_update_mode_adds_supplementary_courses_and_exam_dates(tmp_path):
    initial_courses_file, initial_dates_file = _write_input_files(tmp_path)
    supplemental_courses_file, supplemental_dates_file = _write_input_files(
        tmp_path,
        SUPPLEMENTAL_COURSES_TEXT,
        SUPPLEMENTAL_EXAM_DATES_TEXT,
        suffix="_supplemental",
    )
    service = FileLoadingService()
    service.load_selected_files(initial_courses_file, initial_dates_file)

    result = service.load_selected_files(
        supplemental_courses_file,
        supplemental_dates_file,
        DataLoadMode.UPDATE,
        DataLoadMode.UPDATE,
    )
    loaded_data = result.loaded_data

    assert [course.course_id for course in loaded_data.courses] == [10001, 10002, 10003]
    assert [course.name for course in loaded_data.courses] == [
        "Calculus 1",
        "Software Project",
        "Operating Systems",
    ]
    assert [program.program_id for program in loaded_data.programs] == [
        83101,
        83102,
        83108,
        83109,
    ]
    calculus = next(course for course in loaded_data.courses if course.course_id == 10001)
    assert [affiliation.program_id for affiliation in calculus.affiliations] == [
        83101,
        83102,
        83109,
    ]
    assert [(period.semester.value, period.term.value) for period in loaded_data.exam_periods] == [
        ("FALL", "Aleph"),
        ("SPRI", "Bet"),
        ("SUMM", "Gimel"),
    ]
    assert result.added_course_count == 1
    assert result.added_exam_period_count == 1
    assert result.duplicate_course_count == 1
    assert result.duplicate_exam_period_count == 1
    assert "Courses: added 1 new course" in result.message
    assert "Merged 1 existing course" in result.message
    assert "Exam dates: added 1 new exam period" in result.message
    assert result.message.count("Ignored 1 duplicate record") == 1


def test_courses_and_exam_dates_can_use_different_load_modes(tmp_path):
    initial_courses_file, initial_dates_file = _write_input_files(tmp_path)
    mixed_courses_file, mixed_dates_file = _write_input_files(
        tmp_path,
        REPLACEMENT_COURSES_TEXT,
        SUPPLEMENTAL_EXAM_DATES_TEXT,
        suffix="_mixed",
    )
    service = FileLoadingService()
    service.load_selected_files(initial_courses_file, initial_dates_file)

    result = service.load_selected_files(
        mixed_courses_file,
        mixed_dates_file,
        DataLoadMode.REPLACE,
        DataLoadMode.UPDATE,
    )
    loaded_data = result.loaded_data

    assert [course.course_id for course in loaded_data.courses] == [20001]
    assert [(period.semester.value, period.term.value) for period in loaded_data.exam_periods] == [
        ("FALL", "Aleph"),
        ("SPRI", "Bet"),
        ("SUMM", "Gimel"),
    ]
    assert result.added_course_count == 1
    assert result.added_exam_period_count == 1
    assert result.duplicate_course_count == 0
    assert result.duplicate_exam_period_count == 1
    assert "Courses: replaced with 1 course" in result.message
    assert "Exam dates: added 1 new exam period" in result.message


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
    assert "Replaced loaded data with 2 courses" in window.input_panel.file_loader.error_label.text()


def test_main_window_update_keeps_existing_program_choices(tmp_path, qtbot):
    courses_text = """$$$$
Manual New Program Course
77777
Dr. UI Tester
99999,1,FALL,Elective
Exam
"""
    courses_file, exam_dates_file = _write_input_files(
        tmp_path,
        courses_text,
        SUPPLEMENTAL_EXAM_DATES_TEXT,
    )
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)
    initial_programs = [
        window.input_panel.program_selector.item(index).text()
        for index in range(window.input_panel.program_selector.count())
    ]

    window.input_panel.file_loader.set_courses_path(str(courses_file))
    window.input_panel.file_loader.set_exam_dates_path(str(exam_dates_file))
    window.input_panel.file_loader.set_course_load_mode("update")
    window.input_panel.file_loader.set_exam_dates_load_mode("update")
    qtbot.mouseClick(
        window.input_panel.file_loader.load_button,
        Qt.MouseButton.LeftButton,
    )

    updated_programs = [
        window.input_panel.program_selector.item(index).text()
        for index in range(window.input_panel.program_selector.count())
    ]

    assert set(initial_programs) <= set(updated_programs)
    assert "99999" in updated_programs
