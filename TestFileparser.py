"""
Unit tests for FileParser.py  -  TDD style.

Run with:
    python -m pytest TestFileParser.py -v

Test categories used in every class:
    Sanity checks  – basic valid input produces correct output / correct types
    Negative checks – invalid input raises the expected exception
    Boundary checks – values exactly at the min/max allowed limit
    Edge cases      – unusual-but-valid input, empty input, whitespace, etc.
"""

import json
import tempfile
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(__file__))

from IParser import IParser
from FileParser import (
    RECORD_SEPARATOR,
    VALID_PROGRAM_NUMBERS,
    FileParser,
    parse_catalog_text,
    parse_date_line,
    parse_period_record,
    parse_periods_text,
    parse_program_line,
    parse_record,
    parse_user_selection,
    split_records,
)

# ===========================================================================
# Fixtures – reusable sample data
# ===========================================================================

VALID_RECORD_ONE_PROGRAM = """\
Physics 1
83102
Prof. O. Some
83101,1,FALL,Obligatory
Exam"""

VALID_RECORD_TWO_PROGRAMS = """\
Data Structures
55212
Dr. Jane Doe
83101,1,FALL,Obligatory
83102,2,SPRI,Elective
Project"""

VALID_CATALOG_TEXT = (
    RECORD_SEPARATOR + "\n"
    + VALID_RECORD_ONE_PROGRAM + "\n"
    + RECORD_SEPARATOR + "\n"
    + VALID_RECORD_TWO_PROGRAMS + "\n"
    + RECORD_SEPARATOR
)

VALID_PERIOD_RECORD_ONE_DATE = """\
FALL,Aleph
29-01-2026, 11-03-2026
31-01-2026 Saturday"""

VALID_PERIOD_RECORD_SIMPLE = """\
SPRI,Bet
15-04-2026"""

VALID_DATES_TEXT = (
    RECORD_SEPARATOR + "\n"
    + VALID_PERIOD_RECORD_ONE_DATE + "\n"
    + RECORD_SEPARATOR + "\n"
    + VALID_PERIOD_RECORD_SIMPLE + "\n"
    + RECORD_SEPARATOR
)

COURSE_KEYS  = {"name", "number", "instructor", "programs", "evaluation"}
PROGRAM_KEYS = {"number", "year", "semester", "requirement"}


# ===========================================================================
# 1. VALID_PROGRAM_NUMBERS
# ===========================================================================

class TestValidProgramNumbers:

    # --- Sanity checks -------------------------------------------------------

    def test_contains_all_required_programs(self):
        """All 10 study programs from section 1.1 must be present"""
        expected = {
            "83101", "83102", "83103", "83104", "83105",
            "83107", "83108", "83109", "83115", "83182",
        }
        assert set(VALID_PROGRAM_NUMBERS) == expected

    def test_no_extra_programs_in_list(self):
        """No programs beyond those defined in the requirements"""
        assert len(set(VALID_PROGRAM_NUMBERS)) == 10


# ===========================================================================
# 2. split_records
# ===========================================================================

class TestSplitRecords:

    # --- Sanity checks -------------------------------------------------------

    def test_single_record_between_separators(self):
        text = f"{RECORD_SEPARATOR}\nPhysics 1\n{RECORD_SEPARATOR}"
        result = split_records(text)
        assert len(result) == 1
        assert result[0] == "Physics 1"

    def test_two_records_yields_two_blocks(self):
        text = f"{RECORD_SEPARATOR}\nA\n{RECORD_SEPARATOR}\nB\n{RECORD_SEPARATOR}"
        result = split_records(text)
        assert len(result) == 2
        assert result[0] == "A"
        assert result[1] == "B"

    def test_three_records(self):
        sep = RECORD_SEPARATOR
        text = f"{sep}\nA\n{sep}\nB\n{sep}\nC\n{sep}"
        assert split_records(text) == ["A", "B", "C"]

    def test_full_catalog_text_yields_two_records(self):
        assert len(split_records(VALID_CATALOG_TEXT)) == 2

    # --- Edge cases ----------------------------------------------------------

    def test_empty_string_returns_empty_list(self):
        assert split_records("") == []

    def test_only_separators_returns_empty_list(self):
        text = f"{RECORD_SEPARATOR}{RECORD_SEPARATOR}{RECORD_SEPARATOR}"
        assert split_records(text) == []

    def test_whitespace_only_between_separators_is_ignored(self):
        text = f"{RECORD_SEPARATOR}\n   \n{RECORD_SEPARATOR}\nActual\n{RECORD_SEPARATOR}"
        result = split_records(text)
        assert len(result) == 1
        assert result[0] == "Actual"

    def test_leading_and_trailing_whitespace_stripped(self):
        text = f"{RECORD_SEPARATOR}\n  Hello  \n{RECORD_SEPARATOR}"
        assert split_records(text)[0] == "Hello"

    def test_no_separator_returns_whole_text_as_one_block(self):
        assert split_records("no separator here") == ["no separator here"]


