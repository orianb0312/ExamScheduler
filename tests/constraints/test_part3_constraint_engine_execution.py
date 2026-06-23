import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.models.academic import Course, Exam, ProgramAffiliation
from src.models.enums import RequirementType, Semester, Term
from src.models.scheduling import DateExclusion, ExamPeriod
from src.services.day_status_service import format_constraints, format_exam_periods
from src.services.scheduler_input_state import SchedulerInputState, format_courses
from src.workflow import run_complete_count_workflow


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "part3_req_2_2_mock_pairs.json"
)
ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_COURSES_PATH = ROOT_DIR / "data" / "V1.0CourseDB.txt"
DEFAULT_EXAM_PERIODS_PATH = ROOT_DIR / "data" / "V1.0 ExamDates.txt"
DEFAULT_PROGRAMS_PATH = ROOT_DIR / "data" / "Programs.txt"


@dataclass(frozen=True)
class ConstraintEngineCase:
    # Small cases make the expected schedule count easy to check by hand.
    requirement: str
    courses: tuple[Course, ...]
    selected_programs: tuple[int, ...]
    period: ExamPeriod
    constraints: dict[str, int]
    expected_schedule_count: int


def _course(
    course_id: int,
    name: str,
    requirement_type: RequirementType,
    program_id: int = 83101,
    year: int = 1,
) -> Course:
    return Course(
        course_id=course_id,
        name=name,
        instructor="Dr. Constraint",
        evaluation=Exam(),
        affiliations=[
            ProgramAffiliation(
                program_id=program_id,
                year=year,
                semester=Semester.FALL,
                requirement_type=requirement_type,
            )
        ],
    )


def _fall_period(start_day: int, end_day: int) -> ExamPeriod:
    return _period_with_required_exclusion(
        start_date=date(2026, 1, start_day),
        last_available_date=date(2026, 1, end_day),
    )


def _period_with_required_exclusion(
    start_date: date,
    last_available_date: date,
) -> ExamPeriod:
    # Phase 1 requires every period record to include at least one excluded
    # date. Put it after the useful test range so the expected counts stay
    # easy to reason about.
    excluded_date = last_available_date + timedelta(days=1)
    return ExamPeriod(
        semester=Semester.FALL,
        term=Term.ALEPH,
        start_date=start_date,
        end_date=excluded_date,
        exclusions=[DateExclusion(start_date=excluded_date)],
    )


def _req_2_1_case() -> ConstraintEngineCase:
    return ConstraintEngineCase(
        requirement="2.1",
        courses=(
            _course(91001, "Mandatory Alpha", RequirementType.OBLIGATORY),
            _course(91002, "Mandatory Beta", RequirementType.OBLIGATORY),
        ),
        selected_programs=(83101,),
        period=_fall_period(1, 4),
        constraints={"min_days_between_mandatory": 3},
        expected_schedule_count=2,
    )


def _req_2_2_case() -> ConstraintEngineCase:
    return ConstraintEngineCase(
        requirement="2.2",
        courses=(
            _course(92001, "Elective Alpha", RequirementType.ELECTIVE, year=2),
            _course(92002, "Elective Beta", RequirementType.ELECTIVE, year=2),
        ),
        selected_programs=(83101,),
        period=_fall_period(1, 3),
        constraints={"min_days_between_any": 2},
        expected_schedule_count=2,
    )


def _req_2_3_case() -> ConstraintEngineCase:
    return ConstraintEngineCase(
        requirement="2.3",
        courses=(
            _course(93001, "Elective Alpha", RequirementType.ELECTIVE),
            _course(93002, "Elective Beta", RequirementType.ELECTIVE),
            _course(93003, "Elective Gamma", RequirementType.ELECTIVE),
        ),
        selected_programs=(83101,),
        period=_fall_period(1, 2),
        constraints={"max_elective_conflicts": 1},
        expected_schedule_count=6,
    )


