from __future__ import annotations

import json

from src.ui.main_window import MainWindow


def test_main_window_persists_and_reloads_ai_rules_via_widget_signal(
    tmp_path,
    qtbot,
):
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)
    rules_path = (tmp_path / "data" / "active_ai_rules.json").resolve()

    assert rules_path.is_file()
    assert json.loads(rules_path.read_text(encoding="utf-8")) == []

    window.input_panel._handle_ai_copilot_constraint(
        {"action": "exclude_day", "weekday": "Thursday"}
    )

    saved_rules = json.loads(rules_path.read_text(encoding="utf-8"))
    assert saved_rules == [
        {
            "rule_id": "ai_rule_1",
            "description": "Exclude Thursday from exam scheduling",
            "rule_type": "exclude_day",
            "parameters": {"weekday": "Thursday"},
        }
    ]

    restored_window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(restored_window)
    assert restored_window.input_panel.ai_copilot_rules == {
        "ai_rule_1": {
            "description": "Exclude Thursday from exam scheduling",
            "rule_type": "exclude_day",
            "parameters": {"weekday": "Thursday"},
        }
    }

    restored_window.input_panel._handle_ai_copilot_constraint(
        {
            "action": "fix_date",
            "course": "Algorithms",
            "date": "2026-07-15",
        }
    )
    assert [
        rule["rule_id"]
        for rule in json.loads(rules_path.read_text(encoding="utf-8"))
    ] == ["ai_rule_1", "ai_rule_2"]

    restored_window.input_panel._handle_ai_copilot_constraint(
        {"action": "revert_rule", "rule_id": "ai_rule_1"}
    )
    remaining_rules = json.loads(rules_path.read_text(encoding="utf-8"))
    assert [rule["rule_id"] for rule in remaining_rules] == ["ai_rule_2"]


def test_main_window_ignores_invalid_persistence_events(tmp_path, qtbot):
    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)
    rules_path = (tmp_path / "data" / "active_ai_rules.json").resolve()

    window.handle_new_ai_constraint(
        {
            "operation": "upsert",
            "rule": {
                "rule_id": "base_rule",
                "description": "Remove base rules",
                "rule_type": "exclude_day",
                "parameters": {"weekday": "Thursday"},
            },
        }
    )

    assert json.loads(rules_path.read_text(encoding="utf-8")) == []
