"""Validation rules for the five scheduling constraint parameters.

"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class KValueRule(str, Enum):
    """How the k value of a constraint is allowed to be validated."""

    POSITIVE_INTEGER = "positive_integer"      # k >= 1
    NON_NEGATIVE_INTEGER = "non_negative"      # k >= 0 (zero allowed)


@dataclass(frozen=True)
class ConstraintDefinition:
    """Static description of one schedulable constraint.

    Attributes
    ----------
    key:
        Stable identifier used when the parameters are passed onward.
    code:
        Requirement-document number (e.g. "2.1") shown to the user.
    title:
        Short human-readable name of the constraint.
    description:
        One-line explanation shown next to the toggle.
    k_rule:
        Which validation rule applies to this constraint's k value.
    """

    key: str
    code: str
    title: str
    description: str
    k_rule: KValueRule

    @property
    def allows_zero(self) -> bool:
        return self.k_rule is KValueRule.NON_NEGATIVE_INTEGER


# The five constraints, ordered as in the requirements document.
CONSTRAINT_DEFINITIONS: tuple[ConstraintDefinition, ...] = (
    ConstraintDefinition(
        key="min_days_between_mandatory",
        code="2.1",
        title="Minimum days between mandatory exams",
        description="Days between two mandatory exams in the same program and year.",
        k_rule=KValueRule.POSITIVE_INTEGER,
    ),
    ConstraintDefinition(
        key="min_days_between_any",
        code="2.2",
        title="Minimum days between any two exams",
        description="Days between two exams (mandatory or elective).",
        k_rule=KValueRule.POSITIVE_INTEGER,
    ),
    ConstraintDefinition(
        key="max_elective_conflicts",
        code="2.3",
        title="Maximum elective conflicts",
        description="Conflicts allowed between two elective courses in the same program.",
        k_rule=KValueRule.NON_NEGATIVE_INTEGER,
    ),
    ConstraintDefinition(
        key="min_days_before_last_mandatory",
        code="2.4",
        title="Minimum days before last mandatory exam",
        description="Days between a given date and the last mandatory exam in the program/year.",
        k_rule=KValueRule.POSITIVE_INTEGER,
    ),
    ConstraintDefinition(
        key="max_exams_per_day",
        code="2.5",
        title="Maximum exams per day",
        description="Exams allowed to be scheduled on the same day.",
        k_rule=KValueRule.POSITIVE_INTEGER,
    ),
)

CONSTRAINTS_BY_KEY: dict[str, ConstraintDefinition] = {
    definition.key: definition for definition in CONSTRAINT_DEFINITIONS
}


@dataclass(frozen=True)
class ConstraintValueResult:
    """Validation outcome for a single constraint's k value."""

    key: str
    enabled: bool
    error: str | None
    value: int | None

    @property
    def is_valid(self) -> bool:
        return self.error is None


@dataclass(frozen=True)
class ConstraintValidation:
    """Aggregate validation result for all five constraints."""

    results: tuple[ConstraintValueResult, ...]

    @property
    def is_valid(self) -> bool:
        return all(result.is_valid for result in self.results)

    @property
    def errors(self) -> tuple[str, ...]:
        return tuple(
            f"{result.key}: {result.error}"
            for result in self.results
            if result.error is not None
        )

    def sanitized_parameters(self) -> dict[str, int]:
        """Return only enabled, valid constraints as a clean key -> k mapping.

        Disabled constraints are excluded entirely, so the consumer receives
        exactly the active parameters and nothing else.
        """
        return {
            result.key: result.value
            for result in self.results
            if result.enabled and result.is_valid and result.value is not None
        }


class ConstraintSettingsPolicy:
    """Validate raw constraint inputs against the per-constraint k rules."""

    def validate_value(
        self,
        definition: ConstraintDefinition,
        enabled: bool,
        raw_value: str,
    ) -> ConstraintValueResult:
        """Validate a single constraint's enabled flag and raw text value."""
        # A disabled constraint is never an error; its value is simply ignored.
        if not enabled:
            return ConstraintValueResult(
                key=definition.key,
                enabled=False,
                error=None,
                value=None,
            )

        text = raw_value.strip()
        if not text:
            return ConstraintValueResult(
                key=definition.key,
                enabled=True,
                error="A value is required when this constraint is enabled.",
                value=None,
            )

        if not _is_integer(text):
            return ConstraintValueResult(
                key=definition.key,
                enabled=True,
                error="Value must be a whole number.",
                value=None,
            )

        value = int(text)
        minimum = 0 if definition.allows_zero else 1
        if value < minimum:
            wording = (
                "zero or a positive whole number"
                if definition.allows_zero
                else "a positive whole number"
            )
            return ConstraintValueResult(
                key=definition.key,
                enabled=True,
                error=f"Value must be {wording}.",
                value=None,
            )

        return ConstraintValueResult(
            key=definition.key,
            enabled=True,
            error=None,
            value=value,
        )

    def validate_all(
        self,
        states: dict[str, tuple[bool, str]],
    ) -> ConstraintValidation:
        """Validate every known constraint.

        Parameters
        ----------
        states:
            Mapping of constraint key -> (enabled, raw_value).
        """
        results = []
        for definition in CONSTRAINT_DEFINITIONS:
            enabled, raw_value = states.get(definition.key, (False, ""))
            results.append(self.validate_value(definition, enabled, raw_value))
        return ConstraintValidation(results=tuple(results))


def _is_integer(text: str) -> bool:
    candidate = text[1:] if text.startswith(("+", "-")) else text
    return candidate.isdigit()


DEFAULT_CONSTRAINT_SETTINGS_POLICY = ConstraintSettingsPolicy()