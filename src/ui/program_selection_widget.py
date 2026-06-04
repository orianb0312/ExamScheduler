from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem

from src.services.program_selection_policy import (
    DEFAULT_PROGRAM_SELECTION_POLICY,
    ProgramSelectionPolicy,
)


MAX_SELECTED_PROGRAMS = DEFAULT_PROGRAM_SELECTION_POLICY.max_selected
LIMIT_MESSAGE = DEFAULT_PROGRAM_SELECTION_POLICY.limit_message
PROGRAM_ID_ROLE = Qt.ItemDataRole.UserRole


class ProgramSelectionWidget(QListWidget):
    programSelectionChanged = pyqtSignal(list)
    limitMessageChanged = pyqtSignal(str)
    selectionCountChanged = pyqtSignal(int, int)

    def __init__(
        self,
        parent=None,
        policy: ProgramSelectionPolicy | None = None,
    ):
        super().__init__(parent)
        self._policy = policy or DEFAULT_PROGRAM_SELECTION_POLICY
        self._updating_item_state = False
        self.setObjectName("programSelector")
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setMinimumHeight(180)
        self.setMaximumHeight(260)
        self.itemChanged.connect(self._on_item_changed)

    def add_programs(self, programs: list[str]):
        """Adds missing program identifiers as checkboxes."""
        self.blockSignals(True)
        existing_programs = {
            self._program_id_for_item(self.item(index))
            for index in range(self.count())
        }

        for program in programs:
            program_id = str(program)
            if program_id in existing_programs:
                continue
            item = self._create_item(program_id)
            self.addItem(item)
            existing_programs.add(program_id)

        self.blockSignals(False)
        self._sync_limit_state()
        self.programSelectionChanged.emit(self.get_selected_items())

    def set_programs(self, programs: list[str]):
        """Replaces the visible program identifiers."""
        self.blockSignals(True)
        self.clear()
        self.blockSignals(False)
        self.limitMessageChanged.emit("")
        self.add_programs(programs)

    def _create_item(self, text: str):
        item = QListWidgetItem(f"Program {text} ({text})")
        item.setData(PROGRAM_ID_ROLE, text)
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled |
            Qt.ItemFlag.ItemIsUserCheckable
        )
        item.setCheckState(Qt.CheckState.Unchecked)
        return item

    def get_selected_items(self) -> list[str]:
        """Returns a list of all currently checked program identifiers."""
        return [
            self._program_id_for_item(self.item(i))
            for i in range(self.count())
            if self.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _on_item_changed(self, item):
        """Keeps the program selection inside the allowed Phase 2 limit."""
        if self._updating_item_state:
            return

        selected_count = len(self.get_selected_items())
        if (
            item.checkState() == Qt.CheckState.Checked
            and not self._policy.is_selection_count_allowed(selected_count)
        ):
            self._set_item_checked(item, False)

        self._sync_limit_state()
        self.programSelectionChanged.emit(self.get_selected_items())

    def _sync_limit_state(self):
        selected_count = len(self.get_selected_items())
        limit_reached = self._policy.is_limit_reached(selected_count)

        self._updating_item_state = True
        try:
            for index in range(self.count()):
                item = self.item(index)
                is_checked = item.checkState() == Qt.CheckState.Checked
                self._set_item_enabled(item, is_checked or not limit_reached)
        finally:
            self._updating_item_state = False

        self.limitMessageChanged.emit(self._policy.message_for_count(selected_count))
        self.selectionCountChanged.emit(selected_count, self._policy.max_selected)

    def _set_item_checked(self, item, checked: bool):
        self._updating_item_state = True
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self._updating_item_state = False

    @staticmethod
    def _set_item_enabled(item, enabled: bool):
        flags = item.flags()
        if enabled:
            item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled)
        else:
            item.setFlags(flags & ~Qt.ItemFlag.ItemIsEnabled)

    @staticmethod
    def _program_id_for_item(item) -> str:
        value = item.data(PROGRAM_ID_ROLE)
        return str(value) if value is not None else item.text()
