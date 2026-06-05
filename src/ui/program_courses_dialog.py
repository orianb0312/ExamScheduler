from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.services.selected_programs_service import CourseRow


class ProgramCoursesDialog(QDialog):
    """
    Modal, read-only dialog that lists all courses connected to a single study program.
    Complies with Jira task: 'Add Course View For A Program' showing only ID and Name.
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

        self.setWindowTitle(f"Courses — {display_name}")
        self.setMinimumSize(500, 400)
        self.resize(550, 450)
        self.setModal(True)

        self._build_ui()
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


        self.table_widget = QTableWidget()
        self.table_widget.setObjectName("programCoursesTable")
        #self.table_widget.setColumnCount(2)
        #self.table_widget.setHorizontalHeaderLabels(["Course ID", "Course Name"])
        self.table_widget.setColumnCount(4)
        self.table_widget.setHorizontalHeaderLabels(["Course ID", "Course Name", "Status", "Assessment Method"])

        #self.table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        #self.table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_widget.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_widget.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

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

    def _populate_table(self) -> None:
        if not self._courses:
            self.table_widget.setRowCount(0)
            self._summary_label.setText("No courses found.")
            return


        unique_courses: list[CourseRow] = []
        seen_ids: set[str] = set()

        for course in self._courses:
            if course.course_id not in seen_ids:
                seen_ids.add(course.course_id)
                unique_courses.append(course)

        self.table_widget.setRowCount(len(unique_courses))

        for row, course in enumerate(unique_courses):
            id_item = QTableWidgetItem(course.course_id)
            name_item = QTableWidgetItem(course.name)
            status_val = getattr(course, 'requirement', 'N/A')
            if not status_val:
                status_val = 'N/A'
            assessment_val = getattr(course, 'assessment', 'N/A')
            if not assessment_val:
                assessment_val = 'N/A'
            status_item = QTableWidgetItem(str(status_val))
            assessment_item = QTableWidgetItem(str(assessment_val))

            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            assessment_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table_widget.setItem(row, 0, id_item)
            self.table_widget.setItem(row, 1, name_item)
            self.table_widget.setItem(row, 2, status_item)
            self.table_widget.setItem(row, 3, assessment_item)

        count = len(unique_courses)
        self._summary_label.setText(
            f"{count} unique course{'s' if count != 1 else ''} found for this program."
        )