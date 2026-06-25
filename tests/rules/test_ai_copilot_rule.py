from __future__ import annotations

import json
from datetime import date

from src.models.academic import Course, Exam, ProgramAffiliation
from src.models.enums import RequirementType, Semester
from src.rules.ai_copilot_rule import AICopilotRule


def _course(
    course_id: int,
    name: str,
    instructor: str = "Dr. Cohen",
    program_id: int = 83101,
) -> Course:
    return Course(
        course_id=course_id,
        name=name,
        instructor=instructor,
        evaluation=Exam(),
        affiliations=[
            ProgramAffiliation(
                program_id=program_id,
                year=1,
                semester=Semester.FALL,
                requirement_type=RequirementType.OBLIGATORY,
            )
        ],
    )


def _record(rule_id: str, rule_type: str, parameters: dict) -> dict:
    return {
        "rule_id": rule_id,
        "description": f"Test {rule_type} rule",
        "rule_type": rule_type,
        "parameters": parameters,
    }


def _rule_file(tmp_path, records: list[dict]):
    path = tmp_path / "active_ai_rules.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


def test_fix_date_rule_enforces_exact_course_date(tmp_path):
    algorithms = _course(10001, "Algorithms")
    rule = AICopilotRule(
        _rule_file(
            tmp_path,
            [
                _record(
                    "ai_rule_1",
                    "fix_date",
                    {"course": "Algorithms", "date": "2026-01-05"},
                )
            ],
        )
    )

    assert rule.is_valid({algorithms: date(2026, 1, 5)})
    assert not rule.is_valid({algorithms: date(2026, 1, 6)})


def test_exclude_day_and_lecturer_rules_enforce_weekdays(tmp_path):
    algorithms = _course(10001, "Algorithms", "Prof. Cohen")
    physics = _course(10002, "Physics", "Dr. Levi")
    rule = AICopilotRule(
        _rule_file(
            tmp_path,
            [
                _record(
                    "ai_rule_1",
                    "exclude_day",
                    {"course": "Physics", "weekday": "Thursday"},
                ),
                _record(
                    "ai_rule_2",
                    "lecturer_unavailable",
                    {"lecturer": "Cohen", "weekday": "Sunday"},
                ),
            ],
        )
    )

    assert rule.is_valid(
        {
            algorithms: date(2026, 1, 5),
            physics: date(2026, 1, 6),
        }
    )
    assert not rule.is_valid({physics: date(2026, 1, 8)})
    assert not rule.is_valid({algorithms: date(2026, 1, 4)})


def test_program_limit_and_global_spacing_are_enforced(tmp_path):
    algorithms = _course(10001, "Algorithms")
    physics = _course(10002, "Physics")
    rule = AICopilotRule(
        _rule_file(
            tmp_path,
            [
                _record(
                    "ai_rule_1",
                    "program_limit",
                    {"program": "83101", "max_exams_per_day": 1},
                ),
                _record(
                    "ai_rule_2",
                    "exam_spacing",
                    {"min_days": 2},
                ),
            ],
        )
    )

    assert rule.is_valid(
        {
            algorithms: date(2026, 1, 5),
            physics: date(2026, 1, 7),
        }
    )
    assert not rule.is_valid(
        {
            algorithms: date(2026, 1, 5),
            physics: date(2026, 1, 5),
        }
    )
    assert not rule.is_valid(
        {
            algorithms: date(2026, 1, 5),
            physics: date(2026, 1, 6),
        }
    )


def test_month_and_date_range_exclusions_are_enforced(tmp_path):
    algorithms = _course(10001, "Algorithms")
    month_rule = AICopilotRule(
        _rule_file(
            tmp_path,
            [
                _record(
                    "ai_rule_1",
                    "exclude_period",
                    {"month": 1},
                )
            ],
        )
    )

    assert not month_rule.is_valid({algorithms: date(2026, 1, 15)})
    assert month_rule.is_valid({algorithms: date(2026, 2, 1)})

    range_rule = AICopilotRule(
        _rule_file(
            tmp_path,
            [
                _record(
                    "ai_rule_2",
                    "exclude_period",
                    {
                        "start_date": "2026-03-10",
                        "end_date": "2026-03-20",
                    },
                )
            ],
        )
    )
    assert not range_rule.is_valid({algorithms: date(2026, 3, 15)})
    assert range_rule.is_valid({algorithms: date(2026, 3, 21)})


def test_tampered_records_are_rejected_without_disabling_valid_rules(tmp_path):
    rules_path = _rule_file(
        tmp_path,
        [
            _record(
                "ai_rule_1",
                "exclude_day",
                {"weekday": "Thursday"},
            ),
            {
                **_record(
                    "ai_rule_2",
                    "program_limit",
                    {"program": "Computer Science", "max_exams_per_day": 1},
                ),
                "command": "DROP TABLE schedules",
            },
        ],
    )

    rule = AICopilotRule(rules_path)

    assert [item["rule_id"] for item in rule.ai_constraints] == ["ai_rule_1"]
    assert not rule.is_valid({_course(10001, "Algorithms"): date(2026, 1, 8)})


def test_missing_or_invalid_file_is_fail_closed_for_ai_data_only(tmp_path):
    missing_rule = AICopilotRule(tmp_path / "missing.json")
    assert missing_rule.ai_constraints == []
    assert missing_rule.is_valid({_course(10001, "Algorithms"): date(2026, 1, 5)})

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text('{"not":"a list"}', encoding="utf-8")
    invalid_rule = AICopilotRule(invalid_path)
    assert invalid_rule.ai_constraints == []
