"""
ICSFormatter tests
============================

  Group 1 — RFC 5545 line folding (_fold_line): 75-octet wrapping, continuation
            spaces, no mid-character splits on Hebrew, round-trip unfolding.
  Group 2 — Per-script month-cell budgeting & shortening (_summary_body,
            _shorten, _contains_hebrew): English keeps id, Hebrew shortens,
            mixed counts as Hebrew, word-boundary cuts.
  Group 3 — Cancellation prefix, mixed publish+cancel in one file, and
            multiple events.

Run:
    pytest tests/test_ics_formatter_extended.py -v
"""

from __future__ import annotations

from datetime import date, time

from src.models.enums import Semester, Term
from src.output.ics_formatter import ICSFormatter
from src.output.output_models import ScheduledExam


def _exam(**overrides) -> ScheduledExam:
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


def _publish(exam: ScheduledExam) -> str:
    return ICSFormatter().format(publish_data={Semester.FALL: {Term.ALEPH: [exam]}})


# ===========================================================================
# Group 1 — Line folding (RFC 5545 §3.1)
# ===========================================================================

def test_no_output_line_exceeds_75_octets():
    """Every physical line, UTF-8 encoded, must be at most 75 bytes."""
    long_hebrew = "מבוא להנדסת תוכנה ומערכות מידע מתקדמות במיוחד לסטודנטים"
    content = _publish(_exam(course_name=long_hebrew, instructor="פרופ' ישראל ישראלי הגדול"))
    for line in content.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75, f"line over 75 octets: {line!r}"


def test_folded_continuation_lines_start_with_single_space():
    """A folded line continues on the next line, prefixed by exactly one space."""
    long_hebrew = "מבוא להנדסת תוכנה ומערכות מידע מתקדמות במיוחד לסטודנטים"
    content = _publish(_exam(course_name=long_hebrew))
    physical = content.split("\r\n")
    # At least one continuation line must exist for this long input.
    continuations = [ln for ln in physical if ln.startswith(" ")]
    assert continuations
    for ln in continuations:
        assert not ln.startswith("  ")  # exactly one leading space, not two


def test_folding_never_splits_a_hebrew_character():
    """
    Folding happens on byte boundaries, but a multibyte Hebrew character must
    never be cut between two lines. We prove it by unfolding and confirming the
    full Hebrew string survived intact.
    """
    long_hebrew = "מבני נתונים ואלגוריתמים מתקדמים ומבני נתונים גאומטריים יעילים"
    content = _publish(_exam(course_name=long_hebrew))
    unfolded = content.replace("\r\n ", "")  # RFC unfolding: CRLF + space -> nothing
    assert long_hebrew in unfolded


def test_unfolding_round_trips_to_logical_content():
    """Unfolding the output must reconstruct the logical (pre-fold) lines."""
    long_hebrew = "מבוא להנדסת תוכנה ומערכות מידע מתקדמות במיוחד לסטודנטים"
    content = _publish(_exam(course_name=long_hebrew, instructor="פרופ' דנה כהן הגדולה מאוד"))
    unfolded = content.replace("\r\n ", "")
    # The DESCRIPTION logical line should be whole and contain the full name.
    assert f"DESCRIPTION:Exam: {long_hebrew}" in unfolded


def test_short_line_is_not_folded():
    """A line already within 75 octets must be emitted unchanged."""
    content = _publish(_exam(course_name="Algorithms"))
    assert "SUMMARY:Algorithms (10001)" in content.split("\r\n")


# ===========================================================================
# Group 2 — Per-script budgeting & shortening
# ===========================================================================

def test_contains_hebrew_detection():
    assert ICSFormatter._contains_hebrew("מבני נתונים")
    assert ICSFormatter._contains_hebrew("Java בשפת")          # mixed
    assert not ICSFormatter._contains_hebrew("Data Structures")  # pure English
    assert not ICSFormatter._contains_hebrew("Physics 1")


def test_english_name_keeps_id_in_summary():
    content = _publish(_exam(course_name="Data Structures", course_id=83101))
    summary = next(l for l in content.splitlines() if l.startswith("SUMMARY:"))
    assert summary == "SUMMARY:Data Structures (83101)"


def test_long_hebrew_name_drops_id_and_adds_ellipsis():
    content = _publish(_exam(course_name="מבני נתונים ואלגוריתמים", course_id=10001))
    summary = next(l for l in content.splitlines() if l.startswith("SUMMARY:"))
    body = summary[len("SUMMARY:"):]
    assert "(10001)" not in body
    assert body.endswith("\u2026")


def test_mixed_language_name_uses_hebrew_budget():
    """
    A name with any Hebrew uses the tighter Hebrew budget. 'תכנות מונחה עצמים
    בשפת Java' (27 chars) exceeds the Hebrew budget, so it must be shortened.
    """
    content = _publish(_exam(course_name="תכנות מונחה עצמים בשפת Java", course_id=83130))
    summary = next(l for l in content.splitlines() if l.startswith("SUMMARY:"))
    body = summary[len("SUMMARY:"):]
    assert body.endswith("\u2026")
    assert len(body) <= ICSFormatter.HEBREW_MAX_CHARS + 1


