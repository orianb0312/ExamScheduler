"""
file_parser.py
-------------
Concrete IParser that reads course, period, and user-selection data
from plain-text files.

All domain constants (valid values, patterns) are imported from IParser
so they are shared across all concrete parsers.

Expected config keys
--------------------
course_file : str   path to the courses plain-text file  (records separated by $$$$)
dates_file  : str   path to the exam-period plain-text file
user_file   : str   path to the user-selection file  e.g. "83101, 83102, 83108"
constraints_file : str|None   optional V1 constraint settings file

Usage
-----
    config = {
        "course_file": "Courses.txt",
        "dates_file":  "Dates.txt",
        "user_file":   "User.txt",
    }
    json_str = FileParser().parse_to_json(config)
"""

import json
import re
from datetime import datetime

from src.parser.IParser import (
    IParser,
    VALID_YEARS,
    VALID_SEMESTERS,
    VALID_REQUIREMENTS,
    VALID_EVALUATIONS,
    PROGRAM_NUMBER_PATTERN,
    COURSE_NUMBER_PATTERN,
    VALID_MOEDS,
    DATE_PATTERN,
    VALID_PROGRAM_NUMBERS,
)
from src.parser.constraint_file_parser import parse_constraints_text

# ---------------------------------------------------------------------------
# File-format constant  –  specific to the plain-text file format only
# ---------------------------------------------------------------------------

RECORD_SEPARATOR = "$$$$"


# ===========================================================================
# COURSES – parsing helpers
# ===========================================================================

def split_records(text: str) -> list[str]:
    """Split raw file text into individual record blocks using '$$$$' as separator."""
    text = text.lstrip("\ufeff")
    parts = text.split(RECORD_SEPARATOR)
    return [p.strip() for p in parts if p.strip()]


def parse_program_line(line: str) -> dict:
    """Parse '83101,1,FALL,Obligatory' -> dict."""
    parts = line.strip().split(",")
    if len(parts) != 4:
        raise ValueError(
            f"Invalid program line (expected 4 comma-separated fields): '{line}'"
        )
    number, year, semester, requirement = [p.strip() for p in parts]

    if not PROGRAM_NUMBER_PATTERN.match(number):
        raise ValueError(f"Invalid program number (must be 5 digits): '{number}'")
    # The SRS limits selectable study programs to the official program list.
    if number not in VALID_PROGRAM_NUMBERS:
        raise ValueError(
            f"Unknown program number '{number}'. "
            f"Valid options: {sorted(VALID_PROGRAM_NUMBERS)}"
        )
    if year not in VALID_YEARS:
        raise ValueError(f"Invalid year (must be 1-4): '{year}'")
    if semester not in VALID_SEMESTERS:
        raise ValueError(f"Invalid semester (must be FALL/SPRI/SUMM): '{semester}'")
    if requirement not in VALID_REQUIREMENTS:
        raise ValueError(f"Invalid requirement (must be Obligatory/Elective): '{requirement}'")

    return {
        "number":      number,
        "year":        year,
        "semester":    semester,
        "requirement": requirement,
    }


def parse_record(record_text: str) -> dict:
    """
    Parse a single course record block into a dict.

    Line order:
      0    - Course name
      1    - Course number  (5 digits)
      2    - Instructor name
      3..n - Program line(s)
      last - Evaluation
    """
    lines = [ln.strip() for ln in record_text.splitlines() if ln.strip()]

    if len(lines) < 5:
        raise ValueError(
            f"Record has too few lines (need at least 5, got {len(lines)}): {lines}"
        )

    name       = lines[0]
    number     = lines[1]
    instructor = lines[2]

    if not COURSE_NUMBER_PATTERN.match(number):
        raise ValueError(f"Invalid course number (must be 5 digits): '{number}'")

    evaluation = lines[-1]
    if evaluation not in VALID_EVALUATIONS:
        raise ValueError(f"Invalid evaluation '{evaluation}'")

    program_lines = lines[3:-1]
    if not program_lines:
        raise ValueError("Record must contain at least one program line")

    return {
        "name":       name,
        "number":     number,
        "instructor": instructor,
        "programs":   [parse_program_line(pl) for pl in program_lines],
        "evaluation": evaluation,
    }


def parse_catalog_text(text: str) -> list[dict]:
    """Parse full courses-file text into a list of course dicts."""
    courses = [parse_record(r) for r in split_records(text)]
    _validate_unique_course_numbers(courses)
    return courses


def _validate_unique_course_numbers(courses: list[dict]) -> None:
    seen = set()
    duplicates = []

    for course in courses:
        number = course["number"]
        if number in seen:
            duplicates.append(number)
        seen.add(number)

    if duplicates:
        duplicate_list = ", ".join(sorted(set(duplicates)))
        raise ValueError(f"Duplicate course number(s): {duplicate_list}")


# ===========================================================================
# PERIODS – parsing helpers
# ===========================================================================

def _validate_date(value: str, field_name: str) -> None:
    """Raise ValueError if value is not a valid DD-MM-YYYY date string."""
    if not DATE_PATTERN.match(value):
        raise ValueError(
            f"Invalid {field_name} date format (expected DD-MM-YYYY): '{value}'"
        )
    try:
        datetime.strptime(value, "%d-%m-%Y")
    except ValueError:
        raise ValueError(f"Invalid {field_name} date value: '{value}'")


