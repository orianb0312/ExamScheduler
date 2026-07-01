import json
from pathlib import Path

from tools.ai_model_benchmark import (
    BenchmarkCase,
    build_prompt,
    load_cases,
    parse_json_object,
    score_parsed,
    validate_cases,
)


CASES_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "ai_model_benchmark_cases.json"
)


def test_benchmark_cases_are_english_only_and_have_unique_ids():
    cases = load_cases(CASES_PATH)

    validate_cases(cases)
    assert len(cases) >= 30
    assert all(case.request.isascii() for case in cases)


def test_benchmark_prompt_includes_context_and_user_request():
    case = BenchmarkCase(
        id="revert_rule",
        category="rule_management",
        request="Allow exams on Fridays again",
        expected={"action": "revert_rule", "rule_id": "ai_rule_1"},
        context={
            "chatbot_rules": {
                "ai_rule_1": {
                    "description": "Exclude Friday from exam scheduling",
                    "rule_type": "exclude_day",
                    "parameters": {"weekday": "Friday"},
                }
            }
        },
    )

    prompt = build_prompt(case)

    assert "Allow exams on Fridays again" in prompt
    assert "ai_rule_1" in prompt
    assert "Return only one JSON object" in prompt
    assert "Minimum gap 5 days" in prompt
    assert "tests and finals mean exams" in prompt


def test_strict_json_parser_rejects_duplicate_keys():
    parsed, is_valid, reason = parse_json_object(
        '{"action":"exclude_day","action":"fix_date","weekday":"Sunday"}'
    )

    assert parsed is None
    assert is_valid is False
    assert reason.startswith("invalid_json")


def test_exact_score_rewards_precise_rule_match():
    case = BenchmarkCase(
        id="fix_date",
        category="supported_fix_date",
        request="Schedule Physics on 2026-07-15",
        expected={"action": "fix_date", "course": "Physics", "date": "2026-07-15"},
    )
    parsed = {"action": "fix_date", "course": "Physics", "date": "2026-07-15"}

    score, reason = score_parsed(case, parsed, json_valid=True, schema_valid=True, json_reason="json_ok")

    assert score == 2
    assert reason == "exact_match"


def test_exact_score_gives_partial_credit_for_wrong_details():
    case = BenchmarkCase(
        id="fix_date",
        category="supported_fix_date",
        request="Schedule Physics on 2026-07-15",
        expected={"action": "fix_date", "course": "Physics", "date": "2026-07-15"},
    )
    parsed = {"action": "fix_date", "course": "Physics", "date": "2026-07-16"}

    score, reason = score_parsed(case, parsed, json_valid=True, schema_valid=True, json_reason="json_ok")

    assert score == 1
    assert reason == "same_intent_wrong_details"


def test_action_score_accepts_english_clarification_message():
    case = BenchmarkCase(
        id="clarify",
        category="clarification",
        request="Schedule Physics tomorrow",
        expected={"action": "clarify"},
        match="action",
        required_keys=("message",),
    )
    parsed = {
        "action": "clarify",
        "message": "Which exact ISO date should Physics use?",
    }

    score, reason = score_parsed(case, parsed, json_valid=True, schema_valid=True, json_reason="json_ok")

    assert score == 2
    assert reason == "action_match"


def test_case_file_is_valid_json():
    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    assert data["version"] == 1
    assert data["default_models"]
