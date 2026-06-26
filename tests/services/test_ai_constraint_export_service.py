import json

import pytest

from src.rules.ai_copilot_rule import AICopilotRule
from src.services.ai_constraint_export_service import export_ai_constraint


def test_export_ai_constraint_writes_solver_schema(tmp_path):
    destination = tmp_path / "active_ai_rules.json"

    result = export_ai_constraint(
        '{"action":"exclude_day","weekday":"Friday"}',
        destination,
        AICopilotRule.validate_rule_record,
    )

    assert result == destination.resolve()
    assert json.loads(destination.read_text(encoding="utf-8")) == [
        {
            "rule_id": "ai_rule_1",
            "description": "Exclude Friday",
            "rule_type": "exclude_day",
            "parameters": {"weekday": "Friday"},
        }
    ]


@pytest.mark.parametrize(
    "payload",
    [
        '{"action":"program_limit","program":"83101","max_exams_per_day":0}',
        '{"action":"exam_spacing","min_days":0}',
        '{"action":"exclude_day","weekday":"Friday","unknown":1}',
        '{"action":"exclude_day","action":"fix_date"}',
    ],
)
def test_export_ai_constraint_rejects_invalid_or_ambiguous_json(
    payload,
    tmp_path,
):
    with pytest.raises(ValueError):
        export_ai_constraint(
            payload,
            tmp_path / "active_ai_rules.json",
            AICopilotRule.validate_rule_record,
        )
