import json
import time
from datetime import date

from src.output.output_manager import TextOutputManager
from src.models.academic import Course, Exam, ProgramAffiliation
from src.models.enums import RequirementType, Semester, Term
from src.models.scheduling import ExamPeriod
from src.rules.academic_conflict_rule import AcademicConflictRule
from src.rules.advanced_constraints_rule import AdvancedConstraintsRule
from src.solver.complete_scheduler import (
    DEFAULT_COMPLETE_SYSTEM_BATCH_SIZE,
    CompleteSystemScheduler,
    DiskAssignmentStore,
    PeriodScheduleSet,
    ScheduleGenerationTimedOut,
)
from src.sorting.schedule_priority import MANDATORY_MIN_GAP


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


def _three_mandatory_courses():
    return [
        Course(10001, "Algorithms", "Dr. A", Exam(), [_affiliation()]),
        Course(10002, "Databases", "Dr. B", Exam(), [_affiliation()]),
        Course(10003, "Physics", "Dr. C", Exam(), [_affiliation()]),
    ]


def _period(term, month):
    return ExamPeriod(
        semester=Semester.FALL,
        term=term,
        start_date=date(2026, month, 1),
        end_date=date(2026, month, 2),
        exclusions=[],
    )


def _wide_period():
    return ExamPeriod(
        semester=Semester.FALL,
        term=Term.ALEPH,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 4),
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


def test_mandatory_span_does_not_prune_valid_partial_assignments():
    scheduler = CompleteSystemScheduler([
        AcademicConflictRule(),
        AdvancedConstraintsRule(
            max_elective_conflicts=99,
            min_mandatory_span=2,
            max_daily_exams=99,
        ),
    ])

    result = scheduler.count_complete_systems([
        (_wide_period(), _three_mandatory_courses()),
    ])

    assert result.period_schedule_counts == [24]
    assert result.complete_system_count == 24


def test_on_demand_stream_keeps_valid_mandatory_span_completions():
    scheduler = CompleteSystemScheduler([
        AcademicConflictRule(),
        AdvancedConstraintsRule(
            max_elective_conflicts=99,
            min_mandatory_span=2,
            max_daily_exams=99,
        ),
    ])

    stream = scheduler.stream_complete_systems_on_demand([
        (_wide_period(), _three_mandatory_courses()),
    ])

    assert sum(1 for _system in stream.systems) == 24


def test_disk_assignment_store_round_trips_assignments_after_spooling():
    first_date = date(2026, 1, 1)
    second_date = date(2026, 1, 2)
    store = DiskAssignmentStore(
        course_indices=[2, 0],
        date_to_id={first_date: 0, second_date: 1},
        id_to_date=[first_date, second_date],
        memory_limit_bytes=1,
    )

    try:
        store.append({2: second_date, 0: first_date})

        assert len(store) == 1
        assert store[0] == {2: second_date, 0: first_date}
        assert list(store) == [{2: second_date, 0: first_date}]
    finally:
        store.close()


def test_period_schedules_are_not_returned_as_materialized_lists():
    scheduler = CompleteSystemScheduler([AcademicConflictRule()])
    courses = _courses()
    schedule_sets = scheduler._build_period_schedule_sets(
        [(_period(Term.ALEPH, 1), courses)]
    )

    try:
        schedule_set = schedule_sets[0]

        assert not isinstance(schedule_set.schedules, list)
        assert schedule_set.count == 2

        first_assignment = schedule_set.schedules[0]
        second_assignment = schedule_set.schedules[1]

        assert set(first_assignment) == {0, 1}
        assert set(second_assignment) == {0, 1}
        assert first_assignment != second_assignment
    finally:
        scheduler._close_schedule_sets(schedule_sets)


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


def test_complete_system_write_orders_output_by_sort_priority(tmp_path):
    scheduler = CompleteSystemScheduler([AcademicConflictRule()])
    courses = _courses()

    result = scheduler.write_complete_systems(
        [(_wide_period(), courses)],
        _output_manager(tmp_path),
        max_systems=2,
        sort_priority=[MANDATORY_MIN_GAP],
    )

    output = result.output_path.read_text(encoding="utf-8")
    first_system = output.split("Complete System #2")[0]

    assert result.complete_system_count == 12
    assert result.written_system_count == 2
    assert "2026-01-01" in first_system
    assert "2026-01-04" in first_system


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


def test_complete_system_stream_handles_huge_schedule_sources_lazily():
    class HugeScheduleSource:
        def __init__(self):
            self.accessed_indexes = []

        def __len__(self):
            return 1_000_000_000

        def __getitem__(self, index):
            self.accessed_indexes.append(index)
            return {}

    class HugeSystemScheduler(CompleteSystemScheduler):
        def __init__(self):
            super().__init__([])
            self.source = HugeScheduleSource()

        def _build_period_schedule_sets(self, _period_course_sets):
            return [
                PeriodScheduleSet(
                    period=_period(Term.ALEPH, 1),
                    courses=[],
                    schedules=self.source,
                )
            ]

    scheduler = HugeSystemScheduler()
    stream = scheduler.stream_complete_systems([], max_systems=2)
    systems = list(stream.systems)

    assert stream.complete_system_count == 1_000_000_000
    assert [system.number for system in systems] == [1, 2]
    assert scheduler.source.accessed_indexes == [0, 1]


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


def test_on_demand_complete_system_stream_matches_exact_prefix():
    scheduler = CompleteSystemScheduler([AcademicConflictRule()])
    courses = _courses()
    period_sets = [
        (_wide_period(), courses),
        (_period(Term.BET, 2), courses),
    ]

    exact = [
        system.text
        for system in scheduler.stream_complete_systems(
            period_sets,
            max_systems=3,
        ).systems
    ]
    on_demand = [
        system.text
        for system in scheduler.stream_complete_systems_on_demand(
            period_sets,
            max_systems=3,
        ).systems
    ]

    assert on_demand == exact


def test_on_demand_complete_system_stream_honors_deadline():
    scheduler = CompleteSystemScheduler([AcademicConflictRule()])
    stream = scheduler.stream_complete_systems_on_demand(
        [(_wide_period(), _courses())],
        deadline=time.perf_counter() - 1.0,
    )

    try:
        next(stream.systems)
    except ScheduleGenerationTimedOut:
        pass
    else:
        raise AssertionError("on-demand stream should stop at an expired deadline")
