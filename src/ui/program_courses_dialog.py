from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.services.selected_programs_service import CourseRow


class ProgramCoursesDialog(QDialog):
    """
    Modal, read-only dialog that lists all courses connected to a single study program.
    Supports filtering the program's courses by academic year and semester.
    """

    def __init__(
        self,
        program_id: str,
        display_name: str,
        courses: list[CourseRow],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._program_id = program_id
        self._display_name = display_name
        self._courses = courses

        self.setWindowTitle(f"Courses - {display_name}")
        self.setMinimumSize(760, 460)
        self.resize(840, 520)
        self.setModal(True)

        self._build_ui()
        self._populate_filter_controls()
        self._populate_table()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        title = QLabel(self._display_name)
        title.setObjectName("dialogProgramTitle")
        title.setStyleSheet("font-weight: bold; font-size: 15px;")
        layout.addWidget(title)

        subtitle = QLabel(f"Program ID: {self._program_id}")
        subtitle.setObjectName("dialogProgramSubtitle")
        subtitle.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(subtitle)

        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(8)

        year_label = QLabel("Year")
        self.year_filter = QComboBox()
        self.year_filter.setObjectName("yearFilter")
        self.year_filter.currentIndexChanged.connect(lambda _index: self._populate_table())

        semester_label = QLabel("Semester")
        self.semester_filter = QComboBox()
        self.semester_filter.setObjectName("semesterFilter")
        self.semester_filter.currentIndexChanged.connect(lambda _index: self._populate_table())

        filter_layout.addWidget(year_label)
        filter_layout.addWidget(self.year_filter)
        filter_layout.addWidget(semester_label)
        filter_layout.addWidget(self.semester_filter)
        filter_layout.addStretch(1)
        layout.addLayout(filter_layout)

        self.table_widget = QTableWidget()
        self.table_widget.setObjectName("programCoursesTable")
        self.table_widget.setColumnCount(6)
        self.table_widget.setHorizontalHeaderLabels([
            "Year",
            "Semester",
            "Course ID",
            "Course Name",
            "Status",
            "Assessment Method",
        ])

        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        self.table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.setAlternatingRowColors(True)

        layout.addWidget(self.table_widget)

        self._summary_label = QLabel()
        self._summary_label.setObjectName("dialogSummaryLabel")
        self._summary_label.setStyleSheet("font-style: italic; color: #555;")
        layout.addWidget(self._summary_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_filter_controls(self) -> None:
        years = sorted(
            {
                course.year
                for course in self._courses
                if isinstance(getattr(course, "year", None), int)
            }
        )
        semesters = sorted(
            {
                str(getattr(course, "semester", "")).strip()
                for course in self._courses
                if str(getattr(course, "semester", "")).strip()
            },
            key=_semester_sort_key,
        )

        self.year_filter.blockSignals(True)
        self.semester_filter.blockSignals(True)
        try:
            self.year_filter.clear()
            self.year_filter.addItem("All Years", None)
            for year in years:
                self.year_filter.addItem(str(year), year)

            self.semester_filter.clear()
            self.semester_filter.addItem("All Semesters", None)
            for semester in semesters:
                self.semester_filter.addItem(semester, semester)
        finally:
            self.year_filter.blockSignals(False)
            self.semester_filter.blockSignals(False)

    def _populate_table(self) -> None:
        if not self._courses:
            self.table_widget.setRowCount(0)
            self._summary_label.setText("No courses found.")
            return

        all_rows = self._unique_courses(self._courses)
        filtered_rows = [
            course
            for course in all_rows
            if self._matches_selected_filters(course)
        ]

        self.table_widget.setRowCount(len(filtered_rows))

        for row, course in enumerate(filtered_rows):
            values = [
                _display_value(getattr(course, "year", None)),
                _display_value(getattr(course, "semester", None)),
                _display_value(getattr(course, "course_id", None)),
                _display_value(getattr(course, "name", None)),
                _display_value(getattr(course, "status", None)),
                _display_value(getattr(course, "assessment", None)),
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_widget.setItem(row, column, item)

        if not filtered_rows:
            self._summary_label.setText("No courses match the selected filters.")
            return

        count = len(filtered_rows)
        total = len(all_rows)
        if count == total:
            self._summary_label.setText(
                f"{count} course{'s' if count != 1 else ''} found for this program."
            )
        else:
            self._summary_label.setText(
                f"{count} of {total} courses shown for this program."
            )

    def _matches_selected_filters(self, course: CourseRow) -> bool:
        selected_year = self.year_filter.currentData()
        selected_semester = self.semester_filter.currentData()

        if selected_year is not None and getattr(course, "year", None) != selected_year:
            return False
        if selected_semester is not None and getattr(course, "semester", None) != selected_semester:
            return False
        return True

    @staticmethod
    def _unique_courses(courses: list[CourseRow]) -> list[CourseRow]:
        unique_courses: list[CourseRow] = []
        seen_keys: set[str] = set()

        for course in courses:
            key = "|".join(
                str(getattr(course, field_name, ""))
                for field_name in ("course_id", "year", "semester", "status", "assessment")
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            unique_courses.append(course)

        return unique_courses


def _semester_sort_key(semester: str) -> int:
    order = {"FALL": 0, "SPRI": 1, "SUMM": 2}
    return order.get(semester, 99)


def _display_value(value) -> str:
    if value is None:
        return "N/A"
    text = str(value).strip()
    if not text:
        return "N/A"
    return text
