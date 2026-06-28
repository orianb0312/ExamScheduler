from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path
from typing import Dict, Mapping

from src.interfaces import ISchedulingRule
from src.models.academic import Course
from src.services.constraint_settings_policy import (
    is_constraint_integer_allowed,
)


LOGGER = logging.getLogger(__name__)


class AICopilotRule(ISchedulingRule):
    """Validate and enforce persisted rules created by the local AI copilot."""

    MAX_FILE_BYTES = 256 * 1024
    MAX_RULES = 100

    _RULE_ID_RE = re.compile(r"^ai_rule_\d+$")
    _SAFE_TEXT_RE = re.compile(r"""^[A-Za-z0-9 .,;:!?'"\(\)\-_/]+$""")
    _WEEKDAYS = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    _PERSON_TITLES = {"dr", "doctor", "prof", "professor"}
    _RULE_SCHEMAS = {
        "fix_date": {
            "required": {"course", "date"},
            "allowed": {"course", "date"},
            "one_of": set(),
        },
        "exclude_day": {
            "required": set(),
            "allowed": {"course", "date", "weekday"},
            "one_of": {"date", "weekday"},
        },
        "exclude_period": {
            "required": set(),
            "allowed": {
                "course",
                "lecturer",
                "program",
                "month",
                "year",
                "start_date",
                "end_date",
            },
            "one_of": set(),
        },
        "lecturer_unavailable": {
            "required": {"lecturer"},
            "allowed": {"lecturer", "date", "weekday", "month", "day", "year"},
            "one_of": set(),
        },
        "program_limit": {
            "required": {"program", "max_exams_per_day"},
            "allowed": {"program", "max_exams_per_day"},
            "one_of": set(),
        },
        "exam_spacing": {
            "required": {"min_days"},
            "allowed": {"min_days"},
            "one_of": set(),
        },
    }

    def __init__(self, ai_rules_filepath: Path | str):
        self.ai_rules_filepath = Path(ai_rules_filepath).expanduser().resolve()
        self.ai_constraints = self._load_ai_rules(self.ai_rules_filepath)
        self._application_logged = False
        LOGGER.debug("Loading active AI rules from %s", self.ai_rules_filepath)
        LOGGER.debug(
            "Loaded %s validated active AI rule(s)",
            len(self.ai_constraints),
        )

    @classmethod
    def validate_rule_record(cls, record: object) -> dict | None:
        """Return a defensive copy of one valid persisted record."""
        if not isinstance(record, Mapping):
            return None
        if set(record) != {"rule_id", "description", "rule_type", "parameters"}:
            return None

        rule_id = record.get("rule_id")
        description = record.get("description")
        rule_type = record.get("rule_type")
        parameters = record.get("parameters")
        if (
            not isinstance(rule_id, str)
            or cls._RULE_ID_RE.fullmatch(rule_id) is None
            or not cls._is_safe_text(description, maximum=180)
            or rule_type not in cls._RULE_SCHEMAS
            or not isinstance(parameters, Mapping)
            or not cls._validate_parameters(str(rule_type), parameters)
        ):
            return None

        return {
            "rule_id": rule_id,
            "description": str(description).strip(),
            "rule_type": str(rule_type),
            "parameters": dict(parameters),
        }

    def _load_ai_rules(self, filepath: Path) -> list[dict]:
        if not filepath.is_file():
            return []

        try:
            if filepath.stat().st_size > self.MAX_FILE_BYTES:
                LOGGER.warning("AI rules file exceeds the safe size limit")
                return []
            payload = json.loads(
                filepath.read_text(encoding="utf-8"),
                object_pairs_hook=self._reject_duplicate_keys,
                parse_constant=self._reject_non_finite_number,
            )
        except (OSError, json.JSONDecodeError, ValueError, RecursionError) as exc:
            LOGGER.warning("Rejected invalid AI rules file: %s", exc)
            return []

        if not isinstance(payload, list) or len(payload) > self.MAX_RULES:
            LOGGER.warning("Rejected AI rules file with invalid root schema")
            return []

        validated_rules: list[dict] = []
        seen_rule_ids: set[str] = set()
        for record in payload:
            validated = self.validate_rule_record(record)
            if validated is None or validated["rule_id"] in seen_rule_ids:
                LOGGER.debug("Skipped an invalid or duplicate AI rule")
                continue
            seen_rule_ids.add(validated["rule_id"])
            validated_rules.append(validated)
        return validated_rules

    def is_valid(self, attempt_state: Dict[Course, date]) -> bool:
        if not self.ai_constraints:
            return True

        if not self._application_logged:
            LOGGER.debug(
                "Applying %s active AI rule(s)",
                len(self.ai_constraints),
            )
            self._application_logged = True

        for rule in self.ai_constraints:
            if not self._rule_is_valid(rule, attempt_state):
                LOGGER.debug(
                    "AI rule rejected scheduling branch: %s (%s)",
                    rule["rule_id"],
                    rule["rule_type"],
                )
                return False
        return True

    def _rule_is_valid(
        self,
        rule: Mapping[str, object],
        attempt_state: Mapping[Course, date],
    ) -> bool:
        rule_type = str(rule["rule_type"])
        parameters = rule["parameters"]
        if not isinstance(parameters, Mapping):
            return False

        if rule_type == "fix_date":
            target_date = date.fromisoformat(str(parameters["date"]))
            return all(
                exam_date == target_date
                for course, exam_date in attempt_state.items()
                if self._course_matches(course, str(parameters["course"]))
            )

        if rule_type == "exclude_day":
            return all(
                not self._date_matches(exam_date, parameters)
                for course, exam_date in attempt_state.items()
                if "course" not in parameters
                or self._course_matches(course, str(parameters["course"]))
            )

        if rule_type == "exclude_period":
            return all(
                not self._date_matches(exam_date, parameters)
                for course, exam_date in attempt_state.items()
                if self._course_is_in_scope(course, parameters)
            )

        if rule_type == "lecturer_unavailable":
            return all(
                not self._date_matches(exam_date, parameters)
                for course, exam_date in attempt_state.items()
                if self._lecturer_matches(
                    course.instructor,
                    str(parameters["lecturer"]),
                )
            )

        if rule_type == "program_limit":
            program_id = int(str(parameters["program"]))
            maximum = int(parameters["max_exams_per_day"])
            date_counts: dict[date, int] = {}
            for course, exam_date in attempt_state.items():
                if any(
                    affiliation.program_id == program_id
                    for affiliation in course.affiliations
                ):
                    date_counts[exam_date] = date_counts.get(exam_date, 0) + 1
                    if date_counts[exam_date] > maximum:
                        return False
            return True

        if rule_type == "exam_spacing":
            minimum_days = int(parameters["min_days"])
            scheduled_dates = list(attempt_state.values())
            return all(
                abs((scheduled_dates[left] - scheduled_dates[right]).days)
                >= minimum_days
                for left in range(len(scheduled_dates))
                for right in range(left + 1, len(scheduled_dates))
            )

        return False

    @classmethod
    def _validate_parameters(
        cls,
        rule_type: str,
        parameters: Mapping[object, object],
    ) -> bool:
        schema = cls._RULE_SCHEMAS[rule_type]
        keys = set(parameters)
        if (
            not all(isinstance(key, str) for key in keys)
            or not schema["required"].issubset(keys)
            or not keys.issubset(schema["allowed"])
        ):
            return False
        if schema["one_of"] and len(keys & schema["one_of"]) != 1:
            return False
        if rule_type == "exclude_period":
            has_month = "month" in parameters
            has_range = (
                "start_date" in parameters or "end_date" in parameters
            )
            if has_month == has_range:
                return False
            if has_range and not {
                "start_date",
                "end_date",
            }.issubset(keys):
                return False
            if "year" in parameters and not has_month:
                return False

        if rule_type == "lecturer_unavailable":
            has_date = "date" in parameters
            has_weekday = "weekday" in parameters
            has_month_day = {"month", "day"}.issubset(keys)
            if sum((has_date, has_weekday, has_month_day)) != 1:
                return False
            if ("month" in parameters) != ("day" in parameters):
                return False
            if "year" in parameters and not has_month_day:
                return False

        for name in ("course", "lecturer"):
            if name in parameters and not cls._is_safe_text(
                parameters[name],
                maximum=120,
            ):
                return False

        if "program" in parameters and (
            not isinstance(parameters["program"], str)
            or re.fullmatch(r"\d{1,10}", parameters["program"]) is None
        ):
            return False

        for date_key in ("date", "start_date", "end_date"):
            if date_key not in parameters:
                continue
            if not isinstance(parameters[date_key], str):
                return False
            try:
                date.fromisoformat(parameters[date_key])
            except ValueError:
                return False
        if {
            "start_date",
            "end_date",
        }.issubset(keys) and date.fromisoformat(
            str(parameters["start_date"])
        ) > date.fromisoformat(str(parameters["end_date"])):
            return False

        if "weekday" in parameters and (
            not isinstance(parameters["weekday"], str)
            or parameters["weekday"].casefold() not in cls._WEEKDAYS
        ):
            return False
        if "month" in parameters and (
            not isinstance(parameters["month"], int)
            or isinstance(parameters["month"], bool)
            or not 1 <= parameters["month"] <= 12
        ):
            return False
        if "day" in parameters and (
            not isinstance(parameters["day"], int)
            or isinstance(parameters["day"], bool)
            or not 1 <= parameters["day"] <= 31
        ):
            return False
        if "year" in parameters and (
            not isinstance(parameters["year"], int)
            or isinstance(parameters["year"], bool)
            or not 1900 <= parameters["year"] <= 2200
        ):
            return False
        if {"month", "day"}.issubset(keys):
            try:
                date(2000, int(parameters["month"]), int(parameters["day"]))
            except ValueError:
                return False

        numeric_constraints = {
            "max_exams_per_day": "max_exams_per_day",
            "min_days": "min_days_between_any",
        }
        for key, constraint_key in numeric_constraints.items():
            if (
                key in parameters
                and not is_constraint_integer_allowed(
                    constraint_key,
                    parameters[key],
                )
            ):
                return False
        return True

    @classmethod
    def _date_matches(
        cls,
        exam_date: date,
        parameters: Mapping[str, object],
    ) -> bool:
        if "date" in parameters:
            return exam_date == date.fromisoformat(str(parameters["date"]))
        if "weekday" in parameters:
            weekday = str(parameters["weekday"]).casefold()
            return exam_date.weekday() == cls._WEEKDAYS[weekday]
        if "month" in parameters:
            if "day" in parameters:
                return (
                    exam_date.month == parameters["month"]
                    and exam_date.day == parameters["day"]
                    and (
                        "year" not in parameters
                        or exam_date.year == parameters["year"]
                    )
                )
            return (
                exam_date.month == parameters["month"]
                and (
                    "year" not in parameters
                    or exam_date.year == parameters["year"]
                )
            )
        return (
            date.fromisoformat(str(parameters["start_date"]))
            <= exam_date
            <= date.fromisoformat(str(parameters["end_date"]))
        )

    @classmethod
    def _course_is_in_scope(
        cls,
        course: Course,
        parameters: Mapping[str, object],
    ) -> bool:
        if "course" in parameters and not cls._course_matches(
            course,
            str(parameters["course"]),
        ):
            return False
        if "lecturer" in parameters and not cls._lecturer_matches(
            course.instructor,
            str(parameters["lecturer"]),
        ):
            return False
        if "program" in parameters and not any(
            affiliation.program_id == int(str(parameters["program"]))
            for affiliation in course.affiliations
        ):
            return False
        return True

    @staticmethod
    def _course_matches(course: Course, requested_course: str) -> bool:
        requested = AICopilotRule._normalize_words(requested_course)
        return requested in {
            AICopilotRule._normalize_words(course.name),
            str(course.course_id),
        }

    @classmethod
    def _lecturer_matches(cls, instructor: str, requested: str) -> bool:
        instructor_words = [
            word
            for word in cls._normalize_words(instructor).split()
            if word not in cls._PERSON_TITLES
        ]
        requested_words = [
            word
            for word in cls._normalize_words(requested).split()
            if word not in cls._PERSON_TITLES
        ]
        if not requested_words or len(requested_words) > len(instructor_words):
            return False
        return instructor_words[-len(requested_words):] == requested_words

    @staticmethod
    def _normalize_words(value: str) -> str:
        return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))

    @classmethod
    def _is_safe_text(cls, value: object, maximum: int) -> bool:
        return (
            isinstance(value, str)
            and bool(value.strip())
            and len(value) <= maximum
            and value.isascii()
            and cls._SAFE_TEXT_RE.fullmatch(value) is not None
        )

    @staticmethod
    def _reject_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    @staticmethod
    def _reject_non_finite_number(value: str):
        raise ValueError(f"Non-finite JSON number: {value}")
