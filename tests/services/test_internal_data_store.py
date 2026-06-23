from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from src.models.academic import Course, Exam, ProgramAffiliation
from src.models.enums import RequirementType, Semester, Term
from src.models.scheduling import DateExclusion, ExamPeriod
from src.services.file_loading_service import FileLoadingService, LoadedSchedulerInput
from src.services.internal_data_store import CACHE_VERSION, InternalDataStore


def test_internal_store_saves_and_loads_processed_data_when_sources_match(tmp_path):
    courses_file, dates_file = _write_source_files(tmp_path)
    store = InternalDataStore(tmp_path / "processed_input.json")
    data = _loaded_data()

    store.save(courses_file, dates_file, data.courses, data.exam_periods)

    restored = store.load_if_current(courses_file, dates_file)

    assert restored is not None
    assert restored.courses[0].course_id == 10001
    assert restored.courses[0].evaluation.requires_scheduling()
    assert restored.courses[0].affiliations[0].requirement_type == RequirementType.OBLIGATORY
    assert restored.exam_periods[0].term == Term.ALEPH
    assert restored.exam_periods[0].exclusions[0].start_date == date(2026, 1, 3)


def test_internal_store_ignores_saved_data_when_source_file_changes(tmp_path):
    courses_file, dates_file = _write_source_files(tmp_path)
    store = InternalDataStore(tmp_path / "processed_input.json")
    data = _loaded_data()
    store.save(courses_file, dates_file, data.courses, data.exam_periods)

    courses_file.write_text("changed source content", encoding="utf-8")

    assert store.load_if_current(courses_file, dates_file) is None


def test_file_loading_service_uses_internal_store_when_files_are_unchanged(tmp_path):
    courses_file, dates_file = _write_source_files(tmp_path)
    store = InternalDataStore(tmp_path / "processed_input.json")
    first_service = FileLoadingService(
        parser_adapter=_FakeParserAdapter(_loaded_data()),
        internal_store=store,
    )
    first_service.load_selected_files(courses_file, dates_file)

    second_service = FileLoadingService(
        parser_adapter=_FailingParserAdapter(),
        internal_store=store,
    )

    result = second_service.load_selected_files(courses_file, dates_file)

    assert result.loaded_data.course_count == 1
    assert result.loaded_data.exam_period_count == 1
    assert result.loaded_data.program_ids_as_strings == ["83101"]


def test_file_loading_service_reparses_when_source_files_change(tmp_path):
    courses_file, dates_file = _write_source_files(tmp_path)
    store = InternalDataStore(tmp_path / "processed_input.json")
    first_parser = _FakeParserAdapter(_loaded_data(course_id=10001))
    FileLoadingService(first_parser, store).load_selected_files(courses_file, dates_file)

    courses_file.write_text("changed source content", encoding="utf-8")
    second_parser = _FakeParserAdapter(_loaded_data(course_id=20001))

    result = FileLoadingService(second_parser, store).load_selected_files(
        courses_file,
        dates_file,
    )

    assert second_parser.call_count == 1
    assert result.loaded_data.courses[0].course_id == 20001


def test_is_cache_stale_detects_modified_source(tmp_path):
    courses_file, dates_file = _write_source_files(tmp_path)
    store = InternalDataStore(tmp_path / "processed_input.json")
    data = _loaded_data()
    store.save(courses_file, dates_file, data.courses, data.exam_periods)

    # Identical files: the cache matches, so it is not stale.
    assert store.is_cache_stale(courses_file, dates_file) is False

    # Editing a source file changes its SHA256, so the cache is now stale.
    courses_file.write_text("changed source content", encoding="utf-8")
    assert store.is_cache_stale(courses_file, dates_file) is True


def test_corrupt_cache_is_treated_as_missing_instead_of_crashing(tmp_path):
    courses_file, dates_file = _write_source_files(tmp_path)
    cache_file = tmp_path / "processed_input.json"
    store = InternalDataStore(cache_file)

    # Simulate a half-written or hand-corrupted cache file.
    cache_file.write_text("{ this is not valid json", encoding="utf-8")

    # A corrupt cache must not raise; it is ignored so a fresh parse can run.
    assert store.load_if_current(courses_file, dates_file) is None
    assert store.is_cache_stale(courses_file, dates_file) is False


def test_cache_with_outdated_version_is_rejected(tmp_path):
    courses_file, dates_file = _write_source_files(tmp_path)
    cache_file = tmp_path / "processed_input.json"
    store = InternalDataStore(cache_file)
    data = _loaded_data()

    # Save normally so the fingerprints match the current files exactly.
    store.save(courses_file, dates_file, data.courses, data.exam_periods)

    # Then bump only the version to simulate a cache from an older app build.
    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    payload["version"] = CACHE_VERSION + 1
    cache_file.write_text(json.dumps(payload), encoding="utf-8")

    # Even though the source files are unchanged, the version mismatch must
    # reject the cache so the newer code re-parses instead of trusting old data.
    assert store.load_if_current(courses_file, dates_file) is None


class _FakeParserAdapter:
    def __init__(self, data: LoadedSchedulerInput) -> None:
        self._data = data
        self.call_count = 0

    def parse_files(self, courses_file: Path, exam_dates_file: Path) -> LoadedSchedulerInput:
        self.call_count += 1
        return self._data


class _FailingParserAdapter:
    def parse_files(self, courses_file: Path, exam_dates_file: Path) -> LoadedSchedulerInput:
        raise AssertionError("Parser should not be called when internal data is current.")


def _write_source_files(tmp_path: Path) -> tuple[Path, Path]:
    courses_file = tmp_path / "courses.txt"
    dates_file = tmp_path / "exam_dates.txt"
    courses_file.write_text("original courses", encoding="utf-8")
    dates_file.write_text("original dates", encoding="utf-8")
    return courses_file, dates_file


def _loaded_data(course_id: int = 10001) -> LoadedSchedulerInput:
    course = Course(
        course_id=course_id,
        name="Algorithms",
        instructor="Dr. Ada",
        evaluation=Exam(),
        affiliations=[
            ProgramAffiliation(
                program_id=83101,
                year=1,
                semester=Semester.FALL,
                requirement_type=RequirementType.OBLIGATORY,
            ),
        ],
    )
    period = ExamPeriod(
        semester=Semester.FALL,
        term=Term.ALEPH,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 10),
        exclusions=[DateExclusion(start_date=date(2026, 1, 3))],
    )
    return LoadedSchedulerInput(courses=(course,), exam_periods=(period,), programs=())