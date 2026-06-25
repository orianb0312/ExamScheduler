"""
Calendar Sync Compatibility & Character Protection Tests
=========================================================
Validates that ICSFormatter produces .ics output that is safe for Hebrew
content across real calendar platforms.

Covers: UTF-8 encoding integrity, timezone anchoring (Asia/Jerusalem),
all-day event fallback (VALUE=DATE), and RFC-5545 structural validity.

"""

from __future__ import annotations

from datetime import date, time


from src.models.enums import Semester, Term
from src.output.ics_formatter import ICSFormatter
from src.output.output_models import ScheduledExam


# A realistic, deliberately complex Hebrew course title (spaces + final letters).
HEBREW_COURSE_NAME = "מבני נתונים ואלגוריתמים"
HEBREW_INSTRUCTOR = 'ד"ר עדה לבלייס'


def _exam(**overrides) -> ScheduledExam:
    """Build a ScheduledExam, Hebrew by default, overridable per test."""
    defaults = dict(
        course_name=HEBREW_COURSE_NAME,
        course_id=10001,
        semester=Semester.FALL,
        term=Term.ALEPH,
        exam_date=date(2026, 1, 10),
        instructor=HEBREW_INSTRUCTOR,
    )
    defaults.update(overrides)
    return ScheduledExam(**defaults)


def _format(**exams_by_kind) -> str:
    """Convenience wrapper to format a single Hebrew exam as publish data."""
    return ICSFormatter().format(
        publish_data={Semester.FALL: {Term.ALEPH: [_exam(**exams_by_kind)]}}
    )


# ---------------------------------------------------------------------------
# Character protection — the heart of this subtask
# ---------------------------------------------------------------------------

def test_hebrew_course_name_survives_intact_in_output():
    """The exact Hebrew title must appear unmodified in the .ics text."""
    content = _format()
    assert HEBREW_COURSE_NAME in content
    assert HEBREW_INSTRUCTOR in content


def test_output_encodes_to_utf8_without_corruption_or_bom():
    """
    Round-trip the output through UTF-8 bytes, the way it is written to disk.
    No BOM (which trips some strict parsers) and the Hebrew must decode back
    byte-for-byte identical.
    """
    content = _format()
    encoded = content.encode("utf-8")

    # A UTF-8 BOM at the start breaks several .ics parsers; ensure none.
    assert not encoded.startswith(b"\xef\xbb\xbf")

    decoded = encoded.decode("utf-8")
    assert decoded == content
    assert HEBREW_COURSE_NAME in decoded


def test_hebrew_characters_are_multibyte_as_expected():
    """
    Sanity check that the Hebrew really is non-ASCII multibyte content
    (each Hebrew letter is 2 bytes in UTF-8) — i.e. we are genuinely
    exercising character protection, not accidentally testing ASCII.
    """
    encoded = HEBREW_COURSE_NAME.encode("utf-8")
    # More bytes than characters proves multibyte encoding is in play.
    assert len(encoded) > len(HEBREW_COURSE_NAME)


# ---------------------------------------------------------------------------
# Timezone anchoring
# ---------------------------------------------------------------------------

def test_timed_exam_is_anchored_to_asia_jerusalem():
    """A timed exam must carry the explicit TZID so external apps do not shift it."""
    content = _format(start_time=time(9, 0), end_time=time(11, 0))
    assert "DTSTART;TZID=Asia/Jerusalem:20260110T090000" in content
    assert "DTEND;TZID=Asia/Jerusalem:20260110T110000" in content
    # A timed event must not also be declared as an all-day VALUE=DATE event.
    assert "VALUE=DATE" not in content


def test_dateless_exam_falls_back_to_all_day_value_date():
    """
    An exam with no hours must export as an all-day event using VALUE=DATE,
    with a non-inclusive next-day DTEND, preventing arbitrary time-shifting.
    """
    content = _format(exam_date=date(2026, 1, 10))
    assert "DTSTART;VALUE=DATE:20260110" in content
    assert "DTEND;VALUE=DATE:20260111" in content
    assert "TZID=Asia/Jerusalem" not in content


# ---------------------------------------------------------------------------
# RFC-5545 structural validity (so external validators accept the file)
# ---------------------------------------------------------------------------

def test_calendar_wrapper_and_event_blocks_are_balanced():
    """VCALENDAR and every VEVENT must open and close correctly."""
    content = _format()
    lines = content.split("\r\n")

    assert lines[0] == "BEGIN:VCALENDAR"
    assert lines[-1] == "END:VCALENDAR"
    assert content.count("BEGIN:VEVENT") == content.count("END:VEVENT") == 1
    assert "VERSION:2.0" in content
    assert "METHOD:PUBLISH" in content


def test_lines_use_crlf_endings():
    """RFC 5545 requires CRLF line breaks; bare LF must not appear."""
    content = _format()
    # Every newline must be part of a CRLF pair.
    assert content.count("\n") == content.count("\r\n")


def test_required_event_properties_present_for_hebrew_event():
    """A published Hebrew event still carries UID, DTSTAMP, and a confirmed status."""
    content = _format()
    assert "UID:" in content
    assert "@examscheduler.local" in content
    assert "DTSTAMP:" in content
    assert "STATUS:CONFIRMED" in content


def test_multiple_hebrew_events_each_get_distinct_uid():
    """Two different Hebrew exams must not collide on the same UID."""
    content = ICSFormatter().format(
        publish_data={
            Semester.FALL: {
                Term.ALEPH: [
                    _exam(course_name="מבני נתונים", course_id=10001),
                    _exam(course_name="מערכות הפעלה", course_id=10002),
                ]
            }
        }
    )
    uids = [line for line in content.splitlines() if line.startswith("UID:")]
    assert len(uids) == 2
    assert uids[0] != uids[1]