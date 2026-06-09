from pathlib import Path

import pytest
from PyQt6.QtCore import Qt

from src.services.file_loading_service import DataLoadMode, FileLoadingError, FileLoadingService
from src.ui.program_selection_widget import PROGRAM_ID_ROLE
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


def test_update_mode_merges_distinct_affiliations_for_duplicate_course(tmp_path):
    initial_courses_text = """$$$$
Shared Course
10001
Dr. Existing
83101,1,FALL,Obligatory
Exam
"""
    supplemental_courses_text = """$$$$
Shared Course Updated
10001
Dr. Incoming
83101,2,SPRI,Elective
83101,1,FALL,Obligatory
Exam
"""
    initial_courses_file, initial_dates_file = _write_input_files(
        tmp_path,
        initial_courses_text,
        EXAM_DATES_TEXT,
    )
    supplemental_courses_file, supplemental_dates_file = _write_input_files(
        tmp_path,
        supplemental_courses_text,
        EXAM_DATES_TEXT,
        suffix="_supplemental_affiliations",
    )
    service = FileLoadingService()
    service.load_selected_files(initial_courses_file, initial_dates_file)

    result = service.load_selected_files(
        supplemental_courses_file,
        supplemental_dates_file,
        DataLoadMode.UPDATE,
        DataLoadMode.UPDATE,
    )
    loaded_course = result.loaded_data.courses[0]

    assert loaded_course.name == "Shared Course"
    assert [
        (
            affiliation.program_id,
            affiliation.year,
            affiliation.semester.value,
            affiliation.requirement_type.value,
        )
        for affiliation in loaded_course.affiliations
    ] == [
        (83101, 1, "FALL", "Obligatory"),
        (83101, 2, "SPRI", "Elective"),
    ]


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


def test_main_window_default_startup_load_does_not_show_success_message(tmp_path, qtbot):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "V1.0CourseDB.txt").write_text(COURSES_TEXT, encoding="utf-8")
    (data_dir / "V1.0 ExamDates.txt").write_text(EXAM_DATES_TEXT, encoding="utf-8")

    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    assert window.loaded_input_data is not None
    assert window.loaded_input_data.course_count == 2
    assert window.input_panel.file_loader.error_label.isHidden()
    assert window.input_panel.file_loader.error_label.text() == ""


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
        window.input_panel.program_selector.item(index).data(PROGRAM_ID_ROLE)
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
        window.input_panel.program_selector.item(index).data(PROGRAM_ID_ROLE)
        for index in range(window.input_panel.program_selector.count())
    ]

    assert set(initial_programs) <= set(updated_programs)
    assert "99999" in updated_programs


def test_main_window_displays_program_name_and_identifier_after_load(tmp_path, qtbot):
    courses_file, exam_dates_file = _write_input_files(tmp_path)
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)

    window.input_panel.file_loader.set_courses_path(str(courses_file))
    window.input_panel.file_loader.set_exam_dates_path(str(exam_dates_file))
    qtbot.mouseClick(
        window.input_panel.file_loader.load_button,
        Qt.MouseButton.LeftButton,
    )

    first_item = window.input_panel.program_selector.item(0)

    assert first_item.data(PROGRAM_ID_ROLE) == "83101"
    assert first_item.text() == "83101"


