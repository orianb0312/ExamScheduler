"""Export one validated AI parser result for file-based workflows."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable


def export_ai_constraint(
    raw_json: str,
    destination: Path | str,
    validate_record: Callable[[object], dict | None],
    rule_id: str = "ai_rule_1",
) -> Path:
    """Validate and export one parsed constraint as an AI rules JSON file."""
    if not isinstance(raw_json, str) or len(raw_json) > 8192:
        raise ValueError("AI constraint JSON is missing or too large.")

    try:
        constraint = json.loads(
            raw_json,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite_number,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError("AI constraint must be valid JSON.") from exc

    if not isinstance(constraint, dict) or "action" not in constraint:
        raise ValueError("AI constraint must be a JSON object with an action.")

    action = constraint.get("action")
    parameters = {
        key: value
        for key, value in constraint.items()
        if key != "action"
    }
    record = {
        "rule_id": rule_id,
        "description": _describe_constraint(str(action), parameters),
        "rule_type": action,
        "parameters": parameters,
    }
    validated = validate_record(record)
    if validated is None:
        raise ValueError("AI constraint does not match the supported schema.")

    output_path = Path(destination).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps([validated], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_path, output_path)
    return output_path


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_non_finite_number(value: str):
    raise ValueError(f"Non-finite JSON number: {value}")


def _describe_constraint(action: str, parameters: dict) -> str:
    if action == "fix_date":
        return f'Fix {parameters.get("course")} on {parameters.get("date")}'
    if action == "exclude_day":
        day = parameters.get("date") or parameters.get("weekday")
        course = parameters.get("course")
        return f"Exclude {day} for {course}" if course else f"Exclude {day}"
    if action == "exclude_period":
        period = parameters.get("month") or (
            f'{parameters.get("start_date")} through {parameters.get("end_date")}'
        )
        if parameters.get("lecturer"):
            return f'Exclude period {period} for lecturer {parameters["lecturer"]}'
        if parameters.get("course"):
            return f'Exclude period {period} for {parameters["course"]}'
        if parameters.get("program"):
            return f'Exclude period {period} for program {parameters["program"]}'
        return f"Exclude period {period}"
    if action == "lecturer_unavailable":
        day = (
            parameters.get("date")
            or parameters.get("weekday")
            or _format_month_day(parameters)
        )
        return f'Lecturer {parameters.get("lecturer")} unavailable on {day}'
    if action == "program_limit":
        return (
            f'Limit program {parameters.get("program")} to '
            f'{parameters.get("max_exams_per_day")} exams per day'
        )
    if action == "exam_spacing":
        return f'Minimum {parameters.get("min_days")} days between exams'
    return "Unsupported AI scheduling rule"


def _format_month_day(parameters: dict) -> str | None:
    if "month" not in parameters or "day" not in parameters:
        return None
    month_names = (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )
    try:
        month = month_names[int(parameters["month"]) - 1]
        day = int(parameters["day"])
    except (TypeError, ValueError, IndexError):
        return None
    value = f"{month} {day}"
    if parameters.get("year"):
        value = f'{value}, {parameters["year"]}'
    return value
