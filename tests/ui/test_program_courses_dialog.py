import pytest
from dataclasses import dataclass
from src.ui.program_courses_dialog import ProgramCoursesDialog


@dataclass
class MockCourseRow:
    """
    A mock data class mimicking 'CourseRow' from selected_programs_service.py.
    Includes the newly required fields: status and assessment.
    """
    course_id: str
    name: str
    status: str
    assessment: str


@pytest.fixture
def courses_dialog(qtbot):
    """
    Fixture providing a fresh ProgramCoursesDialog instance populated with mock data.
    """
    mock_courses = [
        MockCourseRow(
            course_id="83101",
            name="Calculus 1",
            status="Obligatory",
            assessment="Exam"
        ),
        MockCourseRow(
            course_id="83102",
            name="Advanced Programming",
            status="Elective",
            assessment="Project"
        )
    ]

    dialog = ProgramCoursesDialog(
        program_id="83104",
        display_name="Industrial Engineering",
        courses=mock_courses
    )

    qtbot.addWidget(dialog)
    return dialog


def test_dialog_table_has_four_columns(courses_dialog):
    """
    Verifies that the table structure was updated to include 4 columns
    with the correct headers.
    """
    table = courses_dialog.table_widget

    assert table.columnCount() == 4

    headers = [table.horizontalHeaderItem(i).text() for i in range(4)]
    assert headers == ["Course ID", "Course Name", "Status", "Assessment Method"]


def test_dialog_displays_status_and_assessment(courses_dialog):
    """
    Acceptance Criteria: Verify that the displayed values come from the loaded course data.
    Checks if the status and assessment method are correctly extracted and displayed.
    """
    table = courses_dialog.table_widget

    assert table.rowCount() == 2

    # Assert row 0 (Calculus 1 - Obligatory / Exam)
    assert table.item(0, 0).text() == "83101"
    assert table.item(0, 1).text() == "Calculus 1"
    assert table.item(0, 2).text() == "Obligatory"
    assert table.item(0, 3).text() == "Exam"

    # Assert row 1 (Advanced Programming - Elective / Project)
    assert table.item(1, 0).text() == "83102"
    assert table.item(1, 1).text() == "Advanced Programming"
    assert table.item(1, 2).text() == "Elective"
    assert table.item(1, 3).text() == "Project"


def test_dialog_handles_missing_attributes_gracefully(qtbot):
    """
    Edge Case: The provided CourseRow objects are missing the new attributes.
    Verifies that the UI falls back to 'N/A' without crashing.
    """

    @dataclass
    class IncompleteCourseRow:
        course_id: str
        name: str
        # Intentionally omitting 'status' and 'assessment'

    incomplete_courses = [IncompleteCourseRow(course_id="99999", name="Legacy Course")]

    dialog = ProgramCoursesDialog(
        program_id="00000",
        display_name="Legacy Program",
        courses=incomplete_courses
    )
    qtbot.addWidget(dialog)

    table = dialog.table_widget

    # Ensure it didn't crash and populated the row
    assert table.rowCount() == 1

    # Verify fallback logic kicks in
    assert table.item(0, 2).text() == "N/A"
    assert table.item(0, 3).text() == "N/A"

def test_visual_inspection_pause(courses_dialog):
    """
    TEMPORARY TEST: Opens the dialog on the screen so you can visually
    inspect the column widths, alignment, and spacing.
    Close the dialog window manually to finish the test.
    """
    courses_dialog.exec()