# ===========================================================================
# 3. parse_program_line
# ===========================================================================

class TestParseProgramLine:

    # --- Sanity checks -------------------------------------------------------

    def test_returns_dict(self):
        assert isinstance(parse_program_line("83101,1,FALL,Obligatory"), dict)

    def test_dict_has_all_keys(self):
        assert parse_program_line("83101,1,FALL,Obligatory").keys() == PROGRAM_KEYS

    def test_valid_obligatory_fall(self):
        prog = parse_program_line("83101,1,FALL,Obligatory")
        assert prog["number"]      == "83101"
        assert prog["year"]        == "1"
        assert prog["semester"]    == "FALL"
        assert prog["requirement"] == "Obligatory"

    def test_valid_elective_spring(self):
        prog = parse_program_line("12345,3,SPRI,Elective")
        assert prog["number"]      == "12345"
        assert prog["year"]        == "3"
        assert prog["semester"]    == "SPRI"
        assert prog["requirement"] == "Elective"

    def test_valid_summer_semester(self):
        assert parse_program_line("99999,4,SUMM,Elective")["semester"] == "SUMM"

    def test_summ_obligatory_combination(self):
        """SUMM + Obligatory — valid combination"""
        prog = parse_program_line("83101,2,SUMM,Obligatory")
        assert prog["semester"]    == "SUMM"
        assert prog["requirement"] == "Obligatory"

    def test_spri_elective_year_three(self):
        """SPRI + Elective + year 3 — additional valid combination"""
        prog = parse_program_line("83104,3,SPRI,Elective")
        assert prog["year"]        == "3"
        assert prog["semester"]    == "SPRI"
        assert prog["requirement"] == "Elective"

    # --- Negative checks -----------------------------------------------------

    def test_invalid_program_number_too_short(self):
        with pytest.raises(ValueError, match="program number"):
            parse_program_line("8310,1,FALL,Obligatory")

    def test_invalid_program_number_too_long(self):
        with pytest.raises(ValueError, match="program number"):
            parse_program_line("831011,1,FALL,Obligatory")

    def test_invalid_program_number_non_digits(self):
        with pytest.raises(ValueError, match="program number"):
            parse_program_line("8310A,1,FALL,Obligatory")

    def test_invalid_year_zero(self):
        with pytest.raises(ValueError, match="year"):
            parse_program_line("83101,0,FALL,Obligatory")

    def test_invalid_year_five(self):
        with pytest.raises(ValueError, match="year"):
            parse_program_line("83101,5,FALL,Obligatory")

    def test_invalid_semester(self):
        with pytest.raises(ValueError, match="semester"):
            parse_program_line("83101,1,WINT,Obligatory")

    def test_invalid_requirement(self):
        with pytest.raises(ValueError, match="requirement"):
            parse_program_line("83101,1,FALL,Mandatory")

    def test_too_few_fields(self):
        with pytest.raises(ValueError, match="4 comma-separated"):
            parse_program_line("83101,1,FALL")

    def test_too_many_fields(self):
        with pytest.raises(ValueError, match="4 comma-separated"):
            parse_program_line("83101,1,FALL,Obligatory,Extra")

    # --- Boundary checks -----------------------------------------------------

    def test_year_boundary_min_is_one(self):
        """Year 1 — minimum valid value"""
        assert parse_program_line("83101,1,FALL,Obligatory")["year"] == "1"

    def test_year_boundary_max_is_four(self):
        """Year 4 — maximum valid value"""
        assert parse_program_line("83101,4,SUMM,Elective")["year"] == "4"

    # --- Edge cases ----------------------------------------------------------

    def test_whitespace_around_fields_is_tolerated(self):
        prog = parse_program_line(" 83101 , 2 , SPRI , Elective ")
        assert prog["number"] == "83101"
        assert prog["year"]   == "2"


# ===========================================================================
# 4. parse_record
# ===========================================================================

