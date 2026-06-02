import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel, QFileDialog
from PyQt6.QtCore import pyqtSignal, Qt

class FileLoaderWidget(QWidget):
    """
    A passive, format-agnostic UI view managing file path collections.
    Dispatches targeted state modifications and verification events to support decoupled architecture.
    """
    # Signal emitted when the user triggers the data load sequence
    load_requested = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        # Top-level layout orchestration
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(20)

        # Header Section
        header_label = QLabel("Data Source Configuration")
        main_layout.addWidget(header_label)

        # -------------------------------------------------------------------
        # Row 1: Courses Catalog Configuration
        # -------------------------------------------------------------------
        courses_layout = QHBoxLayout()
        courses_layout.setSpacing(12)

        courses_lbl = QLabel("Courses File:")
        courses_lbl.setMinimumWidth(120)

        self.courses_input = QLineEdit()
        self.courses_input.setReadOnly(False)
        self.courses_input.setPlaceholderText("Select catalog data file from local system...")
        self.courses_input.textChanged.connect(self._validate_inputs)

        self.courses_btn = QPushButton("Browse...")
        self.courses_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.courses_btn.clicked.connect(self._browse_courses)

        courses_layout.addWidget(courses_lbl)
        courses_layout.addWidget(self.courses_input)
        courses_layout.addWidget(self.courses_btn)
        main_layout.addLayout(courses_layout)

        # -------------------------------------------------------------------
        # Row 2: Exam Dates / Calendar Layout
        # -------------------------------------------------------------------
        exams_layout = QHBoxLayout()
        exams_layout.setSpacing(12)

        exams_lbl = QLabel("Exam Dates File:")
        exams_lbl.setMinimumWidth(120)

        self.exams_input = QLineEdit()
        self.exams_input.setReadOnly(False)
        self.exams_input.setPlaceholderText("Select calendar/period layout configuration...")
        self.exams_input.textChanged.connect(self._validate_inputs)

        self.exams_btn = QPushButton("Browse...")
        self.exams_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exams_btn.clicked.connect(self._browse_exam_dates)

        exams_layout.addWidget(exams_lbl)
        exams_layout.addWidget(self.exams_input)
        exams_layout.addWidget(self.exams_btn)
        main_layout.addLayout(exams_layout)

        # -------------------------------------------------------------------
        # Contextual Inline Error Feedback Block
        # -------------------------------------------------------------------
        self.error_label = QLabel("")
        self.error_label.setObjectName("error_label")
        self.error_label.setVisible(False)  # Muted initially until invalid state occurs
        main_layout.addWidget(self.error_label)

        main_layout.addStretch(1)

        # -------------------------------------------------------------------
        # Bottom Execution Control
        # -------------------------------------------------------------------
        self.load_button = QPushButton("Load Files Into Scheduler")
        self.load_button.setObjectName("load_button")
        self.load_button.setEnabled(False)
        self.load_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.load_button.clicked.connect(self._handle_load_clicked)
        main_layout.addWidget(self.load_button)

        self.setLayout(main_layout)

    # =======================================================================
    # MVP INTERFACE METHODS (Exposed API for Presenters/Controllers)
    # =======================================================================

    def get_courses_path(self) -> str:
        """Retrieves the raw text value of the courses input field."""
        return self.courses_input.text()

    def set_courses_path(self, path: str):
        """Sets the courses input text programmatically and re-evaluates UI validation state."""
        self.courses_input.setText(path)
        self._validate_inputs()

    def get_exam_dates_path(self) -> str:
        """Retrieves the raw text value of the exam dates input field."""
        return self.exams_input.text()

    def set_exam_dates_path(self, path: str):
        """Sets the exam dates input text programmatically and re-evaluates UI validation state."""
        self.exams_input.setText(path)
        self._validate_inputs()

    def show_load_success(self, course_count: int, period_count: int, program_count: int):
        self.error_label.setText(
            f"Loaded {course_count} courses, {period_count} exam periods, "
            f"and {program_count} study programs."
        )
        self.error_label.setVisible(True)

    def show_load_error(self, message: str):
        self.error_label.setText(f"Error: {message}")
        self.error_label.setVisible(True)
        self.load_button.setEnabled(False)

    # =======================================================================
    # INTERNAL EVENT LOGIC & VALIDATION INTERCEPTORS
    # =======================================================================

    def _browse_courses(self):
        """Launches the native Windows File Dialog to capture standard user selection paths."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Courses File", "", "All Files (*)")
        if file_path:
            self.set_courses_path(file_path)

    def _browse_exam_dates(self):
        """Launches the native Windows File Dialog to capture standard user selection paths."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Exam Dates File", "", "All Files (*)")
        if file_path:
            self.set_exam_dates_path(file_path)

    def _validate_inputs(self):
        """
        Evaluates current input parameters defensively.
        Updates user-facing warning fields without modifying backend system memory state.
        """
        courses_path = self.get_courses_path()
        exams_path = self.get_exam_dates_path()

        # Isolate verification hooks to actively populated targets only
        courses_missing = courses_path != "" and not os.path.isfile(courses_path)
        exams_missing = exams_path != "" and not os.path.isfile(exams_path)

        if courses_missing or exams_missing:
            errors = []
            if courses_missing:
                errors.append("Courses file path is invalid or does not exist.")
            if exams_missing:
                errors.append("Exam Dates file path is invalid or does not exist.")

            self.error_label.setText(" Error: " + " | ".join(errors))
            self.error_label.setVisible(True)
            self.load_button.setEnabled(False)
        else:
            # Clear warnings if states are currently valid or empty
            self.error_label.setVisible(False)
            self.error_label.setText("")

            # Unlock operational transition buttons only if fully loaded and verified
            courses_exists = os.path.isfile(courses_path)
            exams_exists = os.path.isfile(exams_path)
            self.load_button.setEnabled(courses_exists and exams_exists)

    def _handle_load_clicked(self):
        """Propagates verified path strings to active listeners upon user dispatch request."""
        self.load_requested.emit(self.get_courses_path(), self.get_exam_dates_path())
