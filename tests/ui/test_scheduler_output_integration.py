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
from src.models.academic import Course, ProgramAffiliation
from src.models.enums import RequirementType, Semester
from src.services.schedule_output_service import (
    StdoutScheduleParser,
    ScheduleOutputDataAdapter,
    ScheduleSystem,
)
from src.ui.ui_cache import ScheduleCache

# Mock raw output chunks coming down from OS system pipes
STDOUT_CHUNK_A = "Complete System #1\n=== SEMESTER: FALL ===\n[TERM: Aleph]\nCalculus 1 | 2026-01-05 | Dr. Ada Lovelace\n"
STDOUT_CHUNK_B = "Complete System #2\n=== SEMESTER: FALL ===\n[TERM: Aleph]\nPhysics 1 | 2026-01-07 | Dr. Richard Feynman\n"


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
    assert window.output_view.schedule_label.text() == "1 of 1 schedules"
    assert "Algorithms (10001)" in cells[1].exam_text()
    assert "83101 | Obligatory" in cells[1].exam_text()


def test_output_stream_parsing_and_ui_cache_integration():
    """
    Integration Test: Simulates real-time unbuffered stdout chunk reception,
    metadata lookup decoration, and fixed-size batch UI pagination storage.
    """
    from src.models.academic import Exam

    # 1. Setup mock rich catalog inventory models with the mandatory Exam evaluation type argument
    calc_course = Course(10001, "Calculus 1", "Dr. Ada Lovelace", Exam())
    calc_course.add_affiliation(ProgramAffiliation(83101, 1, Semester.FALL, RequirementType.OBLIGATORY))

    physics_course = Course(10002, "Physics 1", "Dr. Richard Feynman", Exam())
    physics_course.add_affiliation(ProgramAffiliation(83101, 1, Semester.FALL, RequirementType.OBLIGATORY))

    # Initialize the interconnected pipeline modules
    parser = StdoutScheduleParser()
    adapter = ScheduleOutputDataAdapter(courses=[calc_course, physics_course], selected_program_ids=[83101])
    ui_cache = ScheduleCache(batch_size=1)  # Fixed batch size of 1 to rigorously force paging boundaries

    # 2. Simulate streaming chunk A arrival
    parsed_systems_a = parser.feed(STDOUT_CHUNK_A)
    # The parser buffers System #1 internally until a new marker pushes it out
    assert len(parsed_systems_a) == 0
    ui_cache.extend(adapter.convert(parsed_systems_a))

    # 3. Simulate streaming chunk B arrival
    parsed_systems_b = parser.feed(STDOUT_CHUNK_B)
    # Incoming System #2 marker successfully flushes completed System #1 out of the stream buffer
    assert len(parsed_systems_b) == 1
    ui_cache.extend(adapter.convert(parsed_systems_b))

    # 4. Flush the stream to capture the final remaining system block from memory
    final_flushed = parser.flush()
    assert len(final_flushed) == 1  # System #2 is captured on process termination
    ui_cache.extend(adapter.convert(final_flushed))

    # 5. Assert integrated pagination total calculations inside the cache layer
    assert ui_cache.system_count == 2
    assert ui_cache.batch_count == 2  # Two pages created because batch_size was set to 1

    # Validate that Page 1 holds enriched metadata retrieved from the catalog lookup map
    page_1_systems = ui_cache.get_page(1)
    assert len(page_1_systems) == 1

    target_exam = page_1_systems[0].periods[0].exams[0]
    assert target_exam.course_id == 10001
    assert target_exam.program_ids == (83101,)
    assert target_exam.requirement_types == ("Obligatory",)