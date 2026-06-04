from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.services.file_selection_service import FileSelectionValidator


class FileLoaderWidget(QWidget):
    """Collect course/date file paths and emit a load request."""

    load_requested = pyqtSignal(str, str, str, str)

    def __init__(self, parent=None, validator: FileSelectionValidator | None = None):
        super().__init__(parent)
        self._validator = validator or FileSelectionValidator()
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(14)

        header_label = QLabel("Data Source Configuration")
        header_label.setObjectName("sectionTitle")
        main_layout.addWidget(header_label)

        courses_layout = QHBoxLayout()
        courses_layout.setSpacing(12)

        courses_lbl = QLabel("Courses File:")
        courses_lbl.setMinimumWidth(120)

        self.courses_input = QLineEdit()
        self.courses_input.setReadOnly(False)
        self.courses_input.setMinimumHeight(32)
        self.courses_input.setPlaceholderText("Select catalog data file from local system...")
        self.courses_input.textChanged.connect(self._validate_inputs)

        self.courses_btn = QPushButton("Browse...")
        self.courses_btn.setObjectName("browseButton")
        self.courses_btn.setFixedWidth(104)
        self.courses_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.courses_btn.clicked.connect(self._browse_courses)

        self.course_replace_button = self._create_mode_button("Replace")
        self.course_update_button = self._create_mode_button("Update")
        self.course_mode_group = QButtonGroup(self)
        self.course_mode_group.setExclusive(True)
        self.course_mode_group.addButton(self.course_replace_button)
        self.course_mode_group.addButton(self.course_update_button)
        self.course_replace_button.setChecked(True)

        courses_layout.addWidget(courses_lbl)
        courses_layout.addWidget(self.courses_input)
        courses_layout.addWidget(self.courses_btn)
        courses_layout.addWidget(self.course_replace_button)
        courses_layout.addWidget(self.course_update_button)
        main_layout.addLayout(courses_layout)

        exams_layout = QHBoxLayout()
        exams_layout.setSpacing(12)

        exams_lbl = QLabel("Exam Dates File:")
        exams_lbl.setMinimumWidth(120)

        self.exams_input = QLineEdit()
        self.exams_input.setReadOnly(False)
        self.exams_input.setMinimumHeight(32)
        self.exams_input.setPlaceholderText("Select calendar/period layout configuration...")
        self.exams_input.textChanged.connect(self._validate_inputs)

        self.exams_btn = QPushButton("Browse...")
        self.exams_btn.setObjectName("browseButton")
        self.exams_btn.setFixedWidth(104)
        self.exams_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exams_btn.clicked.connect(self._browse_exam_dates)

        self.exam_dates_replace_button = self._create_mode_button("Replace")
        self.exam_dates_update_button = self._create_mode_button("Update")
        self.exam_dates_mode_group = QButtonGroup(self)
        self.exam_dates_mode_group.setExclusive(True)
        self.exam_dates_mode_group.addButton(self.exam_dates_replace_button)
        self.exam_dates_mode_group.addButton(self.exam_dates_update_button)
        self.exam_dates_replace_button.setChecked(True)

        exams_layout.addWidget(exams_lbl)
        exams_layout.addWidget(self.exams_input)
        exams_layout.addWidget(self.exams_btn)
        exams_layout.addWidget(self.exam_dates_replace_button)
        exams_layout.addWidget(self.exam_dates_update_button)
        main_layout.addLayout(exams_layout)

        self.error_label = QLabel("")
        self.error_label.setObjectName("error_label")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        main_layout.addWidget(self.error_label)

        self.load_button = QPushButton("Load Files Into Scheduler")
        self.load_button.setObjectName("load_button")
        self.load_button.setFixedWidth(220)
        self.load_button.setMinimumHeight(34)
        self.load_button.setEnabled(False)
        self.load_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.load_button.clicked.connect(self._handle_load_clicked)

        load_action_layout = QHBoxLayout()
        load_action_layout.setContentsMargins(0, 0, 0, 0)
        load_action_layout.addStretch(1)
        load_action_layout.addWidget(self.load_button)
        main_layout.addLayout(load_action_layout)

        self.setLayout(main_layout)

    def get_courses_path(self) -> str:
        return self.courses_input.text()

    def set_courses_path(self, path: str):
        self.courses_input.setText(path)
        self._validate_inputs()

    def get_exam_dates_path(self) -> str:
        return self.exams_input.text()

    def set_exam_dates_path(self, path: str):
        self.exams_input.setText(path)
        self._validate_inputs()

    def get_course_load_mode(self) -> str:
        return "replace" if self.course_replace_button.isChecked() else "update"

    def set_course_load_mode(self, mode: str):
        if mode == "replace":
            self.course_replace_button.setChecked(True)
        elif mode == "update":
            self.course_update_button.setChecked(True)

    def get_exam_dates_load_mode(self) -> str:
        return "replace" if self.exam_dates_replace_button.isChecked() else "update"

    def set_exam_dates_load_mode(self, mode: str):
        if mode == "replace":
            self.exam_dates_replace_button.setChecked(True)
        elif mode == "update":
            self.exam_dates_update_button.setChecked(True)

    def show_load_success(
        self,
        course_count: int,
        period_count: int,
        program_count: int,
        message: str | None = None,
    ):
        self.error_label.setText(
            message
            or f"Loaded {course_count} courses, {period_count} exam periods, "
            f"and {program_count} study programs."
        )
        self.error_label.setVisible(True)

    def show_load_error(self, message: str):
        self.error_label.setText(f"Error: {message}")
        self.error_label.setVisible(True)
        self.load_button.setEnabled(False)

    def _browse_courses(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Courses File", "", "All Files (*)")
        if file_path:
            self.set_courses_path(file_path)

    def _browse_exam_dates(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Exam Dates File", "", "All Files (*)")
        if file_path:
            self.set_exam_dates_path(file_path)

    @staticmethod
    def _create_mode_button(label: str) -> QPushButton:
        button = QPushButton(label)
        button.setObjectName("modeButton")
        button.setCheckable(True)
        button.setFixedWidth(82)
        button.setMinimumHeight(32)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _validate_inputs(self):
        result = self._validator.validate(
            self.get_courses_path(),
            self.get_exam_dates_path(),
        )

        if result.errors:
            self.error_label.setText(result.message)
            self.error_label.setVisible(True)
            self.load_button.setEnabled(False)
        else:
            self.error_label.setVisible(False)
            self.error_label.setText("")
            self.load_button.setEnabled(result.can_load)

    def _handle_load_clicked(self):
        self.load_requested.emit(
            self.get_courses_path(),
            self.get_exam_dates_path(),
            self.get_course_load_mode(),
            self.get_exam_dates_load_mode(),
        )
