import json

import pytest

from src.parser.constraint_file_parser import (
    EXPECTED_CONSTRAINT_KEYS,
    parse_constraints_text,
)
from src.parser.file_parser import FileParser


def _disabled_constraints() -> dict[str, str]:
    # Start from the safest file: every constraint present but turned off.
    return {key: "-" for key in EXPECTED_CONSTRAINT_KEYS}


def _constraints_text(values: dict[str, str]) -> str:
    return "\n".join(f"$$$$\n{key}\n{value}" for key, value in values.items()) + "\n"


def _records_text(records: list[tuple[str, str]]) -> str:
    return "\n".join(f"$$$$\n{key}\n{value}" for key, value in records) + "\n"


def test_parse_constraints_text_matches_by_key_and_skips_disabled():
    # The order is mixed on purpose; identity must come from the key name.
    text = _records_text(
        [
            ("max_exams_per_day", "2"),
            ("min_days_between_any", "-"),
            ("max_elective_conflicts", "0"),
            ("min_days_before_last_mandatory", "-"),
            ("min_days_between_mandatory", "3"),
        ]
    )

    assert parse_constraints_text(text) == {
        "min_days_between_mandatory": 3,
        "max_elective_conflicts": 0,
        "max_exams_per_day": 2,
    }


@pytest.mark.parametrize(
    "key",
    [
        "min_days_between_mandatory",
        "min_days_between_any",
        "min_days_before_last_mandatory",
        "max_exams_per_day",
    ],
)
@pytest.mark.parametrize("bad_value", ["0", "-1"])
def test_positive_constraints_reject_zero_and_negative_from_file(
    key: str,
    bad_value: str,
):
    # These four requirements say "positive", so zero is not good enough.
    values = _disabled_constraints()
    values[key] = bad_value

    with pytest.raises(ValueError, match=key):
        parse_constraints_text(_constraints_text(values))


def test_max_elective_conflicts_allows_zero_but_rejects_negative_from_file():
    # Requirement 2.3 is the one special case where zero is allowed.
    values = _disabled_constraints()
    values["max_elective_conflicts"] = "0"

    assert parse_constraints_text(_constraints_text(values)) == {
        "max_elective_conflicts": 0
    }

    values["max_elective_conflicts"] = "-1"
    with pytest.raises(ValueError, match="max_elective_conflicts"):
        parse_constraints_text(_constraints_text(values))


def test_parse_constraints_text_rejects_missing_duplicate_and_unknown_keys():
    # Missing chunks are rejected so a file cannot silently skip a rule.
    values = _disabled_constraints()
    values.pop("max_exams_per_day")
    with pytest.raises(ValueError, match="Missing constraint key"):
        parse_constraints_text(_constraints_text(values))

    # Duplicate chunks are rejected because "last value wins" would be too loose.
    records = [(key, "-") for key in EXPECTED_CONSTRAINT_KEYS]
    records.append(("min_days_between_mandatory", "3"))
    with pytest.raises(ValueError, match="Duplicate constraint key"):
        parse_constraints_text(_records_text(records))

    # Unknown names are rejected so typos fail loudly.
    values = _disabled_constraints()
    values["made_up_constraint"] = "1"
    with pytest.raises(ValueError, match="Unknown constraint key"):
        parse_constraints_text(_constraints_text(values))


def test_file_parser_includes_sanitized_constraints_node(tmp_path):
    # This covers the full FileParser path, not only the small helper parser.
    course_file = tmp_path / "courses.txt"
    dates_file = tmp_path / "dates.txt"
    user_file = tmp_path / "programs.txt"
    constraints_file = tmp_path / "constraints.txt"

    course_file.write_text(
        "\n".join(
            [
                "$$$$",
                "Intro to Scheduling",
                "10001",
                "Dr. Parser",
                "83101,1,FALL,Obligatory",
                "Exam",
            ]
        ),
        encoding="utf-8",
    )
    dates_file.write_text(
        "\n".join(
            [
                "$$$$",
                "FALL,Aleph",
                "01-01-2026, 02-01-2026",
                "02-01-2026 Blocked",
            ]
        ),
        encoding="utf-8",
    )
    user_file.write_text("83101", encoding="utf-8")

    values = _disabled_constraints()
    values["min_days_between_mandatory"] = "2"
    values["max_elective_conflicts"] = "0"
    constraints_file.write_text(_constraints_text(values), encoding="utf-8")

    parsed = json.loads(
        FileParser().parse_to_json(
            {
                "course_file": str(course_file),
                "dates_file": str(dates_file),
                "user_file": str(user_file),
                "constraints_file": str(constraints_file),
            }
        )
    )

    assert parsed["constraints_node"] == {
        "min_days_between_mandatory": 2,
        "max_elective_conflicts": 0,
    }


def test_file_parser_includes_sorting_priority_node(tmp_path):
    course_file = tmp_path / "courses.txt"
    dates_file = tmp_path / "dates.txt"
    user_file = tmp_path / "programs.txt"
    sorting_file = tmp_path / "sorting.txt"

    course_file.write_text(
        "\n".join(
            [
                "$$$$",
                "Intro to Scheduling",
                "10001",
                "Dr. Parser",
                "83101,1,FALL,Obligatory",
                "Exam",
            ]
        ),
        encoding="utf-8",
    )
    dates_file.write_text(
        "\n".join(
            [
                "$$$$",
                "FALL,Aleph",
                "01-01-2026, 02-01-2026",
                "02-01-2026 Blocked",
            ]
        ),
        encoding="utf-8",
    )
    user_file.write_text("83101", encoding="utf-8")
    sorting_file.write_text(
        "$$$$\nsorting_priority\n3.5\nmandatory_min_gap\n",
        encoding="utf-8",
    )

    parsed = json.loads(
        FileParser().parse_to_json(
            {
                "course_file": str(course_file),
                "dates_file": str(dates_file),
                "user_file": str(user_file),
                "sorting_file": str(sorting_file),
            }
        )
    )

    assert parsed["sorting_node"] == [
        "max_daily_exams",
        "mandatory_min_gap",
    ]
