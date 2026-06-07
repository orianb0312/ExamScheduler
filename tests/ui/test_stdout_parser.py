from src.services.schedule_output_service import BATCH_END_MARKER, StdoutScheduleParser


def test_parser_emits_complete_system_blocks_when_next_marker_arrives():
    parser = StdoutScheduleParser()

    systems = parser.feed(
        "log line\n"
        "Complete System #1\n"
        "=== SEMESTER: FALL ===\n"
        "  Course A | 2026-01-01 | Dr. A\n"
        "Complete System #2\n"
        "=== SEMESTER: FALL ===\n"
    )

    assert len(systems) == 1
    assert systems[0].number == 1
    assert "Course A" in systems[0].text

    final = parser.flush()

    assert len(final) == 1
    assert final[0].number == 2


def test_parser_handles_chunked_partial_stdout_markers():
    parser = StdoutScheduleParser()

    assert parser.feed("Complete Sy") == []
    systems = parser.feed("stem #1\nCourse A\nComplete System #2\nCourse B\n")

    assert len(systems) == 1
    assert systems[0].number == 1
    assert "Course A" in systems[0].text
    assert parser.flush()[0].number == 2


def test_parser_ignores_summary_lines_without_schedule_markers():
    parser = StdoutScheduleParser()

    assert parser.feed("Complete systems: 12\nWritten systems: 0\n") == []
    assert parser.flush() == []


def test_parser_supports_period_schedule_markers_too():
    parser = StdoutScheduleParser()

    parser.feed("Schedule #7\nCourse A\nSchedule #8\nCourse B\n")
    systems = parser.feed("Schedule #9\nCourse C\n")

    assert [system.number for system in systems] == [8]
    assert parser.flush()[0].number == 9


def test_parser_flushes_last_system_when_batch_marker_arrives():
    parser = StdoutScheduleParser()

    systems = parser.feed(
        "Complete System #1\n"
        "Course A\n"
        f"{BATCH_END_MARKER}\n"
    )

    assert len(systems) == 1
    assert systems[0].number == 1
    assert "Course A" in systems[0].text
    assert parser.flush() == []
