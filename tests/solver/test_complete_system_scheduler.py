import json
from datetime import date

from src.output.output_manager import TextOutputManager
from src.models.academic import Course, Exam, ProgramAffiliation
from src.models.enums import RequirementType, Semester, Term
from src.models.scheduling import ExamPeriod
from src.rules.academic_conflict_rule import AcademicConflictRule
from src.solver.complete_scheduler import (
    DEFAULT_COMPLETE_SYSTEM_BATCH_SIZE,
    CompleteSystemScheduler,
    PeriodScheduleSet,
)


def _affiliation():
    return ProgramAffiliation(
        program_id=83101,
        year=1,
        semester=Semester.FALL,
        requirement_type=RequirementType.OBLIGATORY,
    )


def _courses():
    return [
        Course(10001, "Algorithms", "Dr. A", Exam(), [_affiliation()]),
        Course(10002, "Databases", "Dr. B", Exam(), [_affiliation()]),
    ]


def _period(term, month):
    return ExamPeriod(
        semester=Semester.FALL,
        term=term,
        start_date=date(2026, month, 1),
        end_date=date(2026, month, 2),
        exclusions=[],
    )


def _output_manager(tmp_path):
    output_config = tmp_path / "config.json"
    output_config.write_text(
        json.dumps(
            {
                "output_settings": {
                    "base_directory": str(tmp_path / "output"),
                    "master_filename": "complete_systems",
                }
            }
        ),
        encoding="utf-8",
    )
    return TextOutputManager(str(output_config))


def test_complete_system_count_multiplies_period_counts():
    scheduler = CompleteSystemScheduler([AcademicConflictRule()])
    courses = _courses()

    result = scheduler.count_complete_systems(
        [
            (_period(Term.ALEPH, 1), courses),
            (_period(Term.BET, 2), courses),
        ]
    )

    assert result.period_course_counts == [2, 2]
    assert result.period_schedule_counts == [2, 2]
    assert result.complete_system_count == 4
    assert result.written_system_count == 0


def test_complete_system_write_respects_explicit_limit(tmp_path):
    scheduler = CompleteSystemScheduler([AcademicConflictRule()])
    courses = _courses()

    result = scheduler.write_complete_systems(
        [
            (_period(Term.ALEPH, 1), courses),
            (_period(Term.BET, 2), courses),
        ],
        _output_manager(tmp_path),
        max_systems=3,
    )

    assert result.complete_system_count == 4
    assert result.written_system_count == 3
    assert result.truncated is True

    output = result.output_path.read_text(encoding="utf-8")
    assert output.count("Complete System #") == 3
    assert "Stopped after writing 3 of 4 complete systems" in output


def test_complete_system_auto_writes_all_when_small(tmp_path):
    scheduler = CompleteSystemScheduler([AcademicConflictRule()])
    courses = _courses()

    result = scheduler.write_complete_systems_auto(
        [
            (_period(Term.ALEPH, 1), courses),
            (_period(Term.BET, 2), courses),
        ],
        _output_manager(tmp_path),
        time_limit_seconds=30.0,
    )

    assert result.complete_system_count == 4
    assert result.written_system_count == 4
    assert result.truncated is False

    output = result.output_path.read_text(encoding="utf-8")
    assert output.count("Complete System #") == 4
    assert "Total complete systems: 4" in output


def test_complete_system_stream_yields_incremental_batches():
    scheduler = CompleteSystemScheduler([AcademicConflictRule()])
    courses = _courses()

    stream = scheduler.stream_complete_systems(
        [
            (_period(Term.ALEPH, 1), courses),
            (_period(Term.BET, 2), courses),
        ]
    )
    batches = stream.iter_batches(batch_size=2)

    first_batch = next(batches)
    second_batch = next(batches)

    assert [system.number for system in first_batch] == [1, 2]
    assert [system.number for system in second_batch] == [3, 4]
    assert "Complete System #1" in first_batch[0].text
    assert "Complete System #4" in second_batch[1].text


def test_complete_system_stream_default_batch_size_is_1000():
    class ManySystemScheduler(CompleteSystemScheduler):
        def _build_period_schedule_sets(self, _period_course_sets):
            return [
                PeriodScheduleSet(
                    period=_period(Term.ALEPH, 1),
                    courses=[],
                    schedules=[{} for _ in range(DEFAULT_COMPLETE_SYSTEM_BATCH_SIZE + 1)],
                )
            ]

    stream = ManySystemScheduler([]).stream_complete_systems([])
    batches = stream.iter_batches()

    first_batch = next(batches)
    second_batch = next(batches)

    assert len(first_batch) == DEFAULT_COMPLETE_SYSTEM_BATCH_SIZE
    assert len(second_batch) == 1
    assert first_batch[0].number == 1
    assert second_batch[0].number == DEFAULT_COMPLETE_SYSTEM_BATCH_SIZE + 1


def test_complete_system_stream_does_not_rebuild_when_next_batch_is_requested():
    class CountingScheduler(CompleteSystemScheduler):
        def __init__(self):
            super().__init__([AcademicConflictRule()])
            self.build_count = 0

        def _build_period_schedule_sets(self, period_course_sets):
            self.build_count += 1
            return super()._build_period_schedule_sets(period_course_sets)

    scheduler = CountingScheduler()
    courses = _courses()

    stream = scheduler.stream_complete_systems(
        [
            (_period(Term.ALEPH, 1), courses),
            (_period(Term.BET, 2), courses),
        ]
    )
    batches = stream.iter_batches(batch_size=1)

    assert scheduler.build_count == 1
    assert next(batches)[0].number == 1
    assert next(batches)[0].number == 2
    assert scheduler.build_count == 1