def _req_2_4_case() -> ConstraintEngineCase:
    return ConstraintEngineCase(
        requirement="2.4",
        courses=(
            _course(94001, "Mandatory Alpha", RequirementType.OBLIGATORY),
            _course(94002, "Mandatory Beta", RequirementType.OBLIGATORY),
        ),
        selected_programs=(83101,),
        period=_fall_period(1, 4),
        constraints={"min_days_before_last_mandatory": 3},
        expected_schedule_count=2,
    )


def _req_2_5_case() -> ConstraintEngineCase:
    return ConstraintEngineCase(
        requirement="2.5",
        courses=(
            _course(
                95001,
                "Program One Mandatory",
                RequirementType.OBLIGATORY,
                program_id=83101,
            ),
            _course(
                95002,
                "Program Two Mandatory",
                RequirementType.OBLIGATORY,
                program_id=83102,
            ),
        ),
        selected_programs=(83101, 83102),
        period=_fall_period(1, 2),
        constraints={"max_exams_per_day": 1},
        expected_schedule_count=2,
    )


PART3_CASES = (
    # Each case has at least one schedule that should be pruned and at least
    # one boundary schedule that should remain valid.
    pytest.param(_req_2_1_case, id="req_2_1_mandatory_spacing"),
    pytest.param(_req_2_2_case, id="req_2_2_any_spacing"),
    pytest.param(_req_2_3_case, id="req_2_3_elective_conflicts"),
    pytest.param(_req_2_4_case, id="req_2_4_mandatory_span"),
    pytest.param(_req_2_5_case, id="req_2_5_daily_cap"),
)


@pytest.mark.parametrize("case_factory", PART3_CASES)
def test_v1_constraint_files_discard_violating_schedules(
    tmp_path: Path,
    case_factory,
):
    case = case_factory()

    schedule_count = _count_with_v1_files(tmp_path, case)

    assert schedule_count == case.expected_schedule_count


@pytest.mark.parametrize("case_factory", PART3_CASES)
def test_gui_runtime_constraint_inputs_discard_violating_schedules(
    tmp_path: Path,
    case_factory,
):
    case = case_factory()

    schedule_count = _count_with_gui_runtime_files(tmp_path, case)

    assert schedule_count == case.expected_schedule_count


@pytest.mark.parametrize(
    "case",
    json.loads(FIXTURE_PATH.read_text(encoding="utf-8")),
    ids=lambda case: case["case_id"],
)
def test_req_2_2_prep_pairs_are_enforced_by_the_scheduler(
    tmp_path: Path,
    case: dict,
):
    engine_case = ConstraintEngineCase(
        requirement="2.2",
        courses=(
            _course_from_req_2_2_fixture(case["left_course"], case),
            _course_from_req_2_2_fixture(case["right_course"], case),
        ),
        selected_programs=(case["program_id"],),
        period=_period_with_required_exclusion(
            start_date=date.fromisoformat(case["left_date"]),
            last_available_date=date.fromisoformat(case["right_date"]),
        ),
        constraints={"min_days_between_any": case["k"]},
        expected_schedule_count=2 if case["expected_allowed"] else 0,
    )

    schedule_count = _count_with_v1_files(tmp_path, engine_case)

    assert schedule_count == engine_case.expected_schedule_count


def test_official_v1_dataset_smoke_prunes_with_all_five_constraints(
    tmp_path: Path,
):
    # This is deliberately a smoke test. The focused cases above prove each
    # rule; this one proves the official V1 files still travel through the
    # public workflow and that the combined constraints actually prune output.
    constraints_file = tmp_path / "official_constraints.txt"
    constraints_file.write_text(
        format_constraints(
            {
                "min_days_between_mandatory": 3,
                "min_days_between_any": 2,
                "max_elective_conflicts": 1,
                "min_days_before_last_mandatory": 5,
                "max_exams_per_day": 2,
            }
        ),
        encoding="utf-8",
    )

    baseline_count = _count_official_v1_first_period(tmp_path / "baseline")
    constrained_count = _count_official_v1_first_period(
        tmp_path / "constrained",
        constraints_file=constraints_file,
    )

    assert baseline_count > 0
    assert constrained_count < baseline_count


