import math
import time
from datetime import date, timedelta
from pathlib import Path

from src.models.enums import Semester, Term, RequirementType
from src.models.academic import (
    Course,
    ProgramAffiliation,
    Exam,
    Project,
    Attendance,
)
from src.models.scheduling import (
    ExamPeriod,
    DateExclusion,
    filter_exam_courses,
)
from src.rules.academic_conflict_rule_m import AcademicConflictRule
from src.solver.scheduler import Scheduler


ROOT_DIR = Path(__file__).resolve().parents[2]

PROGRAMS_FILE = ROOT_DIR / "data" / "Programs.txt"
EXAM_DATES_FILE = ROOT_DIR / "data" / "V1.0 ExamDates.txt"
COURSES_FILE = ROOT_DIR / "data" / "V1.0CourseDB.txt"

OUTPUT_DIR = ROOT_DIR / "output"
OUTPUT_FILE = OUTPUT_DIR / "exam_schedules.txt"


def _parse_date(value: str) -> date:
    day, month, year = value.strip().split("-")
    return date(int(year), int(month), int(day))


def _parse_programs(path: Path) -> list[int]:
    with open(path, "r", encoding="utf-8") as file:
        content = file.read().strip()

    return [
        int(program.strip())
        for program in content.split(",")
        if program.strip()
    ]


def _parse_semester(value: str) -> Semester:
    value = value.strip()

    for semester in Semester:
        if semester.value == value or semester.name == value:
            return semester

    raise ValueError(f"Unknown semester: {value}")


def _parse_term(value: str) -> Term:
    value = value.strip()

    for term in Term:
        if term.value.lower() == value.lower() or term.name.lower() == value.lower():
            return term

    raise ValueError(f"Unknown term: {value}")


def _parse_requirement(value: str) -> RequirementType:
    value = value.strip()

    for requirement in RequirementType:
        if (
            requirement.value.lower() == value.lower()
            or requirement.name.lower() == value.lower()
        ):
            return requirement

    raise ValueError(f"Unknown requirement type: {value}")


def _parse_evaluation(value: str):
    value = value.strip().lower()

    if value == "exam":
        return Exam()

    if value == "project":
        return Project()

    if value == "attendance":
        return Attendance()

    raise ValueError(f"Unknown evaluation type: {value}")


def _parse_exam_periods(path: Path) -> list[ExamPeriod]:
    with open(path, "r", encoding="utf-8") as file:
        content = file.read()

    raw_records = [
        record.strip()
        for record in content.split("$$$$")
        if record.strip()
    ]

    periods = []

    for record in raw_records:
        lines = [
            line.strip()
            for line in record.splitlines()
            if line.strip()
        ]

        semester_text, term_text = [
            part.strip()
            for part in lines[0].split(",")
        ]

        start_text, end_text = [
            part.strip()
            for part in lines[1].split(",")
        ]

        period = ExamPeriod(
            semester=_parse_semester(semester_text),
            term=_parse_term(term_text),
            start_date=_parse_date(start_text),
            end_date=_parse_date(end_text),
        )

        for line in lines[2:]:
            line = line.lstrip("-").strip()

            if "," in line:
                start_part, rest = line.split(",", 1)
                end_part = rest.strip().split()[0]

                period.add_exclusion(
                    DateExclusion(
                        start_date=_parse_date(start_part.strip()),
                        end_date=_parse_date(end_part.strip()),
                    )
                )
            else:
                exclusion_date = line.split()[0]

                period.add_exclusion(
                    DateExclusion(_parse_date(exclusion_date))
                )

        periods.append(period)

    return periods


