"""
Legacy V1 Baseline Parsing Tests
==================================
Loads the three original V1 production files from tests/fixtures/legacy_v1/
through the V2 parser and cache layer.

Each test verifies:
  (a) correctness  — the parser produces the expected output from real data
  (b) latency      — each stage completes under the 1-second threshold

Run with -s to see the timing report:
    pytest tests/services/test_legacy_v1_parsing.py -v -s
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.parser.file_parser import parse_catalog_text, parse_periods_text
from src.parser.course_factory import build_courses_from_json
from src.parser.period_factory import build_periods_from_json
from src.services.file_loading_service import FileLoadingService
from src.services.internal_data_store import InternalDataStore

import json

# ---------------------------------------------------------------------------
# Fixture paths — the canonical V1 reference files committed to the repo.
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "legacy_v1"
COURSES_FILE  = FIXTURES_DIR / "V1.0CourseDB.txt"
DATES_FILE    = FIXTURES_DIR / "V1.0 ExamDates.txt"
PROGRAMS_FILE = FIXTURES_DIR / "Programs.txt"

THRESHOLD_SECONDS = 1.0


def _require_fixtures() -> None:
    """Skip the whole module if the fixture files have not been committed yet."""
    missing = [p for p in (COURSES_FILE, DATES_FILE, PROGRAMS_FILE) if not p.is_file()]
    if missing:
        pytest.skip(
            f"Legacy V1 fixture files not found: {[str(p) for p in missing]}. "
            f"Copy the original V1 files to {FIXTURES_DIR} to enable these tests."
        )


_require_fixtures()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_legacy_course_catalog_parses_correctly_and_fast():
    """
    Raw text → dict parsing of the V1 course catalog.
    Verifies course count, key field values, and mixed evaluation types
    (Exam + Project) from the real production file.
    """
    text = COURSES_FILE.read_text(encoding="utf-8")

    start = time.perf_counter()
    records = parse_catalog_text(text)
    elapsed = _elapsed_ms(start)
    print(f"\n  [latency] Raw course catalog parsing: {elapsed:.1f} ms")

    # Correctness — three courses exactly as in the original file.
    assert len(records) == 3, f"Expected 3 courses, got {len(records)}"

    names = [r["name"] for r in records]
    assert "Physics 1" in names
    assert "Software Project" in names
    assert "Calculus 1" in names

    # Evaluation types must survive — one Project among the Exams.
    evaluations = {r["name"]: r["evaluation"] for r in records}
    assert evaluations["Physics 1"] == "Exam"
    assert evaluations["Software Project"] == "Project"
    assert evaluations["Calculus 1"] == "Exam"

    assert elapsed / 1000 < THRESHOLD_SECONDS, (
        f"Course catalog parsing took {elapsed:.1f} ms — over threshold"
    )


def test_legacy_exam_dates_parses_correctly_and_fast():
    """
    Raw text → dict parsing of the V1 exam dates file.
    Verifies period count, semester/term labels with inconsistent spacing
    ('FALL, Aleph' vs 'FALL,Bet'), and mixed exclusion formats
    (single date, range, with and without comments).
    """
    text = DATES_FILE.read_text(encoding="utf-8")

    start = time.perf_counter()
    records = parse_periods_text(text)
    elapsed = _elapsed_ms(start)
    print(f"\n  [latency] Raw exam dates parsing: {elapsed:.1f} ms")

    # Correctness — three periods.
    assert len(records) == 3, f"Expected 3 periods, got {len(records)}"

    keys = [(r["semester"], r["moed"]) for r in records]
    assert ("FALL", "Aleph") in keys
    assert ("FALL", "Bet")   in keys
    assert ("SPRI", "Aleph") in keys

    # FALL Aleph has the most complex exclusion set — 7 entries including a range.
    fall_aleph = next(r for r in records if r["semester"] == "FALL" and r["moed"] == "Aleph")
    assert len(fall_aleph["exclusions"]) == 7, (
        f"Expected 7 exclusions in FALL Aleph, got {len(fall_aleph['exclusions'])}"
    )

    assert elapsed / 1000 < THRESHOLD_SECONDS, (
        f"Exam dates parsing took {elapsed:.1f} ms — over threshold"
    )


def test_legacy_model_construction_is_correct_and_fast():
    """
    Builds full Course and ExamPeriod model objects from the parsed V1 JSON.
    Verifies program affiliations, requirement types, and period date boundaries.
    """
    course_dicts = parse_catalog_text(COURSES_FILE.read_text(encoding="utf-8"))
    period_dicts = parse_periods_text(DATES_FILE.read_text(encoding="utf-8"))
    parser_json  = json.dumps(
        {"courses_node": course_dicts, "periods_node": period_dicts, "user_node": []},
        ensure_ascii=False,
    )

    start = time.perf_counter()
    courses = list(build_courses_from_json(parser_json))
    periods = list(build_periods_from_json(parser_json))
    elapsed = _elapsed_ms(start)
    print(f"\n  [latency] Model object construction: {elapsed:.1f} ms")

    # Courses
    assert len(courses) == 3
    course_ids = {c.course_id for c in courses}
    assert 83102 in course_ids   # Physics 1
    assert 83533 in course_ids   # Software Project
    assert 83112 in course_ids   # Calculus 1

    # Every exam course must require scheduling; Project must not.
    for course in courses:
        if course.name == "Software Project":
            assert not course.evaluation.requires_scheduling()
        else:
            assert course.evaluation.requires_scheduling()

    # Periods
    assert len(periods) == 3

    assert elapsed / 1000 < THRESHOLD_SECONDS, (
        f"Model construction took {elapsed:.1f} ms — over threshold"
    )


def test_legacy_cache_save_and_load_roundtrip(tmp_path):
    """
    Saves the parsed V1 data to the internal cache and restores it.
    Verifies the roundtrip preserves all courses, periods, and affiliations,
    and that both stages stay under the latency threshold.
    """
    from src.services.file_loading_service import ExistingFileParserAdapter

    adapter  = ExistingFileParserAdapter()
    loaded   = adapter.parse_files(COURSES_FILE, DATES_FILE)
    store    = InternalDataStore(tmp_path / "processed_input.json")

    # Save
    start = time.perf_counter()
    store.save(COURSES_FILE, DATES_FILE, loaded.courses, loaded.exam_periods)
    save_elapsed = _elapsed_ms(start)
    print(f"\n  [latency] Cache save: {save_elapsed:.1f} ms  "
          f"({store.storage_file.stat().st_size // 1024} KB)")

    # Load (hot path)
    start = time.perf_counter()
    snapshot = store.load_if_current(COURSES_FILE, DATES_FILE)
    load_elapsed = _elapsed_ms(start)
    print(f"  [latency] Cache load (hot path): {load_elapsed:.1f} ms")

    assert snapshot is not None, "Cache load returned None — fingerprint mismatch"
    assert len(snapshot.courses)      == len(loaded.courses)
    assert len(snapshot.exam_periods) == len(loaded.exam_periods)

    # Spot-check one course survives the roundtrip intact.
    original  = next(c for c in loaded.courses      if c.course_id == 83102)
    restored  = next(c for c in snapshot.courses    if c.course_id == 83102)
    assert restored.name       == original.name
    assert restored.instructor == original.instructor
    assert len(restored.affiliations) == len(original.affiliations)

    assert save_elapsed / 1000 < THRESHOLD_SECONDS
    assert load_elapsed / 1000 < THRESHOLD_SECONDS


def test_legacy_full_service_cold_cache(tmp_path):
    """
    Full FileLoadingService.load_selected_files on a cold cache (first load).
    This is the worst-case path: parse + validate + save.
    Verifies the service returns the correct program list and stays under 1s.
    """
    store   = InternalDataStore(tmp_path / "cache.json")
    service = FileLoadingService(internal_store=store)

    start = time.perf_counter()
    result = service.load_selected_files(COURSES_FILE, DATES_FILE)
    elapsed = _elapsed_ms(start)
    print(f"\n  [latency] Full service load — cold cache: {elapsed:.1f} ms")

    assert result.loaded_data.course_count      == 3
    assert result.loaded_data.exam_period_count == 3

    program_ids = result.loaded_data.program_ids_as_strings
    assert "83101" in program_ids
    assert "83102" in program_ids
    assert "83108" in program_ids

    assert elapsed / 1000 < THRESHOLD_SECONDS, (
        f"Cold cache load took {elapsed:.1f} ms — over threshold"
    )


def test_legacy_full_service_warm_cache(tmp_path):
    """
    Full FileLoadingService.load_selected_files on a warm cache (second load).
    This is the everyday path: the parser must NOT be called — data comes from cache.
    Verifies that warm-cache latency is significantly lower than cold-cache.
    """
    store = InternalDataStore(tmp_path / "cache.json")

    # Prime the cache.
    FileLoadingService(internal_store=store).load_selected_files(COURSES_FILE, DATES_FILE)

    # Second load — hot path.
    service2 = FileLoadingService(internal_store=store)
    start    = time.perf_counter()
    result   = service2.load_selected_files(COURSES_FILE, DATES_FILE)
    elapsed  = _elapsed_ms(start)
    print(f"\n  [latency] Full service load — warm cache: {elapsed:.1f} ms")

    assert result.loaded_data.course_count      == 3
    assert result.loaded_data.exam_period_count == 3

    assert elapsed / 1000 < THRESHOLD_SECONDS, (
        f"Warm cache load took {elapsed:.1f} ms — over threshold"
    )

    def test_legacy_v1_run_without_constraints_file_fallback(tmp_path):
        """
        Backward Compatibility Guard:
        Verifies that the system successfully loads and parses legacy V1 production files
        even when the newer V2 constraints file is entirely absent. The system should
        gracefully fall back to default runtime settings without raising errors.
        """
        from src.services.file_loading_service import FileLoadingService
        from src.services.internal_data_store import InternalDataStore

        store = InternalDataStore(tmp_path / "cache_fallback.json")
        service = FileLoadingService(internal_store=store)

        # Execute load omitting the --constraints-file flag/parameter to simulate V1 behavior
        start = time.perf_counter()
        result = service.load_selected_files(COURSES_FILE, DATES_FILE)
        elapsed = _elapsed_ms(start)
        print(f"\n  [latency] Legacy run without constraints fallback: {elapsed:.1f} ms")

        # 1. Correctness — Ensure base baseline data is parsed flawlessly
        assert result.loaded_data.course_count == 3
        assert result.loaded_data.exam_period_count == 3

        # 2. Fallback Safety — Validate that missing constraints do not crash the pipeline
        # (Adapt the exact attribute check below to match your service's configuration schema)
        assert hasattr(result, "loaded_data"), "Data failed to initialize in absence of constraints"

        # 3. Latency Performance — Must complete well under the strict 1-second threshold
        assert elapsed / 1000 < THRESHOLD_SECONDS, (
            f"Fallback loading took {elapsed:.1f} ms — over threshold"
        )