from __future__ import annotations

import uuid
from datetime import date, time

from src.models.enums import Semester, Term
from src.output.ics_formatter import ICSFormatter
from src.output.output_models import ScheduledExam


def _sample_exam(**overrides) -> ScheduledExam:
    """Create a reusable ScheduledExam instance for test scenarios."""
    defaults = dict(
        course_name="Algorithms",
        course_id=10001,
        semester=Semester.FALL,
        term=Term.ALEPH,
        exam_date=date(2026, 1, 10),
        instructor="Dr. Ada",
    )
    defaults.update(overrides)
    return ScheduledExam(**defaults)


def test_request_ics_contains_required_calendar_fields() -> None:
    formatter = ICSFormatter()
    content = formatter.format(
        publish_data={Semester.FALL: {Term.ALEPH: [_sample_exam()]}}
    )

    assert "VERSION:2.0" in content
    assert "METHOD:PUBLISH" in content
    assert "PRODID:-//Bar Ilan Engineering Faculty//ExamScheduler V4.0//EN" in content
    assert "SUMMARY:Exam: Algorithms (10001) - Aleph" in content
    assert "DTSTART;VALUE=DATE:20260110" in content
    assert "STATUS:CANCELLED" not in content


def test_cancel_ics_marks_events_cancelled() -> None:
    formatter = ICSFormatter()
    content = formatter.format(
        cancel_data={Semester.FALL: {Term.ALEPH: [_sample_exam()]}}
    )

    assert "METHOD:PUBLISH" in content
    assert "STATUS:CANCELLED" in content


def test_uid_is_deterministic_for_same_exam_identity() -> None:
    exam = _sample_exam()
    first = ICSFormatter().format(publish_data={Semester.FALL: {Term.ALEPH: [exam]}})
    second = ICSFormatter().format(publish_data={Semester.FALL: {Term.ALEPH: [exam]}})

    uid_line = next(line for line in first.splitlines() if line.startswith("UID:"))
    assert uid_line in second.splitlines()
    assert uid_line.endswith("@examscheduler.local")


def test_uid_matches_uuid5_contract() -> None:
    exam = _sample_exam(course_id=42, exam_date=date(2026, 2, 3))
    expected = f"{uuid.uuid5(uuid.NAMESPACE_DNS, '42-20260203')}@examscheduler.local"
    content = ICSFormatter().format(publish_data={Semester.FALL: {Term.ALEPH: [exam]}})
    assert f"UID:{expected}" in content


def test_all_day_event_uses_non_inclusive_dtend() -> None:
    content = ICSFormatter().format(
        publish_data={Semester.FALL: {Term.ALEPH: [_sample_exam(exam_date=date(2026, 1, 10))]}}
    )
    assert "DTSTART;VALUE=DATE:20260110" in content
    assert "DTEND;VALUE=DATE:20260111" in content


def test_timed_event_uses_timezone_aware_datetimes() -> None:
    exam = _sample_exam(start_time=time(9, 0), end_time=time(11, 0))
    content = ICSFormatter().format(publish_data={Semester.FALL: {Term.ALEPH: [exam]}})

    assert "DTSTART;TZID=Asia/Jerusalem" in content
    assert "DTEND;TZID=Asia/Jerusalem" in content
    assert "VALUE=DATE" not in content


def test_empty_structured_data_returns_empty_string() -> None:
    assert ICSFormatter().format(publish_data={}) == ""
    assert ICSFormatter().format() == ""