def test_unchanged_source_files_allow_internal_data_loading(tmp_path):
    """
    Acceptance Criteria:
    - On application startup, check whether internal saved data exists.
    - Compare the stored source file information with the current source files.
    - If the source files are unchanged, load the internal saved data.
    - Populate the application state from the internal data.
    - Write a test confirming that unchanged source files allow internal data loading.
    """
    from src.services.internal_data_store import InternalDataStore
    from src.services.file_loading_service import FileLoadingService

    # Setup test files and an isolated cache file
    courses_file, exam_dates_file = _write_input_files(tmp_path)
    cache_file = tmp_path / "test_cache.json"
    store = InternalDataStore(cache_file)

    # 1. FIRST RUN (App Startup without cache)
    # The internal data doesn't exist yet, so it reads the files and creates the cache.
    first_service = FileLoadingService(internal_store=store)
    first_result = first_service.load_selected_files(courses_file, exam_dates_file)

    assert cache_file.exists(), "Internal saved data MUST be created after the first load."

    # 2. SECOND RUN (App Restart with unchanged files)
    # We create a dummy parser that intentionally crashes the test if it gets called.
    # This is the ultimate proof that the app uses internal data WITHOUT reloading source files.
    class _CrashParser:
        def parse_files(self, c_file, e_file):
            raise AssertionError("FAILED: The app tried to parse the files instead of using internal saved data!")

    second_service = FileLoadingService(parser_adapter=_CrashParser(), internal_store=store)
    second_result = second_service.load_selected_files(courses_file, exam_dates_file)

    # 3. ASSERTIONS: Verify the application state is successfully populated from the internal data
    assert second_result.loaded_data is not None
    assert second_result.loaded_data.course_count == first_result.loaded_data.course_count
    assert second_result.loaded_data.exam_period_count == first_result.loaded_data.exam_period_count

def test_internal_data_ignored_when_source_file_becomes_empty(tmp_path):
    """
    Edge Case 1: The user clears all text from a source file after it was cached.
    The hash will change, so the system must ignore the cache and parse again.
    """
    from src.services.internal_data_store import InternalDataStore
    from src.services.file_loading_service import FileLoadingService, LoadedSchedulerInput

    courses_file, exam_dates_file = _write_input_files(tmp_path)
    cache_file = tmp_path / "test_cache_empty.json"
    store = InternalDataStore(cache_file)

    # 1. Populate the cache with valid data
    FileLoadingService(internal_store=store).load_selected_files(courses_file, exam_dates_file)

    # 2. Simulate user clearing the file completely
    courses_file.write_text("", encoding="utf-8")

    # 3. Create a mock parser that tracks if it was called
    class _TrackerParser:
        def __init__(self):
            self.called = False

        def parse_files(self, c_file, e_file):
            self.called = True
            return LoadedSchedulerInput(courses=(), exam_periods=(), programs=())

    tracker = _TrackerParser()
    FileLoadingService(parser_adapter=tracker, internal_store=store).load_selected_files(courses_file,
                                                                                         exam_dates_file)

    # 4. Assert that the cache was bypassed due to the file becoming empty
    assert tracker.called is True, "System used cached data even though the source file was emptied!"

def test_internal_data_ignored_when_cache_file_is_corrupted(tmp_path):
    """
    Edge Case 2: The internal JSON cache file gets corrupted.
    The system should gracefully catch the JSON error, bypass the cache, and re-parse.
    """
    from src.services.internal_data_store import InternalDataStore
    from src.services.file_loading_service import FileLoadingService, LoadedSchedulerInput

    courses_file, exam_dates_file = _write_input_files(tmp_path)
    cache_file = tmp_path / "test_cache_corrupted.json"
    store = InternalDataStore(cache_file)

    # 1. Populate the cache normally
    FileLoadingService(internal_store=store).load_selected_files(courses_file, exam_dates_file)

    # 2. Simulate data corruption in the JSON file
    cache_file.write_text("{ corrupted : json [ data !! ", encoding="utf-8")

    # 3. Create a mock parser that tracks if it was called
    class _TrackerParser:
        def __init__(self):
            self.called = False

        def parse_files(self, c_file, e_file):
            self.called = True
            return LoadedSchedulerInput(courses=(), exam_periods=(), programs=())

    tracker = _TrackerParser()
    FileLoadingService(parser_adapter=tracker, internal_store=store).load_selected_files(courses_file,
                                                                                         exam_dates_file)

    # 4. Assert that the cache was bypassed safely without crashing the application
    assert tracker.called is True, "System crashed or didn't call parser when cache was corrupted!"
