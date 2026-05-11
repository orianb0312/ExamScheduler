"""
IParser.py
----------
Abstract base class (interface) for any course-catalog parser.

Also defines all domain constants – valid values that apply regardless
of the data source (file, database, API, etc.).
"""

import re
from abc import ABC, abstractmethod

# ---------------------------------------------------------------------------
# Domain constants  –  valid regardless of data source
# ---------------------------------------------------------------------------

# --- courses ----------------------------------------------------------------
VALID_YEARS            = {"1", "2", "3", "4"}
VALID_SEMESTERS        = {"FALL", "SPRI", "SUMM"}
VALID_REQUIREMENTS     = {"Obligatory", "Elective"}
VALID_EVALUATIONS      = {"Exam", "Project", "Attendance"}
PROGRAM_NUMBER_PATTERN = re.compile(r"^\d{5}$")
COURSE_NUMBER_PATTERN  = re.compile(r"^\d{5}$")

# --- periods ----------------------------------------------------------------
VALID_MOEDS  = {"Aleph", "Bet", "Gimel"}
DATE_PATTERN = re.compile(r"^\d{2}-\d{2}-\d{4}$")

# --- user selection ---------------------------------------------------------
VALID_PROGRAM_NUMBERS = {
    "83101", "83102", "83104", "83107", "83108",
    "83109", "83105", "83182", "83103", "83115",
}


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------

class IParser(ABC):
    """Interface for parsing a course catalog from any data source."""

    @abstractmethod
    def parse_to_json(self, config: dict) -> str:
        """
        Parse the course catalog described by `config` and return a JSON string.

        Parameters
        ----------
        config : dict
            A dictionary whose keys depend on the concrete implementation.
            Each subclass documents and validates its own expected keys.

        Returns
        -------
        str
            A JSON string with three top-level keys:
            {
                "courses_node": [
                    {
                        "name":       str,
                        "number":     str,          # 5-digit string
                        "instructor": str,
                        "programs": [
                            {
                                "number":      str,  # 5-digit string
                                "year":        str,  # "1"|"2"|"3"|"4"
                                "semester":    str,  # "FALL"|"SPRI"|"SUMM"
                                "requirement": str   # "Obligatory"|"Elective"
                            },
                            ...
                        ],
                        "evaluation": str            # "Exam"|"Project"|"Attendance"
                    },
                    ...
                ],
                "periods_node": [ ... ],
                "user_node":    [ ... ]
            }
        """