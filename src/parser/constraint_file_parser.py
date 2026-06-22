"""Parser for V1 file-based scheduling constraint settings."""

from __future__ import annotations

from src.services.constraint_settings_policy import (
    CONSTRAINT_DEFINITIONS,
    CONSTRAINTS_BY_KEY,
    DEFAULT_CONSTRAINT_SETTINGS_POLICY,
    ConstraintSettingsPolicy,
)
from src.services.day_status_service import CONSTRAINT_DISABLED_MARKER


# Same chunk marker used by the existing V1 text files.
RECORD_SEPARATOR = "$$$$"

# Keep the file contract tied to the single source of constraint definitions.
EXPECTED_CONSTRAINT_KEYS: tuple[str, ...] = tuple(
    definition.key for definition in CONSTRAINT_DEFINITIONS
)


def parse_constraints_text(
    text: str,
    policy: ConstraintSettingsPolicy = DEFAULT_CONSTRAINT_SETTINGS_POLICY,
) -> dict[str, int]:
    """Parse and validate a V1 constraints file into enabled key -> k values.

    A chunk contains exactly two non-empty lines: the constraint key and either
    its integer k value or "-" when the constraint is disabled. Keys are matched
    by name so files may be written in any order.
    """
    records = _split_records(text)
    if not records:
        raise ValueError("Constraints file is empty.")

    # The shared policy expects the same shape the GUI uses: enabled flag + raw text.
    states: dict[str, tuple[bool, str]] = {}
    for record in records:
        key, raw_value = _parse_constraint_record(record)

        # Hand-edited files must not invent new constraint names.
        if key not in CONSTRAINTS_BY_KEY:
            raise ValueError(f"Unknown constraint key: '{key}'.")

        # A duplicate key is ambiguous, so reject it instead of guessing.
        if key in states:
            raise ValueError(f"Duplicate constraint key: '{key}'.")

        # "-" is the only disabled marker in the V1 runtime file.
        if raw_value == CONSTRAINT_DISABLED_MARKER:
            states[key] = (False, "")
        else:
            states[key] = (True, raw_value)

    # A missing chunk could accidentally bypass a constraint, so be strict.
    _require_all_constraint_keys(states)

    # Reuse the GUI validation rules so the backend cannot drift.
    validation = policy.validate_all(states)
    if not validation.is_valid:
        raise ValueError(
            "Invalid constraints file: " + "; ".join(validation.errors)
        )

    # The solver receives only enabled constraints with clean integer values.
    return validation.sanitized_parameters()


def _split_records(text: str) -> list[str]:
    # Some editors add a BOM at the start of UTF-8 files.
    cleaned_text = text.lstrip("\ufeff")
    parts = cleaned_text.split(RECORD_SEPARATOR)
    return [part.strip() for part in parts if part.strip()]


def _parse_constraint_record(record_text: str) -> tuple[str, str]:
    # Empty lines are ignored, but the two meaningful lines are mandatory.
    lines = [line.strip() for line in record_text.splitlines() if line.strip()]
    if len(lines) != 2:
        raise ValueError(
            "Constraint record must contain exactly two non-empty lines: "
            "constraint key and value."
        )
    return lines[0], lines[1]


def _require_all_constraint_keys(
    states: dict[str, tuple[bool, str]],
) -> None:
    # All five known keys must appear, even when every constraint is disabled.
    expected_keys = set(EXPECTED_CONSTRAINT_KEYS)
    actual_keys = set(states)
    missing_keys = sorted(expected_keys - actual_keys)
    if missing_keys:
        raise ValueError(
            "Missing constraint key(s): " + ", ".join(missing_keys)
        )
