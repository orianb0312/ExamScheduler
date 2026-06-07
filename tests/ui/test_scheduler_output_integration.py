from __future__ import annotations

from datetime import date

from pytestqt.qtbot import QtBot

from src.models.academic import Course, Exam, ProgramAffiliation
from src.models.enums import RequirementType, Semester, Term
from src.models.scheduling import ExamPeriod
from src.rules.academic_conflict_rule import AcademicConflictRule
from src.services.file_loading_service import LoadedSchedulerInput
from src.services.schedule_output_service import (
    ScheduleOutputDataAdapter,
    StdoutScheduleParser,
)
from src.solver.complete_scheduler import CompleteSystemScheduler
from src.ui.calendar_view_panel import _DayCell
from src.ui.main_window import MainWindow


def test_scheduler_output_reaches_output_screen_calendar(tmp_path, qtbot: QtBot) -> None:
    course = Course(
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
    period = ExamPeriod(
        semester=Semester.FALL,
        term=Term.ALEPH,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 1),
    )

    scheduler = CompleteSystemScheduler([AcademicConflictRule()])
    generated_system = next(
        scheduler.stream_complete_systems([(period, [course])]).systems
    )

    parser = StdoutScheduleParser()
    raw_systems = parser.feed(generated_system.text) + parser.flush()
    adapter = ScheduleOutputDataAdapter(
        courses=[course],
        selected_program_ids=["83101"],
    )

    window = MainWindow(project_root=tmp_path)
    qtbot.addWidget(window)
    window.input_panel.notify_data_loaded(
        LoadedSchedulerInput(
            courses=(course,),
            exam_periods=(period,),
            programs=(),
        )
    )
    window.output_view.add_systems(adapter.convert(raw_systems))

    cached_system = window.output_view.cache.get_page(1)[0]
    cached_exam = cached_system.periods[0].exams[0]
    cells = {
        int(cell.text()): cell
        for cell in window.output_view.findChildren(_DayCell)
        if cell.text().isdigit()
    }

    assert cached_system.number == 1
    assert cached_exam.course_id == 10001
    assert cached_exam.program_ids == (83101,)
    assert cached_exam.requirement_types == ("Obligatory",)
    assert window.output_view.schedule_label.text() == "Schedule 1 of 1"
    assert "Algorithms (10001)" in cells[1].exam_text()
    assert "83101 | Obligatory" in cells[1].exam_text()
