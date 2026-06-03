import pytest
from PyQt6.QtCore import Qt
from src.ui.program_selection_widget import ProgramSelectionWidget


@pytest.fixture
def combo_box(qtbot):
    widget = ProgramSelectionWidget()
    qtbot.addWidget(widget)
    return widget


def test_load_data_displays_all_identifiers(combo_box):
    # Full Version 1 data (all 10 identifiers)
    version_1_data = ["83101", "83102", "83104", "83107", "83108", "83109", "83105", "83182", "83103", "83115"]

    combo_box.add_programs(version_1_data)

    # Verify all items are loaded using QListWidget's count()
    assert combo_box.count() == len(version_1_data)

    # Verify that each item text matches the expected identifier exactly
    for i, expected_id in enumerate(version_1_data):
        assert combo_box.item(i).text() == expected_id

