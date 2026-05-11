"""
parserPrint.py
---------------
Loads parsed JSON data, builds domain objects, and prints them.
"""

import json
import os

from IParser import IParser
from FileParser import FileParser
from course_factory import build_courses_from_json
from period_factory import build_periods_from_json
from scheduling import ExamPeriod
from academic import Course


def get_parser(source_type: str) -> IParser:
    """Return the right IParser implementation for the given source type."""
    if source_type == "file":
        return FileParser()
    else:
        raise ValueError(f"Unknown source_type: '{source_type}'")


def load_app_config(config_path: str) -> dict:
    """Read the JSON config file and return it as a dict."""
    with open(config_path, encoding="utf-8") as fh:
        return json.load(fh)


def print_courses(courses: list[Course]) -> None:
    print(f"=== COURSES ({len(courses)}) ===\n")
    for course in courses:
        print(f"  Name:       {course.name}")
        print(f"  ID:         {course.course_id}")
        print(f"  Instructor: {course.instructor}")
        print(f"  Evaluation: {course.evaluation.__class__.__name__}")
        print(f"  Needs Slot: {course.needs_exam_slot()}")
        print(f"  Affiliations:")
        for aff in course.affiliations:
            print(
                f"    - Program {aff.program_id}  "
                f"year {aff.year}  "
                f"{aff.semester.name}  "
                f"{aff.requirement_type.name}"
            )
        print()


def print_periods(periods: list[ExamPeriod]) -> None:
    print(f"=== EXAM PERIODS ({len(periods)}) ===\n")
    for period in periods:
        print(f"  Semester: {period.semester.name}  |  Term: {period.term.name}")
        print(f"  Period:   {period.start_date.strftime('%d-%m-%Y')} → {period.end_date.strftime('%d-%m-%Y')}")
        print(f"  Exclusions:")
        for excl in period.exclusions:
            date_range = excl.start_date.strftime('%d-%m-%Y')
            if excl.end_date:
                date_range += f" → {excl.end_date.strftime('%d-%m-%Y')}"
            print(f"    - {date_range}")
        print()


def print_user_selection(selection: list) -> None:
    print(f"=== USER SELECTION ({len(selection)} program(s)) ===\n")
    for num in selection:
        print(f"  [{num}]")
    print()


def run_parser_print() -> None:
    """
    Load config, build domain objects and print them.
    Can be called from another main file.
    """
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    app_config  = load_app_config(config_path)

    source_type   = app_config["source_type"]
    parser_config = app_config[source_type]

    parser   = get_parser(source_type)
    json_str = parser.parse_to_json(parser_config)

    courses = build_courses_from_json(json_str)
    periods = build_periods_from_json(json_str)

    data = json.loads(json_str)

    print_courses(courses)
    print_periods(periods)
    print_user_selection(data["user_node"])