import pytest

from src.services.constraint_settings_policy import (
    CONSTRAINTS_BY_KEY,
    DEFAULT_CONSTRAINT_SETTINGS_POLICY,
)


POLICY = DEFAULT_CONSTRAINT_SETTINGS_POLICY

# Part 3 says these k values must be strictly positive.
POSITIVE_K_REQUIREMENTS = [
    ("2.1", "min_days_between_mandatory"),
    ("2.2", "min_days_between_any"),
    ("2.4", "min_days_before_last_mandatory"),
    ("2.5", "max_exams_per_day"),
]


@pytest.mark.parametrize(("requirement", "key"), POSITIVE_K_REQUIREMENTS)
@pytest.mark.parametrize("raw_k", ["0", "-1"])
def test_part3_positive_k_requirements_reject_zero_and_negative(
    requirement: str,
    key: str,
    raw_k: str,
):
    definition = CONSTRAINTS_BY_KEY[key]

    result = POLICY.validate_value(definition, enabled=True, raw_value=raw_k)

    assert definition.code == requirement
    assert not result.is_valid
    assert result.value is None
    assert result.error == "Value must be a positive whole number."


def test_part3_req_2_3_accepts_zero_k():
    # Req 2.3 is the only Part 3 constraint where zero is a valid k.
    definition = CONSTRAINTS_BY_KEY["max_elective_conflicts"]

    result = POLICY.validate_value(definition, enabled=True, raw_value="0")

    assert definition.code == "2.3"
    assert result.is_valid
    assert result.value == 0


def test_part3_req_2_3_rejects_negative_k():
    definition = CONSTRAINTS_BY_KEY["max_elective_conflicts"]

    result = POLICY.validate_value(definition, enabled=True, raw_value="-1")

    assert definition.code == "2.3"
    assert not result.is_valid
    assert result.value is None
    assert result.error == "Value must be zero or a positive whole number."
