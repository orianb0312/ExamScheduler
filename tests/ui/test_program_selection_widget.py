import pytest
from PyQt6.QtCore import Qt
from src.services.program_selection_policy import DEFAULT_PROGRAM_SELECTION_POLICY
from src.ui.program_selection_widget import (
    LIMIT_MESSAGE,
    MAX_SELECTED_PROGRAMS,
    PROGRAM_ID_ROLE,
    ProgramSelectionWidget,
)


@pytest.fixture
def combo_box(qtbot):
    widget = ProgramSelectionWidget()
    qtbot.addWidget(widget)
    return widget


def _item_is_enabled(item) -> bool:
    return bool(item.flags() & Qt.ItemFlag.ItemIsEnabled)


def test_load_data_displays_all_program_names_and_identifiers(combo_box):
    # Full Version 1 data (all 10 identifiers)
    version_1_data = ["83101", "83102", "83104", "83107", "83108", "83109", "83105", "83182", "83103", "83115"]

    combo_box.add_programs(version_1_data)

    # Verify all items are loaded using QListWidget's count()
    assert combo_box.count() == len(version_1_data)

    for i, expected_id in enumerate(version_1_data):
        item = combo_box.item(i)
        assert item.data(PROGRAM_ID_ROLE) == expected_id
        assert item.text() == expected_id


def test_add_programs_preserves_existing_identifiers(combo_box):
    combo_box.add_programs(["83101", "83102"])

    combo_box.add_programs(["83102", "83109"])

    assert [combo_box.item(index).data(PROGRAM_ID_ROLE) for index in range(combo_box.count())] == [
        "83101",
        "83102",
        "83109",
    ]


def test_set_programs_replaces_existing_identifiers(combo_box):
    combo_box.add_programs(["83101", "83102", "83109"])

    combo_box.set_programs(["83115"])

    assert combo_box.count() == 1
    assert combo_box.item(0).data(PROGRAM_ID_ROLE) == "83115"
    assert combo_box.item(0).text() == "83115"


def test_selecting_one_program_records_only_that_program(combo_box):
    combo_box.add_programs(["83101", "83102", "83103"])

    combo_box.item(0).setCheckState(Qt.CheckState.Checked)

    assert combo_box.get_selected_items() == ["83101"]


def test_selection_count_signal_tracks_choices_out_of_five(combo_box):
    counts = []
    combo_box.selectionCountChanged.connect(
        lambda selected, max_selected: counts.append((selected, max_selected))
    )
    combo_box.add_programs(["83101", "83102", "83103", "83104", "83105", "83106"])

    combo_box.item(0).setCheckState(Qt.CheckState.Checked)
    combo_box.item(1).setCheckState(Qt.CheckState.Checked)
    combo_box.item(2).setCheckState(Qt.CheckState.Checked)

    assert counts[-4:] == [
        (0, MAX_SELECTED_PROGRAMS),
        (1, MAX_SELECTED_PROGRAMS),
        (2, MAX_SELECTED_PROGRAMS),
        (3, MAX_SELECTED_PROGRAMS),
    ]


def test_selecting_five_programs_disables_additional_choices(combo_box):
    messages = []
    combo_box.limitMessageChanged.connect(messages.append)
    combo_box.add_programs(["83101", "83102", "83103", "83104", "83105", "83106"])

    assert MAX_SELECTED_PROGRAMS == DEFAULT_PROGRAM_SELECTION_POLICY.max_selected

    for index in range(MAX_SELECTED_PROGRAMS):
        combo_box.item(index).setCheckState(Qt.CheckState.Checked)

    assert combo_box.get_selected_items() == ["83101", "83102", "83103", "83104", "83105"]
    assert messages[-1] == LIMIT_MESSAGE
    assert not _item_is_enabled(combo_box.item(5))


def test_trying_to_select_a_sixth_program_keeps_selection_at_five(combo_box):
    messages = []
    combo_box.limitMessageChanged.connect(messages.append)
    combo_box.add_programs(["83101", "83102", "83103", "83104", "83105", "83106"])

    for index in range(MAX_SELECTED_PROGRAMS):
        combo_box.item(index).setCheckState(Qt.CheckState.Checked)

    combo_box.item(5).setFlags(combo_box.item(5).flags() | Qt.ItemFlag.ItemIsEnabled)
    combo_box.item(5).setCheckState(Qt.CheckState.Checked)

    assert combo_box.get_selected_items() == ["83101", "83102", "83103", "83104", "83105"]
    assert combo_box.item(5).checkState() == Qt.CheckState.Unchecked
    assert messages[-1] == LIMIT_MESSAGE


def test_deselecting_one_program_reenables_remaining_choices(combo_box):
    messages = []
    combo_box.limitMessageChanged.connect(messages.append)
    combo_box.add_programs(["83101", "83102", "83103", "83104", "83105", "83106"])

    for index in range(MAX_SELECTED_PROGRAMS):
        combo_box.item(index).setCheckState(Qt.CheckState.Checked)

    combo_box.item(0).setCheckState(Qt.CheckState.Unchecked)

    assert combo_box.get_selected_items() == ["83102", "83103", "83104", "83105"]
    assert _item_is_enabled(combo_box.item(5))
    assert messages[-1] == ""