
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QHeaderView,
    QSizePolicy,
)


SELECTED_PROGRAMS_TABLE_MIN_HEIGHT = 190


class SelectedProgramsPanel(QWidget):
    """
    Dedicated widget for displaying selected study programs (ID and Name).
    Emits program_detail_requested when a row is clicked.
    """

    program_detail_requested = pyqtSignal(str)  # emits program_id

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(8)

        self.title_label = QLabel("Selected Study Programs Details")
        self.title_label.setObjectName("sectionTitleLabel")
        layout.addWidget(self.title_label)

        hint = QLabel("Click a program to view its courses.")
        hint.setObjectName("panelHintLabel")
        layout.addWidget(hint)

        self.table = QTableWidget()
        self.table.setMinimumHeight(SELECTED_PROGRAMS_TABLE_MIN_HEIGHT)
        self.table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Program Number", "Program Name"])

        self.table.horizontalHeader().setMinimumHeight(35)
        self.table.horizontalHeader().setStyleSheet(
            "QHeaderView::section { padding-left: 10px; padding-right: 10px; }"
        )
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )

        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setCursor(Qt.CursorShape.PointingHandCursor)

        self.table.cellClicked.connect(self._on_cell_clicked)

        layout.addWidget(self.table, 1)

    def update_display(self, programs_details: list[dict[str, str]]) -> None:
        self.table.setRowCount(len(programs_details))

        for row, detail in enumerate(programs_details):
            clean_id = str(detail["program_id"]).strip()

            id_item = QTableWidgetItem(clean_id)
            id_item.setData(Qt.ItemDataRole.UserRole, clean_id)
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            name_item = QTableWidgetItem(detail["display_name"])
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table.setItem(row, 0, id_item)
            self.table.setItem(row, 1, name_item)

    def _on_cell_clicked(self, row: int, _col: int) -> None:
        id_item = self.table.item(row, 0)
        if id_item is None:
            return
        program_id = id_item.data(Qt.ItemDataRole.UserRole)
        if program_id:
            self.program_detail_requested.emit(str(program_id).strip())
