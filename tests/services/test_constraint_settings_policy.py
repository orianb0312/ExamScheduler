"""Tests for the pure constraint validation policy.

"""

import pytest

from src.services.constraint_settings_policy import (
    CONSTRAINTS_BY_KEY,
    DEFAULT_CONSTRAINT_SETTINGS_POLICY,
)


POLICY = DEFAULT_CONSTRAINT_SETTINGS_POLICY


def test_positive_constraints_reject_zero_and_negative():
    """2.1, 2.2, 2.4, 2.5 require a strictly positive whole number."""
    for key in (
        "min_days_between_mandatory",
        "min_days_between_any",
        "min_days_before_last_mandatory",
        "max_exams_per_day",
    ):
        definition = CONSTRAINTS_BY_KEY[key]
        assert POLICY.validate_value(definition, True, "1").is_valid
        assert not POLICY.validate_value(definition, True, "0").is_valid
        assert not POLICY.validate_value(definition, True, "-4").is_valid


def test_max_elective_conflicts_allows_zero():
    """2.3 is the only constraint that accepts zero, but still rejects negatives."""
    definition = CONSTRAINTS_BY_KEY["max_elective_conflicts"]
    assert POLICY.validate_value(definition, True, "0").is_valid
    assert POLICY.validate_value(definition, True, "5").is_valid
    assert not POLICY.validate_value(definition, True, "-1").is_valid


def test_enabled_constraint_requires_a_whole_number():
    """An enabled constraint must carry a non-empty integer value."""
    definition = CONSTRAINTS_BY_KEY["min_days_between_mandatory"]
    assert not POLICY.validate_value(definition, True, "").is_valid
    assert not POLICY.validate_value(definition, True, "   ").is_valid
    assert not POLICY.validate_value(definition, True, "3.5").is_valid
    assert not POLICY.validate_value(definition, True, "abc").is_valid


def test_disabled_constraint_is_always_valid_and_ignored():
    """A disabled constraint never errors, even with junk text, and has no value."""
    definition = CONSTRAINTS_BY_KEY["max_exams_per_day"]
    result = POLICY.validate_value(definition, False, "not a number")
    assert result.is_valid
    assert result.value is None
    assert result.enabled is False


def test_sanitized_parameters_keeps_only_enabled_and_valid():
    """validate_all yields a clean mapping of just the enabled, valid values."""
    states = {
        "min_days_between_mandatory": (True, "3"),    # valid -> kept
        "min_days_between_any": (False, "9"),         # disabled -> dropped
        "max_elective_conflicts": (True, "0"),        # valid zero -> kept
        "min_days_before_last_mandatory": (True, ""), # enabled but empty -> dropped
        "max_exams_per_day": (True, "2"),             # valid -> kept
    }
    validation = POLICY.validate_all(states)

    assert not validation.is_valid  # the empty 2.4 makes the whole set invalid
    assert validation.sanitized_parameters() == {
        "min_days_between_mandatory": 3,
        "max_elective_conflicts": 0,
        "max_exams_per_day": 2,
    }