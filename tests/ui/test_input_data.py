from src.ui.input_data import InputDataStore, PeriodPreview


COURSES_TEXT = """$$$$
Physics 1
83102
Prof. O. Some
83101,1,FALL,Obligatory
83102,1,FALL,Obligatory
Exam
$$$$
Software Project
83533
Dr. Terry Bell
83101,3,SPRI,Elective
83108,2,SPRI,Obligatory
Project
"""

DATES_TEXT = """$$$$
FALL,Aleph
29-01-2026, 11-03-2026
- 31-01-2026 Shabat
$$$$
SPRI,Aleph
03-07-2026, 07-08-2026
- 09-07-2026 Holiday
"""


SUPPLEMENTAL_COURSES_TEXT = """$$$$
Physics 1 Changed
83102
Prof. Replacement
83115,4,FALL,Elective
Exam
$$$$
Discrete Math
84000
Dr. Emmy Noether
83115,1,SUMM,Obligatory
Exam
"""


SUPPLEMENTAL_DATES_TEXT = """$$$$
FALL,Aleph
01-02-2026, 12-03-2026
- 07-02-2026 Shabat
$$$$
SUMM,Bet
15-09-2026, 25-09-2026
- 19-09-2026 Shabat
"""


def test_input_data_store_builds_program_list_from_course_file(tmp_path):
    course_file = tmp_path / "courses.txt"
    dates_file = tmp_path / "dates.txt"
    course_file.write_text(COURSES_TEXT, encoding="utf-8")
    dates_file.write_text(DATES_TEXT, encoding="utf-8")

    store = InputDataStore()
    store.replace(course_file, dates_file)

    programs = store.programs()

    assert [program.program_id for program in programs] == ["83101", "83102", "83108"]
    assert programs[0].name == "Program 83101"
    assert [course.course_id for course in programs[0].courses] == ["83102", "83533"]
    assert programs[0].courses[0].requirement == "Obligatory"
    assert programs[0].courses[1].evaluation == "Project"


def test_input_data_store_builds_period_preview(tmp_path):
    course_file = tmp_path / "courses.txt"
    dates_file = tmp_path / "dates.txt"
    course_file.write_text(COURSES_TEXT, encoding="utf-8")
    dates_file.write_text(DATES_TEXT, encoding="utf-8")

    store = InputDataStore()
    store.replace(course_file, dates_file)

    periods = store.periods()

    assert [(period.semester, period.term) for period in periods] == [
        ("FALL", "Aleph"),
        ("SPRI", "Aleph"),
    ]
    assert periods[0].start_date == "29-01-2026"
    assert periods[0].exclusions == ("31-01-2026 Shabat",)


def test_input_data_store_writes_runtime_files_for_selected_programs(tmp_path):
    course_file = tmp_path / "courses.txt"
    dates_file = tmp_path / "dates.txt"
    runtime_dir = tmp_path / "runtime"
    course_file.write_text(COURSES_TEXT, encoding="utf-8")
    dates_file.write_text(DATES_TEXT, encoding="utf-8")

    store = InputDataStore()
    store.replace(course_file, dates_file)

    runtime_courses, runtime_dates, runtime_programs = store.write_runtime_files(
        runtime_dir,
        ["83101", "83108"],
        [
            PeriodPreview(
                semester="FALL",
                term="Aleph",
                start_date="29-01-2026",
                end_date="12-03-2026",
                exclusions=("31-01-2026 Shabat",),
            )
        ],
    )

    assert "Physics 1" in runtime_courses.read_text(encoding="utf-8")
    assert "29-01-2026, 12-03-2026" in runtime_dates.read_text(encoding="utf-8")
    assert runtime_programs.read_text(encoding="utf-8") == "83101, 83108"


def test_input_data_store_add_keeps_existing_records_and_adds_new_ones(tmp_path):
    course_file = tmp_path / "courses.txt"
    dates_file = tmp_path / "dates.txt"
    supplemental_course_file = tmp_path / "more_courses.txt"
    supplemental_dates_file = tmp_path / "more_dates.txt"
    course_file.write_text(COURSES_TEXT, encoding="utf-8")
    dates_file.write_text(DATES_TEXT, encoding="utf-8")
    supplemental_course_file.write_text(SUPPLEMENTAL_COURSES_TEXT, encoding="utf-8")
    supplemental_dates_file.write_text(SUPPLEMENTAL_DATES_TEXT, encoding="utf-8")

    store = InputDataStore()
    store.replace(course_file, dates_file)
    store.add(supplemental_course_file, supplemental_dates_file)

    course_names = [
        course.name
        for program in store.programs()
        for course in program.courses
    ]
    periods = store.periods()

    assert "Physics 1" in course_names
    assert "Physics 1 Changed" not in course_names
    assert "Discrete Math" in course_names
    assert [(period.semester, period.term) for period in periods] == [
        ("FALL", "Aleph"),
        ("SPRI", "Aleph"),
        ("SUMM", "Bet"),
    ]
    assert periods[0].start_date == "29-01-2026"