def test_shorten_cuts_on_word_boundary():
    """The shortened name should not end mid-word (the char before … is a real
    word end, not a clipped fragment)."""
    fmt = ICSFormatter()
    result = fmt._shorten("מבני נתונים ואלגוריתמים")
    # Expected to cut after a whole word, then ellipsis.
    assert result.endswith("\u2026")
    assert " " not in result[-2:]  # no dangling space right before the ellipsis


def test_description_keeps_full_name_even_when_summary_shortened():
    long_name = "מבני נתונים ואלגוריתמים"
    content = _publish(_exam(course_name=long_name, course_id=10001))
    unfolded = content.replace("\r\n ", "")
    assert f"DESCRIPTION:Exam: {long_name} (10001)" in unfolded


# ===========================================================================
# Group 3 — Cancellation, mixed publish+cancel, multiple events
# ===========================================================================

def test_cancellation_adds_prefix_and_sequence():
    content = ICSFormatter().format(
        cancel_data={Semester.FALL: {Term.ALEPH: [_exam(course_name="Algorithms")]}}
    )
    assert "STATUS:CANCELLED" in content
    assert "SEQUENCE:1" in content
    assert "[CANCELED] " in content


def test_publish_uses_confirmed_status_and_no_cancel_prefix():
    content = _publish(_exam(course_name="Algorithms"))
    assert "STATUS:CONFIRMED" in content
    assert "SEQUENCE:0" in content
    assert "[CANCELED]" not in content


def test_mixed_publish_and_cancel_in_single_file():
    """The formatter advertises mixing CANCELLED and CONFIRMED in one PUBLISH."""
    content = ICSFormatter().format(
        publish_data={Semester.FALL: {Term.ALEPH: [_exam(course_name="Databases", course_id=10002)]}},
        cancel_data={Semester.FALL: {Term.ALEPH: [_exam(course_name="Algorithms", course_id=10001)]}},
    )
    assert "STATUS:CANCELLED" in content
    assert "STATUS:CONFIRMED" in content
    # Both event identities present.
    assert content.count("BEGIN:VEVENT") == 2
    assert content.count("END:VEVENT") == 2


def test_multiple_events_each_emit_their_own_vevent():
    exams = [
        _exam(course_name="Algorithms", course_id=10001),
        _exam(course_name="Databases", course_id=10002),
        _exam(course_name="Networks", course_id=10003),
    ]
    content = ICSFormatter().format(publish_data={Semester.FALL: {Term.ALEPH: exams}})
    assert content.count("BEGIN:VEVENT") == 3
    assert content.count("END:VEVENT") == 3
    uids = [l for l in content.splitlines() if l.startswith("UID:")]
    assert len(uids) == len(set(uids)) == 3  # all present and distinct


def test_events_across_multiple_semesters_and_terms():
    content = ICSFormatter().format(
        publish_data={
            Semester.FALL: {
                Term.ALEPH: [_exam(course_name="Algorithms", course_id=10001)],
                Term.BET: [_exam(course_name="Databases", course_id=10002)],
            },
            Semester.SPRING: {
                Term.ALEPH: [_exam(course_name="Networks", course_id=10003)],
            },
        }
    )
    assert content.count("BEGIN:VEVENT") == 3


def test_short_hebrew_name_fits_without_shortening():
    """A short Hebrew name stays within the Hebrew budget and is not truncated."""
    content = _publish(_exam(course_name="מערכות הפעלה", course_id=10003))
    summary = next(l for l in content.splitlines() if l.startswith("SUMMARY:"))
    body = summary[len("SUMMARY:"):]
    assert not body.endswith("\u2026")
    assert len(body) <= ICSFormatter.HEBREW_MAX_CHARS + 1


def test_no_summary_body_exceeds_its_script_budget():
    """Sweep several names; no SUMMARY may exceed the budget for its script."""
    cases = [
        ("Data Structures", 83101),
        ("Digital Systems", 83120),
        ("Physics 1", 83102),
        ("מבני נתונים ואלגוריתמים", 10001),
        ("מערכות הפעלה", 10003),
        ("תכנות מונחה עצמים בשפת Java", 83130),
    ]
    for name, cid in cases:
        content = _publish(_exam(course_name=name, course_id=cid))
        body = next(
            l for l in content.splitlines() if l.startswith("SUMMARY:")
        )[len("SUMMARY:"):]
        budget = (
            ICSFormatter.HEBREW_MAX_CHARS
            if ICSFormatter._contains_hebrew(name)
            else ICSFormatter.ENGLISH_MAX_CHARS
        )
        assert len(body) <= budget + 1, f"{name!r} body too long: {body!r}"