class TestParseRecord:

    # --- Sanity checks -------------------------------------------------------

    def test_returns_dict(self):
        assert isinstance(parse_record(VALID_RECORD_ONE_PROGRAM), dict)

    def test_dict_has_all_course_keys(self):
        assert parse_record(VALID_RECORD_ONE_PROGRAM).keys() == COURSE_KEYS

    def test_programs_is_a_list(self):
        assert isinstance(parse_record(VALID_RECORD_ONE_PROGRAM)["programs"], list)

    def test_program_entries_are_dicts(self):
        assert all(isinstance(p, dict) for p in parse_record(VALID_RECORD_ONE_PROGRAM)["programs"])

    def test_program_dicts_have_all_keys(self):
        assert all(p.keys() == PROGRAM_KEYS for p in parse_record(VALID_RECORD_ONE_PROGRAM)["programs"])

    def test_course_name(self):
        assert parse_record(VALID_RECORD_ONE_PROGRAM)["name"] == "Physics 1"

    def test_course_number(self):
        assert parse_record(VALID_RECORD_ONE_PROGRAM)["number"] == "83102"

    def test_instructor_name(self):
        assert parse_record(VALID_RECORD_ONE_PROGRAM)["instructor"] == "Prof. O. Some"

    def test_evaluation_exam(self):
        assert parse_record(VALID_RECORD_ONE_PROGRAM)["evaluation"] == "Exam"

    def test_evaluation_project(self):
        assert parse_record(VALID_RECORD_TWO_PROGRAMS)["evaluation"] == "Project"

    def test_evaluation_attendance(self):
        assert parse_record(VALID_RECORD_ONE_PROGRAM.replace("Exam", "Attendance"))["evaluation"] == "Attendance"

    def test_single_program_count(self):
        assert len(parse_record(VALID_RECORD_ONE_PROGRAM)["programs"]) == 1

    def test_single_program_fields(self):
        prog = parse_record(VALID_RECORD_ONE_PROGRAM)["programs"][0]
        assert prog["number"]      == "83101"
        assert prog["year"]        == "1"
        assert prog["semester"]    == "FALL"
        assert prog["requirement"] == "Obligatory"

    def test_two_programs_count(self):
        assert len(parse_record(VALID_RECORD_TWO_PROGRAMS)["programs"]) == 2

    def test_two_programs_second_fields(self):
        prog = parse_record(VALID_RECORD_TWO_PROGRAMS)["programs"][1]
        assert prog["number"]      == "83102"
        assert prog["year"]        == "2"
        assert prog["semester"]    == "SPRI"
        assert prog["requirement"] == "Elective"

    def test_result_is_json_serialisable(self):
        assert isinstance(json.dumps(parse_record(VALID_RECORD_ONE_PROGRAM)), str)

    # --- Negative checks -----------------------------------------------------

    def test_invalid_course_number_raises(self):
        with pytest.raises(ValueError, match="course number"):
            parse_record(VALID_RECORD_ONE_PROGRAM.replace("83102", "8310X"))

    def test_invalid_evaluation_raises(self):
        with pytest.raises(ValueError, match="evaluation"):
            parse_record(VALID_RECORD_ONE_PROGRAM.replace("Exam", "Oral"))

    def test_too_few_lines_raises(self):
        with pytest.raises(ValueError, match="too few lines"):
            parse_record("Name\n83102\nInstructor\nExam")

    def test_invalid_program_line_propagates_error(self):
        with pytest.raises(ValueError):
            parse_record(VALID_RECORD_ONE_PROGRAM.replace("83101,1,FALL,Obligatory", "BAD_LINE"))

    # --- Boundary checks -----------------------------------------------------

    def test_record_with_four_programs(self):
        """Course with 4 program lines — boundary on number of programs"""
        record = (
            "Advanced Math\n"
            "11111\n"
            "Dr. X\n"
            "83101,1,FALL,Obligatory\n"
            "83102,2,SPRI,Elective\n"
            "83104,3,SUMM,Obligatory\n"
            "83107,4,FALL,Elective\n"
            "Exam"
        )
        result = parse_record(record)
        assert len(result["programs"]) == 4

    # --- Edge cases ----------------------------------------------------------

    def test_blank_lines_within_record_ignored(self):
        record = "\nPhysics 1\n\n83102\n\nProf. O. Some\n83101,1,FALL,Obligatory\n\nExam\n"
        course = parse_record(record)
        assert course["name"]   == "Physics 1"
        assert course["number"] == "83102"

    def test_instructor_with_dots_and_hyphens(self):
        """Instructor name with dots and hyphens — edge case for name parsing"""
        record = VALID_RECORD_ONE_PROGRAM.replace("Prof. O. Some", "Dr. A.B. Cohen-Levi")
        assert parse_record(record)["instructor"] == "Dr. A.B. Cohen-Levi"

    def test_course_name_with_numbers(self):
        """Course name containing digits — edge case"""
        record = VALID_RECORD_ONE_PROGRAM.replace("Physics 1", "Calculus 2B")
        assert parse_record(record)["name"] == "Calculus 2B"


# ===========================================================================
# 5. parse_catalog_text
# ===========================================================================

