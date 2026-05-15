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
# Tests
# ===========================================================================
class TestFilterCoursesOptimized:

    # --- Sanity & Basics ---

    def test_single_course_single_match(self):
        """ One course with one matching program — should be returned in a list"""
        scheduler = make_scheduler()
        courses  = [make_course(1, [83101])]
        result   = scheduler.filter_courses_by_programs(courses, ["83101"])
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].course_id == 1

    def test_mixed_matching_and_non_matching_courses(self):
        """ Mix of matching and non-matching courses — only correct course IDs are returned"""
        scheduler = make_scheduler()
        courses = [
            make_course(1, [83101]),
            make_course(2, [83999]),
            make_course(3, [83101]),
        ]
        result = scheduler.filter_courses_by_programs(courses, ["83101"])
        assert len(result) == 2
        assert {c.course_id for c in result} == {1, 3}

    def test_course_with_multiple_programs_one_matches(self):
        """ Course affiliated with multiple programs — included if at least one matches"""
        scheduler = make_scheduler()
        courses = [make_course(1, [83101, 83102, 83104])]
        result  = scheduler.filter_courses_by_programs(courses, ["83104"])
        assert len(result) == 1

    # --- Negative Checks (Empty inputs / No matches) ---

    def test_empty_selected_programs_returns_empty(self):
        """ No programs selected — result must be empty"""
        scheduler = make_scheduler()
        courses = [make_course(1, [83101])]
        result  = scheduler.filter_courses_by_programs(courses, [])
        assert result == []

    def test_empty_courses_list_returns_empty(self):
        """ No courses provided (or both inputs empty) — returns an empty list"""
        scheduler = make_scheduler()
        assert scheduler.filter_courses_by_programs([], ["83101"]) == []
        assert scheduler.filter_courses_by_programs([], []) == []

    def test_no_course_matches_any_selected_program(self):
        """ All courses have programs that are completely absent from the selection"""
        scheduler = make_scheduler()
        courses = [make_course(1, [83999]), make_course(2, [83888])]
        result  = scheduler.filter_courses_by_programs(courses, ["83101", "83102"])
        assert result == []

    def test_course_with_empty_affiliations_excluded(self):
        """ Course has an empty affiliations list — must be safely skipped"""
        scheduler = make_scheduler()
        courses = [make_course(1, [])]
        result  = scheduler.filter_courses_by_programs(courses, ["83101"])
        assert result == []

    # --- Boundaries & Edge Cases ---

    def test_max_selected_programs_boundary(self):
        """ Upper boundary: Maximum selection (5 programs) — correctly filters a mix of courses"""
        scheduler = make_scheduler()
        programs = [83101, 83102, 83104, 83107, 83108]
        courses  = [make_course(1, [83101]), make_course(2, [83999])] # One matches, one does not

        result = scheduler.filter_courses_by_programs(courses, [str(p) for p in programs])
        assert len(result) == 1
        assert result[0].course_id == 1

    def test_duplicate_selected_programs_handled(self):
        """ Edge case: Duplicate program in selection — handled gracefully without multiplying results"""
        scheduler = make_scheduler()
        courses = [make_course(1, [83101])]
        result  = scheduler.filter_courses_by_programs(courses, ["83101", "83101"])
        assert len(result) == 1



