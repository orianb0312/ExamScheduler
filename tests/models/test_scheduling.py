import pytest
from src.models.academic import Course, ProgramAffiliation, Exam, Project, Attendance
from src.models.enums import Semester, RequirementType
from src.models.scheduling import filter_exam_courses


def _affiliation():
    return ProgramAffiliation(
        program_id=83108,
        year=2,
        semester=Semester.FALL,
        requirement_type=RequirementType.OBLIGATORY,
    )


def test_filter_exam_courses_keeps_only_exam_courses():
    a = _affiliation()
    c_exam = Course(10001, "Exam Course", "Dr. A", Exam(), [a])
    c_proj = Course(10002, "Project Course", "Dr. B", Project(), [a])
    c_att = Course(10003, "Attendance Course", "Dr. C", Attendance(), [a])

    result = filter_exam_courses([c_exam, c_proj, c_att])

    assert result == [c_exam]


def test_filter_exam_courses_returns_empty_when_no_exam_courses():
    a = _affiliation()
    c_proj = Course(10004, "Project Course", "Dr. D", Project(), [a])
    c_att = Course(10005, "Attendance Course", "Dr. E", Attendance(), [a])

    result = filter_exam_courses([c_proj, c_att])

    assert result == []


def test_filter_exam_courses_keeps_all_when_all_are_exam():
    a = _affiliation()
    c1 = Course(10006, "Exam 1", "Dr. F", Exam(), [a])
    c2 = Course(10007, "Exam 2", "Dr. G", Exam(), [a])

    result = filter_exam_courses([c1, c2])

    assert result == [c1, c2]


def test_filter_exam_courses_preserves_original_order():
    a = _affiliation()
    c1 = Course(10008, "Exam A", "Dr. H", Exam(), [a])
    c2 = Course(10009, "Project", "Dr. I", Project(), [a])
    c3 = Course(10010, "Exam B", "Dr. J", Exam(), [a])

    result = filter_exam_courses([c1, c2, c3])

    assert result == [c1, c3]