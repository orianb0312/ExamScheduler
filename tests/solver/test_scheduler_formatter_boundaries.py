import json
from datetime import date

from src.models.academic import Course, Exam, ProgramAffiliation
from src.models.enums import RequirementType, Semester, Term
from src.models.scheduling import ExamPeriod
from src.output.output_manager import TextOutputManager
from src.rules.academic_conflict_rule import AcademicConflictRule
from src.solver.complete_scheduler import CompleteSystemScheduler
from src.solver.period_scheduler import Scheduler


class MarkerScheduleFormatter:
    def format_master_header(self) -> str:
        return "CUSTOM MASTER HEADER\n"

    def format_empty_period(self, period: ExamPeriod) -> str:
        return f"CUSTOM EMPTY {period.semester.value}/{period.term.value}\n"

    def format_period_schedule(
        self,
        schedule_number,
        courses,
        period,
        assignment,
    ) -> str:
        return (
            f"CUSTOM PERIOD SCHEDULE {schedule_number} "
            f"{period.semester.value}/{period.term.value} "
            f"{len(courses)} courses {len(assignment)} assignments\n"
        )

    def format_period_schedule_block(self, period, courses, assignment) -> str:
        return (
            f"CUSTOM PERIOD BLOCK {period.semester.value}/{period.term.value} "
            f"{len(courses)} courses {len(assignment)} assignments\n"
        )

    def format_complete_header(
        self,
        complete_system_count,
        period_schedule_counts,
        period_course_counts=None,
        auto_limit_seconds=None,
    ) -> str:
        return f"CUSTOM COMPLETE HEADER {complete_system_count}\n"

    def format_complete_system(self, system_number, period_blocks) -> str:
        return f"CUSTOM COMPLETE SYSTEM {system_number}\n" + "".join(period_blocks)

    def format_complete_truncation(self, written_count, complete_system_count) -> str:
        return f"CUSTOM TRUNCATED {written_count}/{complete_system_count}\n"

    def format_auto_truncation(
        self,
        written_count,
        complete_system_count,
        time_limit_seconds,
    ) -> str:
        return (
            f"CUSTOM AUTO TRUNCATED {written_count}/{complete_system_count} "
            f"{time_limit_seconds}\n"
        )


def _course() -> Course:
    return Course(
        course_id=10001,
        name="Algorithms",
        instructor="Dr. Ada",
        evaluation=Exam(),
        affiliations=[
            ProgramAffiliation(
                program_id=83101,
                year=1,
                semester=Semester.FALL,
                requirement_type=RequirementType.OBLIGATORY,
            )
        ],
    )


def _period() -> ExamPeriod:
    return ExamPeriod(
        semester=Semester.FALL,
        term=Term.ALEPH,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 1),
    )


def _output_manager(tmp_path) -> TextOutputManager:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "output_settings": {
                    "base_directory": str(tmp_path / "output"),
                    "master_filename": "custom_schedule",
                }
            }
        ),
        encoding="utf-8",
    )
    return TextOutputManager(str(config_path))


def test_period_scheduler_uses_injected_formatter(tmp_path):
    output_manager = _output_manager(tmp_path)
    scheduler = Scheduler(
        [AcademicConflictRule()],
        schedule_formatter=MarkerScheduleFormatter(),
    )

    scheduler.run_to_output([_course()], _period(), output_manager)

    output = output_manager.get_full_path().read_text(encoding="utf-8")
    assert "CUSTOM MASTER HEADER" in output
    assert "CUSTOM PERIOD SCHEDULE 1 FALL/Aleph 1 courses 1 assignments" in output
    assert "OFFICIAL UNIVERSITY" not in output


def test_complete_scheduler_uses_injected_formatter_for_streams():
    scheduler = CompleteSystemScheduler(
        [AcademicConflictRule()],
        schedule_formatter=MarkerScheduleFormatter(),
    )

    generated = next(scheduler.stream_complete_systems([(_period(), [_course()])]).systems)

    assert generated.text == (
        "CUSTOM COMPLETE SYSTEM 1\n"
        "CUSTOM PERIOD BLOCK FALL/Aleph 1 courses 1 assignments\n"
    )
