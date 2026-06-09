from datetime import date
from pathlib import Path

import pytest

from src.models.academic import Course, Exam, ProgramAffiliation
from src.models.enums import RequirementType
from src.models.enums import Semester, Term
from src.models.scheduling import ExamPeriod
from src.parser.file_parser import parse_catalog_text
from src.services.cli_run_service import SchedulerRunConfigBuilder, SchedulerRunForm
from src.services.scheduler_input_state import SchedulerInputState, format_courses


def _period() -> ExamPeriod:
    return ExamPeriod(
        semester=Semester.FALL,
        term=Term.ALEPH,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 3),
    )


def _course(program_id: int = 83108) -> Course:
    return Course(
        course_id=77777,
        name="Dynamic Program Course",
        instructor="Dr. Runtime",
        evaluation=Exam(),
        affiliations=[
            ProgramAffiliation(
                program_id=program_id,
                year=2,
                semester=Semester.SUMMER,
                requirement_type=RequirementType.OBLIGATORY,
            )
        ],
    )


def _form(tmp_path: Path) -> SchedulerRunForm:
    return SchedulerRunForm(
        project_root=tmp_path,
        mode="complete-count",
        output_config_text=str(tmp_path / "config.json"),
        period_indexes_text="",
        max_systems_text="",
        time_limit_text="30",
        course_file_text=str(tmp_path / "courses.txt"),
        dates_file_text=str(tmp_path / "original_dates.txt"),
    )


def test_scheduler_input_state_excludes_and_restores_days():
    state = SchedulerInputState(Path("runtime"))
    state.set_exam_periods([_period()])

    state.exclude_day(0, date(2026, 1, 2))
    assert not state.exam_periods[0].is_date_valid(date(2026, 1, 2))

    state.restore_day(0, date(2026, 1, 2))
    assert state.exam_periods[0].is_date_valid(date(2026, 1, 2))


def test_scheduler_input_state_updates_period_start_and_end_dates():
    state = SchedulerInputState(Path("runtime"))
    state.set_exam_periods([_period()])

    state.update_period_dates(0, date(2026, 1, 2), date(2026, 1, 4))

    assert state.exam_periods[0].start_date == date(2026, 1, 2)
    assert state.exam_periods[0].end_date == date(2026, 1, 4)


def test_scheduler_input_state_rejects_unknown_period_index():
    state = SchedulerInputState(Path("runtime"))
    state.set_exam_periods([_period()])

    with pytest.raises(ValueError, match="Unknown exam period index"):
        state.exclude_day(-1, date(2026, 1, 2))


def test_scheduler_input_state_writes_runtime_dates_file(tmp_path):
    state = SchedulerInputState(tmp_path / "runtime")
    state.set_exam_periods([_period()])
    state.exclude_day(0, date(2026, 1, 2))

    runtime_dates_file = state.write_exam_dates_file()

    assert runtime_dates_file == tmp_path / "runtime" / "ui_exam_dates.txt"
    assert runtime_dates_file.read_text(encoding="utf-8") == (
        "$$$$\n"
        "FALL,Aleph\n"
        "01-01-2026, 03-01-2026\n"
        "- 02-01-2026\n"
    )


def test_scheduler_input_state_formats_runtime_courses_for_the_existing_parser():
    text = format_courses([_course()])

    parsed_courses = parse_catalog_text(text)

    assert parsed_courses[0]["number"] == "77777"
    assert parsed_courses[0]["programs"][0]["number"] == "83108"
    assert parsed_courses[0]["programs"][0]["semester"] == "SUMM"
    assert parsed_courses[0]["evaluation"] == "Exam"


def test_run_config_uses_runtime_courses_file_when_data_was_loaded(tmp_path):
    state = SchedulerInputState(tmp_path / "runtime")
    state.set_selected_programs(["83108"])
    state.set_courses([_course()])
    state.set_exam_periods([_period()])

    config = SchedulerRunConfigBuilder(state).build(_form(tmp_path))

    assert config.course_file == tmp_path / "runtime" / "ui_courses.txt"
    assert config.user_file == tmp_path / "runtime" / "ui_selected_programs.txt"
    assert "83108,2,SUMM,Obligatory" in config.course_file.read_text(encoding="utf-8")
    assert config.user_file.read_text(encoding="utf-8") == "83108"


def test_run_config_uses_runtime_dates_file_when_day_state_exists(tmp_path):
    state = SchedulerInputState(tmp_path / "runtime")
    state.set_selected_programs(["83101"])
    state.set_exam_periods([_period()])
    state.update_period_dates(0, date(2026, 1, 2), date(2026, 1, 4))

    config = SchedulerRunConfigBuilder(state).build(_form(tmp_path))

    assert config.dates_file == tmp_path / "runtime" / "ui_exam_dates.txt"
    assert config.user_file == tmp_path / "runtime" / "ui_selected_programs.txt"
    assert "02-01-2026, 04-01-2026" in config.dates_file.read_text(encoding="utf-8")
