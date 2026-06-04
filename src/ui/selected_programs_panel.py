# src/ui/selected_programs_panel.py
from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QHeaderView
)


class SelectedProgramsPanel(QWidget):
    """
    Dedicated widget for displaying selected study programs (ID and Name).
    Fully read-only component enforcing Jira story acceptance criteria.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(8)

        # Header section for the selected programs details view
        self.title_label = QLabel("Selected Study Programs Details")
        self.title_label.setObjectName("sectionTitleLabel")
        layout.addWidget(self.title_label)

        # Configure the table layout for clean and readable data presentation
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Program Number", "Program Name"])

        # Provide breathing room vertically
        self.table.horizontalHeader().setMinimumHeight(35)

        # Prevent letter clipping by injecting padding via QSS
        self.table.horizontalHeader().setStyleSheet(
            "QHeaderView::section {"
            "    padding-left: 10px;"
            "    padding-right: 10px;"
            "}"
        )

        # Enforce automatic column constraints so text fits perfectly
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        # Enforce read-only behavior to prevent unwanted inline modifications
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

        layout.addWidget(self.table)

    def update_display(self, programs_details: list[dict[str, str]]) -> None:
        """
        Refreshes the table view with updated program metadata.
        Invoked whenever the state layer broadcasts selection or loading modifications.
        """
        self.table.setRowCount(len(programs_details))

        for row, detail in enumerate(programs_details):
            id_item = QTableWidgetItem(detail["program_id"])
            name_item = QTableWidgetItem(detail["display_name"])

            # Center-align cell text contents both horizontally and vertically
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table.setItem(row, 0, id_item)
            self.table.setItem(row, 1, name_item)