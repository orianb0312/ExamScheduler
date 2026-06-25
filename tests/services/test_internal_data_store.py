from __future__ import annotations

from datetime import date
from pathlib import Path

from src.models.academic import Course, Exam, ProgramAffiliation
from src.models.enums import RequirementType, Semester, Term
from src.models.scheduling import DateExclusion, ExamPeriod
from src.services.file_loading_service import FileLoadingService, LoadedSchedulerInput
from src.services.internal_data_store import InternalDataStore


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


def test_internal_store_retries_transient_windows_replace_lock(
    tmp_path,
    monkeypatch,
):
    courses_file, dates_file = _write_source_files(tmp_path)
    cache_file = tmp_path / "processed_input.json"
    store = InternalDataStore(cache_file)
    data = _loaded_data()
    real_replace = __import__("os").replace
    attempts = 0

    def intermittently_locked_replace(source, target):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError(5, "Access is denied")
        real_replace(source, target)

    monkeypatch.setattr(
        "src.services.internal_data_store.os.replace",
        intermittently_locked_replace,
    )
    monkeypatch.setattr(
        "src.services.internal_data_store.time.sleep",
        lambda _delay: None,
    )

    store.save(courses_file, dates_file, data.courses, data.exam_periods)

    assert attempts == 3
    assert store.load_if_current(courses_file, dates_file) is not None


def test_file_loading_continues_when_optional_cache_cannot_be_saved(tmp_path):
    courses_file, dates_file = _write_source_files(tmp_path)
    parser = _FakeParserAdapter(_loaded_data())

    class _LockedStore:
        def load_if_current(self, _courses_file, _dates_file):
            return None

        def save(self, *_args):
            raise PermissionError(5, "Access is denied")

    result = FileLoadingService(
        parser_adapter=parser,
        internal_store=_LockedStore(),
    ).load_selected_files(courses_file, dates_file)

    assert parser.call_count == 1
    assert result.loaded_data.course_count == 1
    assert result.loaded_data.exam_period_count == 1


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
