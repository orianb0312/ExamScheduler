import json
from datetime import date

from src.output.output_manager import TextOutputManager
from src.models.academic import Course, Exam, ProgramAffiliation
from src.models.enums import RequirementType, Semester, Term
from src.models.scheduling import ExamPeriod
from src.rules.academic_conflict_rule import AcademicConflictRule
from src.solver.complete_scheduler import CompleteSystemScheduler


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
