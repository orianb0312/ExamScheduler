import sys
from PyQt6.QtWidgets import QListWidget, QAbstractItemView, QApplication, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal


class ProgramSelectionWidget(QListWidget):
    programSelectionChanged = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.itemChanged.connect(self._on_item_changed)

    def add_programs(self, programs: list[str]):
        """Populates the list widget with program identifiers as checkboxes."""
        self.blockSignals(True)
        self.clear()

        for program in programs:
            item = self._create_item(program)
            self.addItem(item)

        self.blockSignals(False)
        self.programSelectionChanged.emit([])

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
        """Emits the updated selection list."""
        self.programSelectionChanged.emit(self.get_selected_items())


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