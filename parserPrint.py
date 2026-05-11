"""
parserPrint.py
---------------
Loads parsed JSON data and prints courses, exam periods,
and user-selected programs.
"""

import json
import os

from IParser import IParser
from FileParser import FileParser


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


def print_courses(courses: list) -> None:
    print(f"=== COURSES ({len(courses)}) ===\n")
    for course in courses:
        print(f"  Name:       {course['name']}")
        print(f"  Number:     {course['number']}")
        print(f"  Instructor: {course['instructor']}")
        print(f"  Evaluation: {course['evaluation']}")
        print(f"  Programs:")
        for prog in course["programs"]:
            print(
                f"    - {prog['number']}  "
                f"year {prog['year']}  "
                f"{prog['semester']}  "
                f"{prog['requirement']}"
            )
        print()


def print_periods(periods: list) -> None:
    print(f"=== EXAM PERIODS ({len(periods)}) ===\n")
    for period in periods:
        print(f"  Semester: {period['semester']}  |  Moed: {period['moed']}")
        for d in period["dates"]:
            date_range = d["start_date"]
            if d["end_date"]:
                date_range += f" → {d['end_date']}"
            comment = f"  ({d['comment']})" if d["comment"] else ""
            print(f"    - {date_range}{comment}")
        print()


def print_user_selection(selection: list) -> None:
    print(f"=== USER SELECTION ({len(selection)} program(s)) ===\n")

    for num in selection:
        print(f"  [{num}]")

    print()


def run_parser_print() -> None:
    """
    Load config, parse data and print it.
    Can be called from another main file.
    """
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    app_config = load_app_config(config_path)

    source_type = app_config["source_type"]
    parser_config = app_config[source_type]

    parser = get_parser(source_type)
    json_str = parser.parse_to_json(parser_config)

    data = json.loads(json_str)

    print_courses(data["courses_node"])
    print_periods(data["periods_node"])
    print_user_selection(data["user_node"])