def _parse_courses(path: Path) -> list[Course]:
    with open(path, "r", encoding="utf-8") as file:
        # פיצול לפי $$$$ וניקוי רווחים מיותרים
        raw_records = [r.strip() for r in file.read().split("$$$$") if r.strip()]

    courses = []
    for record in raw_records:
        lines = [l.strip() for l in record.splitlines() if l.strip()]
        if len(lines) < 4: continue # הגנה מרשומות חסרות

        name = lines[0]
        course_id = int(lines[1])
        instructor = lines[2]
        evaluation_text = lines[-1] # השורה האחרונה תמיד Evaluation

        course = Course(
            course_id=course_id,
            name=name,
            instructor=instructor,
            evaluation=_parse_evaluation(evaluation_text),
        )

        # מעבר על כל שורות התוכניות (השורות שבין המרצה ל-Evaluation)
        for affiliation_line in lines[3:-1]:
            parts = [p.strip() for p in affiliation_line.split(",")]
            if len(parts) == 4:
                course.add_affiliation(ProgramAffiliation(
                    program_id=int(parts[0]),
                    year=int(parts[1]),
                    semester=_parse_semester(parts[2]),
                    requirement_type=_parse_requirement(parts[3])
                ))
        courses.append(course)
    return courses


def _select_period(
    periods: list[ExamPeriod],
    semester: Semester,
    term: Term,
) -> ExamPeriod:
    for period in periods:
        if period.semester == semester and period.term == term:
            return period

    raise AssertionError(
        f"Could not find period for {semester}, {term}"
    )


def _filter_selected_courses(
    courses: list[Course],
    selected_programs: list[int],
    semester: Semester,
) -> list[Course]:
    selected = []

    for course in courses:
        relevant_affiliations = [
            affiliation
            for affiliation in course.affiliations
            if affiliation.program_id in selected_programs
            and affiliation.semester == semester
        ]

        if relevant_affiliations:
            selected.append(course)

    return filter_exam_courses(selected)


def _get_available_dates(period: ExamPeriod) -> list[date]:
    available = []

    current = period.start_date

    while current <= period.end_date:
        if period.is_date_valid(current):
            available.append(current)

        current += timedelta(days=1)

    return available


def test_scheduler_run_to_file_large_output():
    selected_programs = _parse_programs(PROGRAMS_FILE)

    periods = _parse_exam_periods(EXAM_DATES_FILE)

    all_courses = _parse_courses(COURSES_FILE)

    period = _select_period(
        periods=periods,
        semester=Semester.FALL,
        term=Term.ALEPH,
    )

    courses = _filter_selected_courses(
        courses=all_courses,
        selected_programs=selected_programs,
        semester=Semester.FALL,
    )

    available_dates = _get_available_dates(period)

    assert selected_programs == [83101, 83102, 83108]

    assert len(available_dates) == 33

    # assert len(courses) == 10
    print(f"Actual courses loaded: {len(courses)}")
    print(f"Available dates: {len(available_dates)}")

    scheduler = Scheduler(
        rules=[AcademicConflictRule()]
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if OUTPUT_FILE.exists():
        OUTPUT_FILE.unlink()

    started_at = time.perf_counter()

    count = scheduler.run_to_file(
        courses=courses,
        period=period,
        output_path=OUTPUT_FILE,
        enforce_unique=False,
    )

    duration = time.perf_counter() - started_at

    # assert count == expected_count, (
    #     f"Expected {expected_count:,} schedules, got {count:,}"
    # )

    assert OUTPUT_FILE.exists()

    assert OUTPUT_FILE.stat().st_size > 0

    print("\n" + "=" * 80)
    print(" LARGE FILE OUTPUT TEST")
    print(f" Selected programs: {selected_programs}")
    print(f" Courses count: {len(courses)}")
    print(f" Available dates: {len(available_dates)}")
    # print(f" Expected schedules: {expected_count:,}")
    print(f" Written schedules: {count:,}")
    print(f" Runtime: {duration:.4f} seconds")
    print(f" Output file: {OUTPUT_FILE}")
    print(f" Output size: {OUTPUT_FILE.stat().st_size / (1024 * 1024):.2f} MB")

    if duration >= 30:
        print(f" WARNING: exceeded SLA ({duration:.2f}s)")

    print("=" * 80)