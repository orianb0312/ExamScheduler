"""Input controls for configuring an external CLI run."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.ui.process_runner import CliRunConfig


class InputPanel(QWidget):
    """Collect file paths and CLI options without importing v1 code."""

    run_requested = pyqtSignal(CliRunConfig)
    cancel_requested = pyqtSignal()

    def __init__(self, project_root: Path, parent=None) -> None:
        super().__init__(parent)
        self._project_root = project_root

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["complete-count", "period", "complete-write", "auto"])

        self.output_config_edit = self._path_edit(project_root / "config.json")
        self.course_file_edit = self._path_edit(project_root / "data" / "V1.0CourseDB.txt")
        self.dates_file_edit = self._path_edit(project_root / "data" / "V1.0 ExamDates.txt")
        self.user_file_edit = self._path_edit(project_root / "data" / "Programs.txt")
        self.period_indexes_edit = QLineEdit()
        self.period_indexes_edit.setPlaceholderText("Optional, e.g. 0,1")

        self.max_systems_edit = QLineEdit()
        self.max_systems_edit.setPlaceholderText("No limit")
        self.max_systems_edit.setValidator(QIntValidator(1, 10_000_000, self))

        self.time_limit_edit = QLineEdit("30")
        self.time_limit_edit.setValidator(QIntValidator(1, 3600, self))
        self.time_limit_edit.setToolTip("Auto mode time limit in seconds.")

        self.run_button = QPushButton("Run")
        self.run_button.setObjectName("primaryButton")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)

        self._build_layout()
        self._connect_signals()

    def set_running(self, running: bool) -> None:
        self.run_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)

    def _build_layout(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(12)
        title = QLabel("Input Screen")
        title.setObjectName("screenTitle")
        root_layout.addWidget(title)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setColumnStretch(1, 1)
        self._add_row(form, 0, "Mode", self.mode_combo)
        self._add_row(form, 1, "Config", self._with_browse(self.output_config_edit, "Select config file"))
        self._add_row(form, 2, "Courses", self._with_browse(self.course_file_edit, "Select courses file"))
        self._add_row(form, 3, "Exam dates", self._with_browse(self.dates_file_edit, "Select exam dates file"))
        self._add_row(form, 4, "Programs", self._with_browse(self.user_file_edit, "Select programs file"))
        self._add_row(form, 5, "Period indexes", self.period_indexes_edit)
        self._add_row(form, 6, "Max systems", self.max_systems_edit)
        self._add_row(form, 7, "Auto time limit", self.time_limit_edit)
        root_layout.addLayout(form)

        actions = QHBoxLayout()
        actions.addWidget(self.run_button)
        actions.addWidget(self.cancel_button)
        root_layout.addLayout(actions)
        root_layout.addStretch()

    def _connect_signals(self) -> None:
        self.run_button.clicked.connect(self._emit_run_requested)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)

    def _emit_run_requested(self) -> None:
        try:
            config = self._build_config()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid input", str(exc))
            return

        self.run_requested.emit(config)

    def _build_config(self) -> CliRunConfig:
        period_indexes = self._parse_period_indexes(self.period_indexes_edit.text())
        max_systems = self._parse_optional_int(
            self.max_systems_edit.text(),
            "Max systems",
            minimum=1,
            maximum=10_000_000,
        )
        time_limit = float(
            self._parse_required_int(
                self.time_limit_edit.text(),
                "Auto time limit",
                minimum=1,
                maximum=3600,
            )
        )

        return CliRunConfig(
            project_root=self._project_root,
            mode=self.mode_combo.currentText(),
            output_config=self._path_or_none(self.output_config_edit.text()),
            period_indexes=period_indexes,
            max_systems=max_systems,
            time_limit_seconds=time_limit,
            course_file=self._path_or_none(self.course_file_edit.text()),
            dates_file=self._path_or_none(self.dates_file_edit.text()),
            user_file=self._path_or_none(self.user_file_edit.text()),
        )

    @staticmethod
    def _path_edit(path: Path) -> QLineEdit:
        edit = QLineEdit(str(path))
        edit.setMinimumWidth(420)
        edit.setToolTip(str(path))
        edit.setCursorPosition(0)
        return edit

    @staticmethod
    def _add_row(layout: QGridLayout, row: int, label_text: str, widget: QWidget) -> None:
        label = QLabel(label_text)
        label.setMinimumWidth(110)
        layout.addWidget(label, row, 0)
        layout.addWidget(widget, row, 1)

    def _with_browse(self, edit: QLineEdit, title: str) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(edit)
        button = QPushButton("Browse")
        button.setFixedWidth(92)
        button.clicked.connect(lambda: self._browse_file(edit, title))
        layout.addWidget(button)
        return container

    def _browse_file(self, edit: QLineEdit, title: str) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            title,
            str(self._project_root),
        )
        if path:
            edit.setText(path)
            edit.setToolTip(path)
            edit.setCursorPosition(0)

    @staticmethod
    def _path_or_none(text: str) -> Path | None:
        stripped = text.strip()
        return Path(stripped) if stripped else None

    @staticmethod
    def _parse_period_indexes(text: str) -> tuple[int, ...]:
        stripped = text.strip()
        if not stripped:
            return ()

        indexes: list[int] = []
        for token in stripped.split(","):
            value = token.strip()
            if not value:
                continue
            try:
                index = int(value)
            except ValueError as exc:
                raise ValueError("Period indexes must be comma-separated integers.") from exc
            if index < 0:
                raise ValueError("Period indexes must be zero or greater.")
            indexes.append(index)

        return tuple(indexes)

    @staticmethod
    def _parse_optional_int(
        text: str,
        field_name: str,
        minimum: int,
        maximum: int,
    ) -> int | None:
        stripped = text.strip()
        if not stripped:
            return None
        return InputPanel._parse_required_int(stripped, field_name, minimum, maximum)

    @staticmethod
    def _parse_required_int(
        text: str,
        field_name: str,
        minimum: int,
        maximum: int,
    ) -> int:
        stripped = text.strip()
        try:
            value = int(stripped)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a whole number.") from exc

        if value < minimum or value > maximum:
            raise ValueError(f"{field_name} must be between {minimum} and {maximum}.")

        return value
