from dataclasses import dataclass

import pytest

from src.ui.program_courses_dialog import ProgramCoursesDialog


@dataclass
class MockCourseRow:
    course_id: str
    name: str
    year: int
    semester: str
    status: str
    assessment: str


@pytest.fixture
def courses_dialog(qtbot):
    mock_courses = [
        MockCourseRow(
            course_id="83101",
            name="Calculus 1",
            year=1,
            semester="FALL",
            status="Obligatory",
            assessment="Exam",
        ),
        MockCourseRow(
            course_id="83102",
            name="Advanced Programming",
            year=2,
            semester="SPRI",
            status="Elective",
            assessment="Project",
        ),
        MockCourseRow(
            course_id="83103",
            name="Summer Lab",
            year=2,
            semester="SUMM",
            status="Obligatory",
            assessment="Attendance",
        ),
    ]

    dialog = ProgramCoursesDialog(
        program_id="83104",
        display_name="Industrial Engineering",
        courses=mock_courses,
    )

    qtbot.addWidget(dialog)
    return dialog


def _table_rows(dialog: ProgramCoursesDialog) -> list[list[str]]:
    table = dialog.table_widget
    return [
        [
            table.item(row, column).text()
            for column in range(table.columnCount())
        ]
        for row in range(table.rowCount())
    ]


def test_dialog_table_has_year_semester_status_and_assessment_columns(courses_dialog):
    table = courses_dialog.table_widget

    assert table.columnCount() == 6

    headers = [table.horizontalHeaderItem(i).text() for i in range(6)]
    assert headers == [
        "Year",
        "Semester",
        "Course ID",
        "Course Name",
        "Status",
        "Assessment Method",
    ]


def test_dialog_displays_year_semester_status_and_assessment(courses_dialog):
    assert _table_rows(courses_dialog) == [
        ["1", "FALL", "83101", "Calculus 1", "Obligatory", "Exam"],
        ["2", "SPRI", "83102", "Advanced Programming", "Elective", "Project"],
        ["2", "SUMM", "83103", "Summer Lab", "Obligatory", "Attendance"],
    ]


def test_dialog_filters_courses_by_year(courses_dialog):
    courses_dialog.year_filter.setCurrentText("2")

    assert _table_rows(courses_dialog) == [
        ["2", "SPRI", "83102", "Advanced Programming", "Elective", "Project"],
        ["2", "SUMM", "83103", "Summer Lab", "Obligatory", "Attendance"],
    ]


def test_dialog_filters_courses_by_semester(courses_dialog):
    courses_dialog.semester_filter.setCurrentText("SPRI")

    assert _table_rows(courses_dialog) == [
        ["2", "SPRI", "83102", "Advanced Programming", "Elective", "Project"],
    ]


def test_dialog_combines_year_and_semester_filters_and_keeps_all_accessible(courses_dialog):
    courses_dialog.year_filter.setCurrentText("2")
    courses_dialog.semester_filter.setCurrentText("SPRI")

    assert _table_rows(courses_dialog) == [
        ["2", "SPRI", "83102", "Advanced Programming", "Elective", "Project"],
    ]

    courses_dialog.year_filter.setCurrentText("All Years")
    courses_dialog.semester_filter.setCurrentText("All Semesters")

    assert len(_table_rows(courses_dialog)) == 3


def test_dialog_filter_options_include_all_available_years_and_semesters(courses_dialog):
    assert [
        courses_dialog.year_filter.itemText(index)
        for index in range(courses_dialog.year_filter.count())
    ] == ["All Years", "1", "2"]

    assert [
        courses_dialog.semester_filter.itemText(index)
        for index in range(courses_dialog.semester_filter.count())
    ] == ["All Semesters", "FALL", "SPRI", "SUMM"]


def test_dialog_handles_missing_attributes_gracefully(qtbot):
    @dataclass
    class IncompleteCourseRow:
        course_id: str
        name: str

    dialog = ProgramCoursesDialog(
        program_id="00000",
        display_name="Legacy Program",
        courses=[IncompleteCourseRow(course_id="99999", name="Legacy Course")],
    )
    qtbot.addWidget(dialog)

    assert _table_rows(dialog) == [
        ["N/A", "N/A", "99999", "Legacy Course", "N/A", "N/A"],
    ]


def test_dialog_displays_blank_or_none_values_as_not_available(qtbot):
    @dataclass
    class PartialCourseRow:
        course_id: str | None
        name: str
        year: int | None
        semester: str
        status: str | None
        assessment: str

    dialog = ProgramCoursesDialog(
        program_id="00000",
        display_name="Legacy Program",
        courses=[
            PartialCourseRow(
                course_id=None,
                name="   ",
                year=None,
                semester="",
                status=None,
                assessment="",
            )
        ],
    )
    qtbot.addWidget(dialog)

    assert _table_rows(dialog) == [
        ["N/A", "N/A", "N/A", "N/A", "N/A", "N/A"],
    ]