class TestParseCatalogText:

    # --- Sanity checks -------------------------------------------------------

    def test_returns_list(self):
        assert isinstance(parse_catalog_text(VALID_CATALOG_TEXT), list)

    def test_correct_number_of_courses(self):
        assert len(parse_catalog_text(VALID_CATALOG_TEXT)) == 2

    def test_all_items_are_dicts(self):
        assert all(isinstance(c, dict) for c in parse_catalog_text(VALID_CATALOG_TEXT))

    def test_all_dicts_have_course_keys(self):
        assert all(c.keys() == COURSE_KEYS for c in parse_catalog_text(VALID_CATALOG_TEXT))

    def test_first_course_name(self):
        assert parse_catalog_text(VALID_CATALOG_TEXT)[0]["name"] == "Physics 1"

    def test_second_course_name(self):
        assert parse_catalog_text(VALID_CATALOG_TEXT)[1]["name"] == "Data Structures"

    def test_full_catalog_is_json_serialisable(self):
        assert isinstance(json.dumps(parse_catalog_text(VALID_CATALOG_TEXT)), str)

    # --- Boundary checks -----------------------------------------------------

    def test_single_course_catalog(self):
        text = f"{RECORD_SEPARATOR}\n{VALID_RECORD_ONE_PROGRAM}\n{RECORD_SEPARATOR}"
        result = parse_catalog_text(text)
        assert len(result) == 1
        assert result[0]["number"] == "83102"

    # --- Edge cases ----------------------------------------------------------

    def test_empty_text_returns_empty_list(self):
        assert parse_catalog_text("") == []

    def test_only_separators_returns_empty_list(self):
        assert parse_catalog_text(f"{RECORD_SEPARATOR}{RECORD_SEPARATOR}") == []


# ===========================================================================
# 6. IParser interface
# ===========================================================================

class TestIParserInterface:

    # --- Sanity checks -------------------------------------------------------

    def test_iparser_is_abstract(self):
        from abc import ABC
        assert issubclass(IParser, ABC)

    def test_file_parser_is_subclass_of_iparser(self):
        assert issubclass(FileParser, IParser)

    def test_concrete_subclass_is_instantiable(self):
        class DummyParser(IParser):
            def parse_to_json(self, config: dict) -> str:
                return "[]"
        assert isinstance(DummyParser(), IParser)

    def test_polymorphism_called_via_iparser_reference(self):
        class DummyParser(IParser):
            def parse_to_json(self, config: dict) -> str:
                return f'[{{"source": "{config["source"]}"}}]'
        parser: IParser = DummyParser()
        result = json.loads(parser.parse_to_json({"source": "dummy"}))
        assert result == [{"source": "dummy"}]

    def test_config_dict_is_passed_through(self):
        received = {}
        class SpyParser(IParser):
            def parse_to_json(self, config: dict) -> str:
                received.update(config)
                return "[]"
        SpyParser().parse_to_json({"course_file": "x.txt", "dates_file": "y.txt"})
        assert received["course_file"] == "x.txt"
        assert received["dates_file"]  == "y.txt"

    # --- Negative checks -----------------------------------------------------

    def test_cannot_instantiate_iparser_directly(self):
        with pytest.raises(TypeError):
            IParser()

    def test_subclass_without_parse_to_json_is_abstract(self):
        class Incomplete(IParser):
            pass
        with pytest.raises(TypeError):
            Incomplete()


# ===========================================================================
# 7. parse_date_line
# ===========================================================================

class TestParseDateLine:

    # --- Sanity checks -------------------------------------------------------

    def test_returns_dict(self):
        assert isinstance(parse_date_line("31-01-2026"), dict)

    def test_dict_has_all_keys(self):
        assert parse_date_line("31-01-2026").keys() == {"start_date", "end_date", "comment"}

    def test_single_date_no_comment(self):
        result = parse_date_line("31-01-2026")
        assert result["start_date"] == "31-01-2026"
        assert result["end_date"]   is None
        assert result["comment"]    is None

    def test_single_date_with_comment(self):
        result = parse_date_line("31-01-2026 Saturday")
        assert result["start_date"] == "31-01-2026"
        assert result["end_date"]   is None
        assert result["comment"]    == "Saturday"

    def test_date_range_no_comment(self):
        result = parse_date_line("29-01-2026, 11-03-2026")
        assert result["start_date"] == "29-01-2026"
        assert result["end_date"]   == "11-03-2026"
        assert result["comment"]    is None

    def test_date_range_with_comment(self):
        result = parse_date_line("02-03-2026, 04-03-2026 Purim")
        assert result["start_date"] == "02-03-2026"
        assert result["end_date"]   == "04-03-2026"
        assert result["comment"]    == "Purim"

    # --- Negative checks -----------------------------------------------------

    def test_invalid_date_format_raises(self):
        with pytest.raises(ValueError):
            parse_date_line("2026-01-31")

    def test_no_date_in_line_raises(self):
        with pytest.raises(ValueError, match="No date"):
            parse_date_line("Saturday holiday")

    def test_end_before_start_raises(self):
        with pytest.raises(ValueError, match="before end_date"):
            parse_date_line("11-03-2026, 29-01-2026")

    def test_start_equals_end_raises(self):
        with pytest.raises(ValueError, match="before end_date"):
            parse_date_line("01-01-2026, 01-01-2026")

    def test_invalid_day_raises(self):
        with pytest.raises(ValueError):
            parse_date_line("32-01-2026")

    def test_invalid_month_raises(self):
        with pytest.raises(ValueError):
            parse_date_line("01-13-2026")

    def test_non_leap_year_feb_29_raises(self):
        """February 29 in a non-leap year — invalid date"""
        with pytest.raises(ValueError):
            parse_date_line("29-02-2026")

    # --- Boundary checks -----------------------------------------------------

    def test_last_day_of_month_valid(self):
        """January 31 — boundary on maximum day"""
        result = parse_date_line("31-01-2026")
        assert result["start_date"] == "31-01-2026"

    def test_day_zero_raises(self):
        """Day 0 — lower boundary violation"""
        with pytest.raises(ValueError):
            parse_date_line("00-01-2026")

    def test_month_boundary_december_valid(self):
        """December (month 12) — upper boundary on month"""
        result = parse_date_line("31-12-2026")
        assert result["start_date"] == "31-12-2026"

    def test_leap_year_feb_29_valid(self):
        """February 29 in a leap year — valid date at calendar boundary"""
        result = parse_date_line("29-02-2028")
        assert result["start_date"] == "29-02-2028"
        assert result["end_date"]   is None

    # --- Edge cases ----------------------------------------------------------

    def test_comment_with_multiple_words(self):
        """Comment containing multiple words"""
        result = parse_date_line("01-01-2026 New Year Holiday")
        assert result["start_date"] == "01-01-2026"
        assert result["comment"]    == "New Year Holiday"

    def test_date_range_with_multiword_comment(self):
        """Date range combined with a multi-word comment"""
        result = parse_date_line("02-03-2026, 04-03-2026 Purim Break")
        assert result["start_date"] == "02-03-2026"
        assert result["end_date"]   == "04-03-2026"
        assert result["comment"]    == "Purim Break"


