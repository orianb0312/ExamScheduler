import sys
from PyQt6.QtWidgets import QListWidget, QAbstractItemView, QApplication, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal


MAX_SELECTED_PROGRAMS = 5
LIMIT_MESSAGE = "You have reached the limit, you can select up to 5 study programs."


class ProgramSelectionWidget(QListWidget):
    programSelectionChanged = pyqtSignal(list)
    limitMessageChanged = pyqtSignal(str)
    selectionCountChanged = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
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
            self.item(index).text()
            for index in range(self.count())
        }

        for program in programs:
            if program in existing_programs:
                continue
            item = self._create_item(program)
            self.addItem(item)
            existing_programs.add(program)

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
        from PyQt6.QtWidgets import QListWidgetItem
        item = QListWidgetItem(text)
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled |
            Qt.ItemFlag.ItemIsUserCheckable
        )
        item.setCheckState(Qt.CheckState.Unchecked)
        return item

    def get_selected_items(self) -> list[str]:
        """Returns a list of all currently checked program identifiers."""
        return [
            self.item(i).text()
            for i in range(self.count())
            if self.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _on_item_changed(self, item):
        """Keeps the program selection inside the allowed Phase 2 limit."""
        if self._updating_item_state:
            return

        if item.checkState() == Qt.CheckState.Checked and len(self.get_selected_items()) > MAX_SELECTED_PROGRAMS:
            # A disabled item should not be selectable by hand, but this also
            # protects us from programmatic changes and future UI tweaks.
            self._set_item_checked(item, False)

        self._sync_limit_state()
        self.programSelectionChanged.emit(self.get_selected_items())

    def _sync_limit_state(self):
        selected_count = len(self.get_selected_items())
        limit_reached = selected_count >= MAX_SELECTED_PROGRAMS

        self._updating_item_state = True
        try:
            for index in range(self.count()):
                item = self.item(index)
                is_checked = item.checkState() == Qt.CheckState.Checked
                self._set_item_enabled(item, is_checked or not limit_reached)
        finally:
            self._updating_item_state = False

        self.limitMessageChanged.emit(LIMIT_MESSAGE if limit_reached else "")
        self.selectionCountChanged.emit(selected_count, MAX_SELECTED_PROGRAMS)

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


# --- Execution Block for Visual Verification (MVP) ---
if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = QWidget()
    window.setWindowTitle("MVP - Program Selection Area")
    layout = QVBoxLayout(window)

    program_selector = ProgramSelectionWidget()

    version_1_data = [
        "83101", "83102", "83104", "83107", "83108",
        "83109", "83105", "83182", "83103", "83115"
    ]

    program_selector.add_programs(version_1_data)

    program_selector.programSelectionChanged.connect(
        lambda ids: print(f"Selected: {ids}")
    )

    layout.addWidget(program_selector)
    window.resize(300, 250)
    window.show()

    sys.exit(app.exec())
