from PyQt6.QtCore import Qt
from src.services.selected_programs_service import SelectedProgramsViewModel
from src.ui.selected_programs_panel import SelectedProgramsPanel


def test_view_model_fallback_mapping():
    """Confirms that the ViewModel correctly maps baseline selection IDs into official English names."""
    vm = SelectedProgramsViewModel()
    vm.set_selected_program_ids(["83101", "83107"])

    details = vm.get_selected_program_details()

    assert len(details) == 2
    assert details[0]["program_id"] == "83101"
    assert details[0]["display_name"] == "Computer Engineering"
    assert details[1]["program_id"] == "83107"
    assert details[1]["display_name"] == "Data Engineering"


def test_panel_display_update(qtbot):
    """Confirms that the read-only UI panel displays data inputs correctly and applies center alignments."""
    panel = SelectedProgramsPanel()
    qtbot.addWidget(panel)

    mock_details = [
        {"program_id": "83104", "display_name": "Industrial Engineering and Information Systems"}
    ]

    panel.update_display(mock_details)

    assert panel.table.rowCount() == 1
    assert panel.table.item(0, 0).text() == "83104"
    assert panel.table.item(0, 1).text() == "Industrial Engineering and Information Systems"
    assert panel.table.item(0, 0).textAlignment() == Qt.AlignmentFlag.AlignCenter