# ===========================================================================
# 8. parse_period_record
# ===========================================================================

class TestParsePeriodRecord:

    # --- Sanity checks -------------------------------------------------------

    def test_returns_dict(self):
        assert isinstance(parse_period_record(VALID_PERIOD_RECORD_ONE_DATE), dict)

    def test_dict_has_all_keys(self):
        assert parse_period_record(VALID_PERIOD_RECORD_ONE_DATE).keys() == {"semester", "moed", "dates"}

    def test_semester_correct(self):
        assert parse_period_record(VALID_PERIOD_RECORD_ONE_DATE)["semester"] == "FALL"

    def test_moed_correct(self):
        assert parse_period_record(VALID_PERIOD_RECORD_ONE_DATE)["moed"] == "Aleph"

    def test_dates_is_list(self):
        assert isinstance(parse_period_record(VALID_PERIOD_RECORD_ONE_DATE)["dates"], list)

    def test_correct_number_of_dates(self):
        assert len(parse_period_record(VALID_PERIOD_RECORD_ONE_DATE)["dates"]) == 2

    def test_first_date_entry(self):
        d = parse_period_record(VALID_PERIOD_RECORD_ONE_DATE)["dates"][0]
        assert d["start_date"] == "29-01-2026"
        assert d["end_date"]   == "11-03-2026"
        assert d["comment"]    is None

    def test_second_date_entry(self):
        d = parse_period_record(VALID_PERIOD_RECORD_ONE_DATE)["dates"][1]
        assert d["start_date"] == "31-01-2026"
        assert d["end_date"]   is None
        assert d["comment"]    == "Saturday"

    def test_valid_moeds(self):
        for moed in ("Aleph", "Bet", "Gimel"):
            assert parse_period_record(f"FALL,{moed}\n01-01-2026")["moed"] == moed

    def test_valid_semesters(self):
        for sem in ("FALL", "SPRI", "SUMM"):
            assert parse_period_record(f"{sem},Aleph\n01-01-2026")["semester"] == sem

    def test_gimel_moed_with_date_range(self):
        """moed=Gimel with a date range — combination not previously tested"""
        result = parse_period_record("SUMM,Gimel\n01-06-2026, 30-06-2026")
        assert result["moed"]                 == "Gimel"
        assert result["dates"][0]["end_date"] == "30-06-2026"

    def test_simple_period_record_is_json_serialisable(self):
        assert isinstance(json.dumps(parse_period_record(VALID_PERIOD_RECORD_SIMPLE)), str)

    # --- Negative checks -----------------------------------------------------

    def test_invalid_semester_raises(self):
        with pytest.raises(ValueError, match="semester"):
            parse_period_record("WINT,Aleph\n01-01-2026")

    def test_invalid_moed_raises(self):
        with pytest.raises(ValueError, match="moed"):
            parse_period_record("FALL,Dalet\n01-01-2026")

    def test_too_few_lines_raises(self):
        with pytest.raises(ValueError, match="too few lines"):
            parse_period_record("FALL,Aleph")

    def test_invalid_header_format_raises(self):
        with pytest.raises(ValueError, match="header"):
            parse_period_record("FALL\n01-01-2026")

    # --- Boundary checks -----------------------------------------------------

    def test_simple_period_record_single_date(self):
        """VALID_PERIOD_RECORD_SIMPLE — period with exactly one date line"""
        result = parse_period_record(VALID_PERIOD_RECORD_SIMPLE)
        assert result["semester"]               == "SPRI"
        assert result["moed"]                   == "Bet"
        assert len(result["dates"])             == 1
        assert result["dates"][0]["start_date"] == "15-04-2026"
        assert result["dates"][0]["end_date"]   is None
        assert result["dates"][0]["comment"]    is None

    def test_period_with_three_date_lines(self):
        """Period with 3 date lines — upper boundary on number of dates"""
        record = "SUMM,Gimel\n01-06-2026\n15-06-2026\n30-06-2026"
        result = parse_period_record(record)
        assert len(result["dates"]) == 3
        assert result["dates"][2]["start_date"] == "30-06-2026"

    # --- Edge cases ----------------------------------------------------------

    def test_header_with_spaces_around_comma(self):
        """Spaces around the comma in the header — whitespace tolerance"""
        result = parse_period_record("FALL , Aleph\n01-01-2026")
        assert result["semester"] == "FALL"
        assert result["moed"]     == "Aleph"


