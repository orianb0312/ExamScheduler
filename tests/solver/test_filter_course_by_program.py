"""
Unit tests for Scheduler.filter_courses_by_programs  -  TDD style.

Run with:
    python -m pytest TestSchedulerFilter.py -v

Test categories:
    Sanity checks   – basic valid input produces correct output
    Negative checks – invalid/empty input raises or returns empty
    Boundary checks – values exactly at the min/max allowed limit
    Edge cases      – unusual-but-valid input
"""

import pytest
from unittest.mock import MagicMock
from src.models.academic import Course, ProgramAffiliation
from src.interfaces import ISchedulingRule
from src.solver.scheduler import Scheduler


# ===========================================================================
# Helpers – build lightweight Course and ProgramAffiliation mocks
# ===========================================================================

def make_affiliation(program_id: int) -> ProgramAffiliation:
    aff = MagicMock(spec=ProgramAffiliation)
    aff.program_id = program_id
    return aff


def make_course(course_id: int, program_ids: list[int]) -> Course:
    course = MagicMock(spec=Course)
    course.course_id    = course_id
    course.affiliations = [make_affiliation(pid) for pid in program_ids]
    return course


def make_scheduler() -> Scheduler:
    return Scheduler(rules=[])


# ===========================================================================
# 1. Sanity checks
# ===========================================================================

class TestFilterCoursesSanity:

    def test_returns_list(self):
        scheduler = make_scheduler()
        result = scheduler.filter_courses_by_programs([], ["83101"])
        assert isinstance(result, list)

    def test_single_course_single_match(self):
        """One course with one matching program — should be returned"""
        scheduler = make_scheduler()
        courses  = [make_course(1, [83101])]
        result   = scheduler.filter_courses_by_programs(courses, ["83101"])
        assert len(result) == 1
        assert result[0].course_id == 1

    def test_single_course_no_match(self):
        """One course with no matching program — should be excluded"""
        scheduler = make_scheduler()
        courses = [make_course(1, [83102])]
        result  = scheduler.filter_courses_by_programs(courses, ["83101"])
        assert result == []

    def test_multiple_courses_partial_match(self):
        """Three courses, only two match — returns exactly two"""
        scheduler = make_scheduler()
        courses = [
            make_course(1, [83101]),
            make_course(2, [83102]),
            make_course(3, [83104]),
        ]
        result = scheduler.filter_courses_by_programs(courses, ["83101", "83102"])
        assert len(result) == 2

    def test_correct_courses_returned(self):
        """Verify the correct course IDs are in the result"""
        scheduler = make_scheduler()
        courses = [
            make_course(1, [83101]),
            make_course(2, [83999]),
        ]
        result = scheduler.filter_courses_by_programs(courses, ["83101"])
        assert result[0].course_id == 1

    def test_course_with_multiple_programs_one_matches(self):
        """Course affiliated with multiple programs — included if any matches"""
        scheduler = make_scheduler()
        courses = [make_course(1, [83101, 83102, 83104])]
        result  = scheduler.filter_courses_by_programs(courses, ["83104"])
        assert len(result) == 1

    def test_mixed_matching_and_non_matching_courses(self):
        """Mix of matching and non-matching courses — only matching returned"""
        scheduler = make_scheduler()
        courses = [
            make_course(1, [83101]),
            make_course(2, [83999]),
            make_course(3, [83101, 83102]),
            make_course(4, [83888]),
        ]
        result = scheduler.filter_courses_by_programs(courses, ["83101"])
        assert len(result) == 2
        assert {c.course_id for c in result} == {1, 3}

    def test_all_courses_match(self):
        """All courses match — entire list returned"""
        scheduler = make_scheduler()
        courses = [make_course(i, [83101]) for i in range(10)]
        result  = scheduler.filter_courses_by_programs(courses, ["83101"])
        assert len(result) == 10

# ===========================================================================
# 2. Negative checks
# ===========================================================================

class TestFilterCoursesNegative:

    def test_empty_selected_programs_returns_empty(self):
        """No programs selected — nothing should be returned"""
        scheduler = make_scheduler()
        courses = [make_course(1, [83101])]
        result  = scheduler.filter_courses_by_programs(courses, [])
        assert result == []

    def test_empty_courses_list_returns_empty(self):
        """No courses to filter — should return empty list"""
        scheduler = make_scheduler()
        result = scheduler.filter_courses_by_programs([], ["83101"])
        assert result == []

    def test_both_empty_returns_empty(self):
        scheduler = make_scheduler()
        assert scheduler.filter_courses_by_programs([], []) == []

    def test_no_course_matches_any_selected_program(self):
        """All courses have programs not in the selection"""
        scheduler = make_scheduler()
        courses = [make_course(i, [83999]) for i in range(3)]
        result  = scheduler.filter_courses_by_programs(courses, ["83101", "83102"])
        assert result == []

    def test_course_with_empty_affiliations_excluded(self):
        """Course with empty affiliations list — must be skipped"""
        scheduler = make_scheduler()
        courses = [make_course(1, [])]
        result  = scheduler.filter_courses_by_programs(courses, ["83101"])
        assert result == []


# ===========================================================================
# 3. Boundary checks
# ===========================================================================

class TestFilterCoursesBoundary:

    def test_single_course_single_program_match(self):
        """Minimum input — one course, one program, one match"""
        scheduler = make_scheduler()
        courses = [make_course(1, [83101])]
        result  = scheduler.filter_courses_by_programs(courses, ["83101"])
        assert len(result) == 1

    def test_five_selected_programs_all_match(self):
        """Maximum user selection (5 programs) — all match"""
        scheduler = make_scheduler()
        programs  = [83101, 83102, 83104, 83107, 83108]
        courses   = [make_course(i, [programs[i]]) for i in range(5)]
        result    = scheduler.filter_courses_by_programs(
            courses, [str(p) for p in programs]
        )
        assert len(result) == 5

    def test_five_selected_programs_none_match(self):
        """Maximum user selection (5 programs) — none match"""
        scheduler = make_scheduler()
        courses = [make_course(1, [83999])]
        result  = scheduler.filter_courses_by_programs(
            courses, ["83101", "83102", "83104", "83107", "83108"]
        )
        assert result == []

# ===========================================================================
# 4. Edge cases
# ===========================================================================

class TestFilterCoursesEdgeCases:

    def test_duplicate_courses_both_returned(self):
        """Same course object appears twice — both entries returned"""
        scheduler = make_scheduler()
        course  = make_course(1, [83101])
        result  = scheduler.filter_courses_by_programs([course, course], ["83101"])
        assert len(result) == 2

    def test_duplicate_selected_programs_handled(self):
        """Duplicate program in selection — should not affect result"""
        scheduler = make_scheduler()
        courses = [make_course(1, [83101])]
        result  = scheduler.filter_courses_by_programs(courses, ["83101", "83101"])
        assert len(result) == 1