def parse_date_line(line: str) -> dict:
    """
    Parse one excluded-date line.

    Formats accepted:
        31-01-2026 Saturday          single date with optional comment
        29-01-2026, 11-03-2026       date range
        02-03-2026, 04-03-2026 Purim date range with comment

    Returns {"start_date": str, "end_date": str|None, "comment": str|None}
    """
    line = line.strip()
    date_tokens = re.findall(r"\d{2}-\d{2}-\d{4}", line)

    if not date_tokens:
        raise ValueError(f"No date found in line: '{line}'")
    if len(date_tokens) > 2:
        raise ValueError(f"Too many dates in line (max 2): '{line}'")

    start_date = date_tokens[0]
    _validate_date(start_date, "start")

    end_date = None
    if len(date_tokens) == 2:
        end_date = date_tokens[1]
        _validate_date(end_date, "end")
        if datetime.strptime(start_date, "%d-%m-%Y") >= datetime.strptime(end_date, "%d-%m-%Y"):
            raise ValueError(
                f"start_date must be before end_date: '{start_date}' >= '{end_date}'"
            )

    remainder = line
    for tok in date_tokens:
        remainder = remainder.replace(tok, "", 1)
    comment = re.sub(r"^[\s,]+", "", remainder).strip() or None

    return {"start_date": start_date, "end_date": end_date, "comment": comment}


def parse_period_record(record_text: str) -> dict:
    """
    Parse a single period record block into a dict.

    Line order:
      0    - "Semester,Moed"          e.g. "FALL,Aleph"
      1    - "start_date, end_date"   e.g. "29-01-2026, 11-03-2026"
      2..n - Exclusion date lines     (at least one required)
    """
    lines = [ln.strip() for ln in record_text.splitlines() if ln.strip()]

    if len(lines) < 3:
        raise ValueError(
            f"Period record has too few lines (need at least 3, got {len(lines)}): {lines}"
        )

    header_parts = [p.strip() for p in lines[0].split(",")]
    if len(header_parts) != 2:
        raise ValueError(f"Period header must be 'Semester,Moed' (got '{lines[0]}')")

    semester, moed = header_parts
    if semester not in VALID_SEMESTERS:
        raise ValueError(f"Invalid semester '{semester}' (must be FALL/SPRI/SUMM)")
    if moed not in VALID_MOEDS:
        raise ValueError(f"Invalid moed '{moed}' (must be Aleph/Bet/Gimel)")

    bounds = parse_date_line(lines[1])
    if not bounds["end_date"]:
        raise ValueError(
            f"Period bounds line must contain both start and end dates: '{lines[1]}'"
        )

    return {
        "semester":   semester,
        "moed":       moed,
        "start_date": bounds["start_date"],
        "end_date":   bounds["end_date"],
        "exclusions": [parse_date_line(ln) for ln in lines[2:]],
    }


def parse_periods_text(text: str) -> list[dict]:
    """Parse full dates-file text into a list of period dicts."""
    return [parse_period_record(r) for r in split_records(text)]


# ===========================================================================
# USER SELECTION – parsing helper
# ===========================================================================

def parse_user_selection(text: str) -> list[str]:
    """
    Parse the user-selection file.

    Expected format: a single line with 1–5 program numbers separated by commas.
    Example: "83101, 83102, 83108"

    Raises
    ------
    ValueError
        If the selection is empty, contains more than 5 programs,
        or contains an unrecognised program number.
    """
    numbers = [
        t.strip().lstrip("\ufeff")
        for t in text.strip().split(",")
        if t.strip()
    ]

    if not numbers:
        raise ValueError("User selection file is empty – at least one program required.")
    if len(numbers) > 5:
        raise ValueError(f"Too many programs selected ({len(numbers)}); maximum is 5.")
    if len(set(numbers)) != len(numbers):
        raise ValueError("Duplicate program selections are not allowed.")

    for num in numbers:
        if not PROGRAM_NUMBER_PATTERN.match(num):
            raise ValueError(
                f"Invalid program number format (must be 5 digits): '{num}'"
            )
        if num not in VALID_PROGRAM_NUMBERS:
            raise ValueError(
                f"Unknown program number '{num}'. "
                f"Valid options: {sorted(VALID_PROGRAM_NUMBERS)}"
            )

    return numbers


# ===========================================================================
# Concrete IParser: plain-text files
# ===========================================================================

class FileParser(IParser):
    """
    Parses course, period, and user-selection data from plain-text files.

    All domain validation uses constants imported from IParser, ensuring
    the same rules apply here as in any other concrete parser.
    """

    REQUIRED_KEYS = {"course_file", "dates_file", "user_file"}

    def parse_to_json(self, config: dict) -> str:
        """
        Read the required files plus optional constraints, validate and parse
        every record, then return a single JSON string with:
            "courses_node", "periods_node", "user_node", "constraints_node"

        Raises
        ------
        KeyError          – if a required config key is missing
        FileNotFoundError – if any file does not exist
        ValueError        – if any file content is invalid
        """
        missing = self.REQUIRED_KEYS - config.keys()
        if missing:
            raise KeyError(f"Missing required config keys: {missing}")

        with open(config["course_file"], encoding="utf-8-sig") as fh:
            courses = parse_catalog_text(fh.read())

        with open(config["dates_file"], encoding="utf-8-sig") as fh:
            periods = parse_periods_text(fh.read())

        with open(config["user_file"], encoding="utf-8-sig") as fh:
            selection = parse_user_selection(fh.read())

        # Constraint files are optional so old V1 runs still work unchanged.
        constraints = {}
        constraints_file = config.get("constraints_file")
        if constraints_file:
            # Re-validate here because text files can be edited outside the GUI.
            with open(constraints_file, encoding="utf-8-sig") as fh:
                constraints = parse_constraints_text(fh.read())

        return json.dumps(
            {
                "courses_node": courses,
                "periods_node": periods,
                "user_node":    selection,
                "constraints_node": constraints,
            },
            ensure_ascii=False,
            indent=2,
        )