# ===========================================================================
# 9. parse_periods_text
# ===========================================================================

class TestParsePeriodText:

    # --- Sanity checks -------------------------------------------------------

    def test_returns_list(self):
        assert isinstance(parse_periods_text(VALID_DATES_TEXT), list)

    def test_correct_number_of_periods(self):
        assert len(parse_periods_text(VALID_DATES_TEXT)) == 2

    def test_all_items_are_dicts(self):
        assert all(isinstance(p, dict) for p in parse_periods_text(VALID_DATES_TEXT))

    def test_first_period_semester(self):
        assert parse_periods_text(VALID_DATES_TEXT)[0]["semester"] == "FALL"

    def test_second_period_moed(self):
        assert parse_periods_text(VALID_DATES_TEXT)[1]["moed"] == "Bet"

    def test_result_is_json_serialisable(self):
        assert isinstance(json.dumps(parse_periods_text(VALID_DATES_TEXT)), str)

    # --- Edge cases ----------------------------------------------------------

    def test_empty_text_returns_empty_list(self):
        assert parse_periods_text("") == []


# ===========================================================================
# 10. parse_user_selection
# ===========================================================================

class TestParseUserSelection:

    # --- Sanity checks -------------------------------------------------------

    def test_returns_list(self):
        assert isinstance(parse_user_selection("83101"), list)

    def test_single_program(self):
        assert parse_user_selection("83101") == ["83101"]

    def test_two_programs(self):
        assert parse_user_selection("83101, 83102") == ["83101", "83102"]

    def test_five_programs(self):
        result = parse_user_selection("83101, 83102, 83104, 83107, 83108")
        assert len(result) == 5

    def test_all_valid_program_numbers_accepted(self):
        for num in VALID_PROGRAM_NUMBERS:
            assert parse_user_selection(num) == [num]

    def test_order_is_preserved(self):
        result = parse_user_selection("83108, 83101, 83102")
        assert result == ["83108", "83101", "83102"]

    # --- Negative checks -----------------------------------------------------

    def test_more_than_five_raises(self):
        with pytest.raises(ValueError, match="Too many"):
            parse_user_selection("83101, 83102, 83104, 83107, 83108, 83109")

    def test_empty_input_raises(self):
        with pytest.raises(ValueError, match="empty"):
            parse_user_selection("")

    def test_unknown_program_number_raises(self):
        with pytest.raises(ValueError, match="Unknown"):
            parse_user_selection("99999")

    def test_invalid_format_non_digits_raises(self):
        with pytest.raises(ValueError):
            parse_user_selection("ABC")

    def test_four_digit_number_raises(self):
        with pytest.raises(ValueError):
            parse_user_selection("8310")

    def test_six_digit_number_raises(self):
        with pytest.raises(ValueError):
            parse_user_selection("831011")

    # --- Boundary checks -----------------------------------------------------

    def test_exactly_five_is_valid(self):
        result = parse_user_selection("83101, 83102, 83104, 83107, 83108")
        assert len(result) == 5

    # --- Edge cases ----------------------------------------------------------

    def test_whitespace_around_numbers_tolerated(self):
        assert parse_user_selection("  83101  ,  83102  ") == ["83101", "83102"]

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="empty"):
            parse_user_selection("   ")

    def test_duplicate_programs_allowed(self):
        """Duplicates are the caller's concern; parser only validates format"""
        result = parse_user_selection("83101, 83101")
        assert result == ["83101", "83101"]


# ===========================================================================
# 11. FileParser  (three files: courses + dates + user)
# ===========================================================================

