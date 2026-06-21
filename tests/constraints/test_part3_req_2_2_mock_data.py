import json
from datetime import date
from pathlib import Path

import pytest

from src.models.academic import Course, Exam, ProgramAffiliation
from src.models.enums import RequirementType, Semester


# Keep the sample pairs in a fixture so the test data is easy to review.
FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "part3_req_2_2_mock_pairs.json"
)


def _load_cases() -> list[dict]:
    with FIXTURE_PATH.open(encoding="utf-8") as fixture:
        return json.load(fixture)


REQ_2_2_CASES = _load_cases()


def _parse_date(raw_date: str) -> date:
    return date.fromisoformat(raw_date)


def _build_course(raw_course: dict, case: dict) -> Course:
    affiliation = ProgramAffiliation(
        program_id=case["program_id"],
        year=case["year"],
        semester=Semester(case["semester"]),
        requirement_type=RequirementType(raw_course["requirement_type"]),
    )
    return Course(
        course_id=raw_course["course_id"],
        name=raw_course["name"],
        instructor="Req 2.2 fixture",
        evaluation=Exam(),
        affiliations=[affiliation],
    )


def _gap_days(case: dict) -> int:
    return abs((_parse_date(case["right_date"]) - _parse_date(case["left_date"])).days)


def test_req_2_2_mock_data_covers_the_three_exam_pair_types():
    pair_types = {case["pair_type"] for case in REQ_2_2_CASES}

    assert pair_types == {
        "mandatory-mandatory",
        "mandatory-elective",
        "elective-elective",
    }


def test_req_2_2_mock_data_has_exact_and_under_k_cases_for_each_pair_type():
    # Each pair type needs one pass case and one fail case.
    for pair_type in {
        "mandatory-mandatory",
        "mandatory-elective",
        "elective-elective",
    }:
        cases = [case for case in REQ_2_2_CASES if case["pair_type"] == pair_type]
        exact_k = [
            case for case in cases
            if _gap_days(case) == case["k"] and case["expected_allowed"]
        ]
        under_k = [
            case for case in cases
            if _gap_days(case) < case["k"] and not case["expected_allowed"]
        ]

        assert exact_k
        assert under_k


@pytest.mark.parametrize("case", REQ_2_2_CASES, ids=lambda case: case["case_id"])
def test_req_2_2_mock_pairs_are_same_program_same_year_exam_courses(case: dict):
    left = _build_course(case["left_course"], case)
    right = _build_course(case["right_course"], case)

    assert left.needs_exam_slot()
    assert right.needs_exam_slot()
    assert left.affiliations[0].program_id == right.affiliations[0].program_id
    assert left.affiliations[0].year == right.affiliations[0].year


@pytest.mark.parametrize("case", REQ_2_2_CASES, ids=lambda case: case["case_id"])
def test_req_2_2_mock_pairs_document_the_expected_distance_outcome(case: dict):
    gap_days = _gap_days(case)

    assert case["k"] > 0
    assert (gap_days >= case["k"]) is case["expected_allowed"]