def _course_from_req_2_2_fixture(raw_course: dict, case: dict) -> Course:
    return _course(
        course_id=raw_course["course_id"],
        name=raw_course["name"],
        requirement_type=RequirementType(raw_course["requirement_type"]),
        program_id=case["program_id"],
        year=case["year"],
    )


def _count_with_v1_files(tmp_path: Path, case: ConstraintEngineCase) -> int:
    # Write real V1 text files so this path exercises the same parser contract
    # used by file-based runs.
    source_dir = tmp_path / "v1"
    source_dir.mkdir()

    course_file = source_dir / "courses.txt"
    dates_file = source_dir / "dates.txt"
    user_file = source_dir / "programs.txt"
    constraints_file = source_dir / "constraints.txt"

    course_file.write_text(format_courses(case.courses), encoding="utf-8")
    dates_file.write_text(format_exam_periods([case.period]), encoding="utf-8")
    user_file.write_text(
        ", ".join(str(program_id) for program_id in case.selected_programs),
        encoding="utf-8",
    )
    constraints_file.write_text(format_constraints(case.constraints), encoding="utf-8")

    return _run_count(
        tmp_path,
        course_file=course_file,
        dates_file=dates_file,
        user_file=user_file,
        constraints_file=constraints_file,
    )


def _count_with_gui_runtime_files(tmp_path: Path, case: ConstraintEngineCase) -> int:
    # The GUI stores its current choices as runtime files before launching the
    # same backend workflow. This keeps the test close to the desktop path.
    state = SchedulerInputState(tmp_path / "runtime")
    state.set_selected_programs([str(program_id) for program_id in case.selected_programs])
    state.set_courses(case.courses)
    state.set_exam_periods([case.period])
    state.set_constraints(case.constraints)

    course_file = state.write_courses_file()
    dates_file = state.write_exam_dates_file()
    assert course_file is not None
    assert dates_file is not None

    return _run_count(
        tmp_path,
        course_file=course_file,
        dates_file=dates_file,
        user_file=state.write_selected_programs_file(),
        constraints_file=state.write_constraints_file(),
    )


def _run_count(
    tmp_path: Path,
    course_file: Path,
    dates_file: Path,
    user_file: Path,
    constraints_file: Path,
) -> int:
    output_config = _write_output_config(tmp_path, course_file, dates_file, user_file)

    result = run_complete_count_workflow(
        output_config=output_config,
        course_file=course_file,
        dates_file=dates_file,
        user_file=user_file,
        constraints_file=constraints_file,
    )

    assert len(result.period_schedule_counts) == 1
    assert result.complete_system_count == result.period_schedule_counts[0]
    return result.period_schedule_counts[0]


def _count_official_v1_first_period(
    tmp_path: Path,
    constraints_file: Path | None = None,
) -> int:
    tmp_path.mkdir()
    output_config = _write_output_config(
        tmp_path,
        course_file=DEFAULT_COURSES_PATH,
        dates_file=DEFAULT_EXAM_PERIODS_PATH,
        user_file=DEFAULT_PROGRAMS_PATH,
    )

    kwargs = {}
    if constraints_file is not None:
        kwargs["constraints_file"] = constraints_file

    result = run_complete_count_workflow(
        output_config=output_config,
        period_indexes=[0],
        course_file=DEFAULT_COURSES_PATH,
        dates_file=DEFAULT_EXAM_PERIODS_PATH,
        user_file=DEFAULT_PROGRAMS_PATH,
        **kwargs,
    )

    assert len(result.period_schedule_counts) == 1
    return result.period_schedule_counts[0]


def _write_output_config(
    tmp_path: Path,
    course_file: Path,
    dates_file: Path,
    user_file: Path,
) -> Path:
    output_config = tmp_path / "config.json"
    output_config.write_text(
        json.dumps(
            {
                "source_type": "file",
                "file": {
                    "course_file": str(course_file),
                    "dates_file": str(dates_file),
                    "user_file": str(user_file),
                },
                "output_settings": {
                    "base_directory": str(tmp_path / "output"),
                    "master_filename": "constraint_engine_schedule",
                },
            }
        ),
        encoding="utf-8",
    )
    return output_config