class TestFileParser:

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _write_temp(self, content: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def _make_config(
        self,
        course_content: str = VALID_CATALOG_TEXT,
        dates_content:  str = VALID_DATES_TEXT,
        user_content:   str = "83101, 83102",
    ) -> tuple[dict, str, str, str]:
        cp = self._write_temp(course_content)
        dp = self._write_temp(dates_content)
        up = self._write_temp(user_content)
        return {"course_file": cp, "dates_file": dp, "user_file": up}, cp, dp, up

    def _cleanup(self, *paths):
        for p in paths:
            os.unlink(p)

    # --- Sanity checks -------------------------------------------------------

    def test_is_instance_of_iparser(self):
        assert isinstance(FileParser(), IParser)

    def test_returns_string(self):
        config, cp, dp, up = self._make_config()
        try:
            assert isinstance(FileParser().parse_to_json(config), str)
        finally:
            self._cleanup(cp, dp, up)

    def test_top_level_keys_present(self):
        config, cp, dp, up = self._make_config()
        try:
            result = json.loads(FileParser().parse_to_json(config))
            assert set(result.keys()) == {"courses_node", "periods_node", "user_node"}
        finally:
            self._cleanup(cp, dp, up)

    def test_courses_node_is_list(self):
        config, cp, dp, up = self._make_config()
        try:
            assert isinstance(json.loads(FileParser().parse_to_json(config))["courses_node"], list)
        finally:
            self._cleanup(cp, dp, up)

    def test_periods_node_is_list(self):
        config, cp, dp, up = self._make_config()
        try:
            assert isinstance(json.loads(FileParser().parse_to_json(config))["periods_node"], list)
        finally:
            self._cleanup(cp, dp, up)

    def test_user_node_is_list(self):
        config, cp, dp, up = self._make_config()
        try:
            assert isinstance(json.loads(FileParser().parse_to_json(config))["user_node"], list)
        finally:
            self._cleanup(cp, dp, up)

    def test_courses_node_correct_count(self):
        config, cp, dp, up = self._make_config()
        try:
            assert len(json.loads(FileParser().parse_to_json(config))["courses_node"]) == 2
        finally:
            self._cleanup(cp, dp, up)

    def test_courses_node_first_name(self):
        config, cp, dp, up = self._make_config()
        try:
            assert json.loads(FileParser().parse_to_json(config))["courses_node"][0]["name"] == "Physics 1"
        finally:
            self._cleanup(cp, dp, up)

    def test_courses_node_fields_complete(self):
        config, cp, dp, up = self._make_config()
        try:
            course = json.loads(FileParser().parse_to_json(config))["courses_node"][0]
            assert course["number"]     == "83102"
            assert course["instructor"] == "Prof. O. Some"
            assert course["evaluation"] == "Exam"
        finally:
            self._cleanup(cp, dp, up)

    def test_second_course_data_intact(self):
        """Second course in the file is preserved correctly"""
        config, cp, dp, up = self._make_config()
        try:
            courses = json.loads(FileParser().parse_to_json(config))["courses_node"]
            assert courses[1]["name"]          == "Data Structures"
            assert courses[1]["evaluation"]    == "Project"
            assert len(courses[1]["programs"]) == 2
        finally:
            self._cleanup(cp, dp, up)

    def test_periods_node_correct_count(self):
        config, cp, dp, up = self._make_config()
        try:
            assert len(json.loads(FileParser().parse_to_json(config))["periods_node"]) == 2
        finally:
            self._cleanup(cp, dp, up)

    def test_periods_node_first_semester_and_moed(self):
        config, cp, dp, up = self._make_config()
        try:
            period = json.loads(FileParser().parse_to_json(config))["periods_node"][0]
            assert period["semester"] == "FALL"
            assert period["moed"]     == "Aleph"
        finally:
            self._cleanup(cp, dp, up)

    def test_periods_node_dates_present(self):
        config, cp, dp, up = self._make_config()
        try:
            period = json.loads(FileParser().parse_to_json(config))["periods_node"][0]
            assert len(period["dates"]) == 2
            assert period["dates"][0]["start_date"] == "29-01-2026"
        finally:
            self._cleanup(cp, dp, up)

    def test_second_period_data_intact(self):
        """Second period in the file is preserved correctly"""
        config, cp, dp, up = self._make_config()
        try:
            periods = json.loads(FileParser().parse_to_json(config))["periods_node"]
            assert periods[1]["semester"]               == "SPRI"
            assert periods[1]["moed"]                   == "Bet"
            assert len(periods[1]["dates"])             == 1
            assert periods[1]["dates"][0]["start_date"] == "15-04-2026"
        finally:
            self._cleanup(cp, dp, up)

    def test_user_node_correct_values(self):
        config, cp, dp, up = self._make_config(user_content="83101, 83102")
        try:
            assert json.loads(FileParser().parse_to_json(config))["user_node"] == ["83101", "83102"]
        finally:
            self._cleanup(cp, dp, up)

    def test_user_node_order_preserved(self):
        config, cp, dp, up = self._make_config(user_content="83108, 83101, 83102")
        try:
            assert json.loads(FileParser().parse_to_json(config))["user_node"] == ["83108", "83101", "83102"]
        finally:
            self._cleanup(cp, dp, up)

    def test_output_is_valid_parseable_json(self):
        """Output is valid, parseable JSON — not just serialisable"""
        config, cp, dp, up = self._make_config()
        try:
            result = json.loads(FileParser().parse_to_json(config))
            assert isinstance(result, dict)
        finally:
            self._cleanup(cp, dp, up)

    # --- Negative checks -----------------------------------------------------

    def test_missing_course_file_key_raises(self):
        with pytest.raises(KeyError, match="course_file"):
            FileParser().parse_to_json({"dates_file": "d.txt", "user_file": "u.txt"})

    def test_missing_dates_file_key_raises(self):
        with pytest.raises(KeyError, match="dates_file"):
            FileParser().parse_to_json({"course_file": "c.txt", "user_file": "u.txt"})

    def test_missing_user_file_key_raises(self):
        with pytest.raises(KeyError, match="user_file"):
            FileParser().parse_to_json({"course_file": "c.txt", "dates_file": "d.txt"})

    def test_empty_config_raises(self):
        with pytest.raises(KeyError):
            FileParser().parse_to_json({})

    def test_course_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            FileParser().parse_to_json({
                "course_file": "/nonexistent/courses.txt",
                "dates_file":  "/nonexistent/dates.txt",
                "user_file":   "/nonexistent/user.txt",
            })

    def test_invalid_course_file_raises_value_error(self):
        """Course file with a broken record — must raise ValueError"""
        bad_courses = (
            f"{RECORD_SEPARATOR}\n"
            "Course Name\n"
            "BADNUM\n"
            "Instructor\n"
            "Exam\n"
            f"{RECORD_SEPARATOR}"
        )
        config, cp, dp, up = self._make_config(course_content=bad_courses)
        try:
            with pytest.raises(ValueError):
                FileParser().parse_to_json(config)
        finally:
            self._cleanup(cp, dp, up)

    def test_invalid_dates_file_raises_value_error(self):
        """Dates file with a broken header — must raise ValueError"""
        bad_dates = (
            f"{RECORD_SEPARATOR}\n"
            "BAD_HEADER\n"
            "01-01-2026\n"
            f"{RECORD_SEPARATOR}"
        )
        config, cp, dp, up = self._make_config(dates_content=bad_dates)
        try:
            with pytest.raises(ValueError):
                FileParser().parse_to_json(config)
        finally:
            self._cleanup(cp, dp, up)

    def test_invalid_user_selection_raises_value_error(self):
        config, cp, dp, up = self._make_config(user_content="99999")
        try:
            with pytest.raises(ValueError, match="Unknown"):
                FileParser().parse_to_json(config)
        finally:
            self._cleanup(cp, dp, up)

    def test_too_many_programs_raises_value_error(self):
        config, cp, dp, up = self._make_config(
            user_content="83101, 83102, 83104, 83107, 83108, 83109"
        )
        try:
            with pytest.raises(ValueError, match="Too many"):
                FileParser().parse_to_json(config)
        finally:
            self._cleanup(cp, dp, up)

    def test_empty_user_file_raises_value_error(self):
        config, cp, dp, up = self._make_config(user_content="")
        try:
            with pytest.raises(ValueError, match="empty"):
                FileParser().parse_to_json(config)
        finally:
            self._cleanup(cp, dp, up)

    # --- Boundary checks -----------------------------------------------------

    def test_user_node_single_program(self):
        config, cp, dp, up = self._make_config(user_content="83108")
        try:
            assert json.loads(FileParser().parse_to_json(config))["user_node"] == ["83108"]
        finally:
            self._cleanup(cp, dp, up)

    def test_user_node_five_programs(self):
        config, cp, dp, up = self._make_config(
            user_content="83101, 83102, 83104, 83107, 83108"
        )
        try:
            assert len(json.loads(FileParser().parse_to_json(config))["user_node"]) == 5
        finally:
            self._cleanup(cp, dp, up)

    # --- Edge cases ----------------------------------------------------------

    def test_user_node_whitespace_tolerated(self):
        config, cp, dp, up = self._make_config(user_content="  83101  ,  83102  ")
        try:
            assert json.loads(FileParser().parse_to_json(config))["user_node"] == ["83101", "83102"]
        finally:
            self._cleanup(cp, dp, up)

    def test_empty_course_and_dates_files_return_empty_nodes(self):
        config, cp, dp, up = self._make_config(course_content="", dates_content="")
        try:
            result = json.loads(FileParser().parse_to_json(config))
            assert result["courses_node"] == []
            assert result["periods_node"] == []
        finally:
            self._cleanup(cp, dp, up)




