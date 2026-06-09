from unittest.mock import MagicMock
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView
from src.models.academic import Attendance, Exam, Project
from src.services.selected_programs_service import (
    SelectedProgramsViewModel,
    StaticProgramNameResolver,
)
from src.ui.selected_programs_panel import (
    SELECTED_PROGRAMS_TABLE_MIN_HEIGHT,
    SelectedProgramsPanel,
)


def _make_affiliation(
    program_id: int,
    year: int = 1,
    semester: str = "FALL",
    requirement: str = "Obligatory",
):
    aff = MagicMock()
    aff.program_id = int(program_id)
    aff.year = year
    aff.semester.value = semester
    aff.requirement_type.value = requirement
    return aff


def _make_course(
    course_id: int,
    name: str,
    program_ids: list,
    assessment: str = "Exam",
):
    course = MagicMock()
    course.course_id = int(course_id)
    course.name = name
    course.affiliations = [_make_affiliation(pid) for pid in program_ids]
    course.evaluation = {
        "Exam": Exam(),
        "Project": Project(),
        "Attendance": Attendance(),
    }[assessment]
    return course


def _make_loaded_data(courses, programs=None):
    loaded = MagicMock()
    loaded.courses = tuple(courses)
    dummy_program = MagicMock()
    dummy_program.program_id = 0
    loaded.programs = tuple(programs or [dummy_program])
    return loaded


def test_view_model_fallback_mapping():
    """Confirms that the ViewModel correctly maps baseline selection IDs into official English names."""
    vm = SelectedProgramsViewModel()
    vm.set_selected_program_ids(["83101", "83107"])

    details = vm.get_selected_program_details()

    assert len(details) == 2
    assert details[0]["program_id"] == "83101"
    assert details[0]["display_name"] == "Computer Engineering"
    assert details[1]["program_id"] == "83107"
    assert details[1]["display_name"] == "Data Engineering"


def test_view_model_accepts_custom_program_name_resolver():
    vm = SelectedProgramsViewModel(
        StaticProgramNameResolver({"99999": "Future Engineering"})
    )
    vm.set_selected_program_ids(["99999"])

    details = vm.get_selected_program_details()

    assert details == [
        {"program_id": "99999", "display_name": "Future Engineering"}
    ]
    assert vm.get_program_display_name("00000") == "Program 00000"


def test_panel_display_update(qtbot):
    """Confirms that the read-only UI panel displays data inputs correctly and applies center alignments."""
    panel = SelectedProgramsPanel()
    qtbot.addWidget(panel)

    mock_details = [
        {"program_id": "83104", "display_name": "Industrial Engineering and Information Systems"}
    ]

    panel.update_display(mock_details)

    assert panel.table.rowCount() == 1
    assert panel.table.item(0, 0).text() == "83104"
    assert panel.table.item(0, 1).text() == "Industrial Engineering and Information Systems"
    assert panel.table.item(0, 0).textAlignment() == Qt.AlignmentFlag.AlignCenter
    assert panel.table.minimumHeight() == SELECTED_PROGRAMS_TABLE_MIN_HEIGHT



def test_get_courses_for_program_filtering_and_sorting():
    """
    Validates course filtering by program ID, year/semester sorting,
    exclusion of unrelated programs, and handling of multiple affiliations.
    """
    vm = SelectedProgramsViewModel()

    course_1001 = _make_course(1001, "Intro to CS", [83101])
    course_1001.affiliations.append(_make_affiliation(83101, year=2))

    courses = [
        _make_course(1002, "Calculus I", [83101]),
        course_1001,
        _make_course(1003, "Physics I", [83102]),
    ]
    vm.update_available_programs(_make_loaded_data(courses))

    result = vm.get_courses_for_program("83101")
    course_ids = [r.course_id for r in result]

    assert "1001" in course_ids
    assert "1002" in course_ids
    assert "1003" not in course_ids
    assert [(row.year, row.semester, row.course_id) for row in result] == [
        (1, "FALL", "1001"),
        (1, "FALL", "1002"),
        (2, "FALL", "1001"),
    ]
    assert vm.get_courses_for_program("99999") == []


def test_get_courses_for_program_includes_year_semester_status_and_assessment():
    vm = SelectedProgramsViewModel()
    course = _make_course(70001, "Capstone", [83108], assessment="Project")
    course.affiliations[0].year = 3
    course.affiliations[0].semester.value = "SPRI"
    course.affiliations[0].requirement_type.value = "Elective"

    vm.update_available_programs(_make_loaded_data([course]))

    result = vm.get_courses_for_program("83108")

    assert len(result) == 1
    assert result[0].year == 3
    assert result[0].semester == "SPRI"
    assert result[0].status == "Elective"
    assert result[0].requirement == "Elective"
    assert result[0].assessment == "Project"


def test_get_courses_edge_cases_and_display_names():
    """
    Verifies baseline behavior before data is loaded, correct data-type mapping
    for CourseRow fields, and fallback logic for program display names.
    """
    vm = SelectedProgramsViewModel()


    assert vm.get_courses_for_program("83101") == []


    assert vm.get_program_display_name("83108") == "Software Engineering"
    assert vm.get_program_display_name("99999") == "Program 99999"


    courses = [_make_course(5001, "Operating Systems", [83101])]
    vm.update_available_programs(_make_loaded_data(courses))
    result = vm.get_courses_for_program("83101")

    assert len(result) == 1
    assert result[0].course_id == "5001"
    assert result[0].name == "Operating Systems"


def test_panel_interaction_and_readonly_course_view(qtbot):
    """
    Confirms that clicking a program emits the correct detail request,
    and validates that the loaded course display is read-only.
    """
    panel = SelectedProgramsPanel()
    qtbot.addWidget(panel)
    panel.update_display([
        {"program_id": "83101", "display_name": "Computer Engineering"},
        {"program_id": "83102", "display_name": "Electrical Engineering"},
    ])

    emitted = []
    panel.program_detail_requested.connect(emitted.append)
    panel.table.cellClicked.emit(1, 0)
    assert emitted == ["83102"]

    assert panel.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
