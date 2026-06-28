from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
)

from src.services.program_selection_policy import (
    DEFAULT_PROGRAM_SELECTION_POLICY,
    ProgramSelectionPolicy,
)

MAX_SELECTED_PROGRAMS = DEFAULT_PROGRAM_SELECTION_POLICY.max_selected
LIMIT_MESSAGE = DEFAULT_PROGRAM_SELECTION_POLICY.limit_message
PROGRAM_ID_ROLE = Qt.ItemDataRole.UserRole


class ProgramSelectionWidget(QListWidget):
    """
    A custom list widget with checkable items representing study programs.
    Enforces selection limits defined by the program selection policy.
    """
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
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumHeight(180)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
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
        """Replaces the visible program identifiers completely."""
        self.blockSignals(True)
        self.clear()
        self.blockSignals(False)
        self.limitMessageChanged.emit("")
        self.add_programs(programs)

    def _create_item(self, text: str) -> QListWidgetItem:
        """Creates a checkable list item showing the raw 5-digit code."""
        program_id = str(text).strip()
        item = QListWidgetItem(program_id)
        item.setData(PROGRAM_ID_ROLE, program_id)
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled |
            Qt.ItemFlag.ItemIsUserCheckable
        )
        item.setCheckState(Qt.CheckState.Unchecked)
        return item

    def mouseReleaseEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        previous_state = item.checkState() if item is not None else None

        super().mouseReleaseEvent(event)

        if item is None or not _item_is_enabled(item):
            return

        # Qt already toggles real checkbox clicks, so only row/text clicks need
        # this manual toggle.
        if item.checkState() == previous_state:
            item.setCheckState(_opposite_check_state(item.checkState()))

    def get_selected_items(self) -> list[str]:
        """Returns a list of all currently checked program identifiers."""
        return [
            self._program_id_for_item(self.item(i))
            for i in range(self.count())
            if self.item(i).checkState() == Qt.CheckState.Checked
        ]

    def get_selected_program_ids(self) -> list[str]:
        """Alias for get_selected_items used by InputPanel.notify_data_loaded."""
        return self.get_selected_items()

    def _on_item_changed(self, item: QListWidgetItem):
        """Keeps the program selection inside the allowed policy boundaries."""
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
        """Disables unselected items if the maximum allowed limit is reached."""
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

    def _set_item_checked(self, item: QListWidgetItem, checked: bool):
        """Safely alters an item's check state without re-triggering signal evaluation loops."""
        self._updating_item_state = True
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self._updating_item_state = False

    @staticmethod
    def _set_item_enabled(item: QListWidgetItem, enabled: bool):
        """Toggles the enabled flag state of a specific list item."""
        flags = item.flags()
        if enabled:
            item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled)
        else:
            item.setFlags(flags & ~Qt.ItemFlag.ItemIsEnabled)

    @staticmethod
    def _program_id_for_item(item: QListWidgetItem) -> str:
        """Extracts the unique program identifier stored inside the custom user data role."""
        value = item.data(PROGRAM_ID_ROLE)
        return str(value) if value is not None else item.text()


def _item_is_enabled(item: QListWidgetItem) -> bool:
    return bool(item.flags() & Qt.ItemFlag.ItemIsEnabled)


def _opposite_check_state(state: Qt.CheckState) -> Qt.CheckState:
    return (
        Qt.CheckState.Unchecked
        if state == Qt.CheckState.Checked
        else Qt.CheckState.Checked
    )
