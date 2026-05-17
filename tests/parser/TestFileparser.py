import pytest
from src.parser.file_parser import (
    RECORD_SEPARATOR, VALID_PROGRAM_NUMBERS, parse_catalog_text, parse_date_line, parse_period_record,
    parse_program_line, parse_record, parse_user_selection, split_records
)

# --- Sample Data ---
VALID_RECORD = "Physics 1\n83102\nProf. O. Some\n83101,1,FALL,Obligatory\nExam"
VALID_PERIOD = "FALL,Aleph\n29-01-2026, 11-03-2026\n31-01-2026 Saturday"

# ===========================================================================
# 1. Basic Components
# ===========================================================================

def test_split_records():
    text = f"{RECORD_SEPARATOR}\nRec 1\n{RECORD_SEPARATOR}\nRec 2\n{RECORD_SEPARATOR}"
    assert split_records(text) == ["Rec 1", "Rec 2"]
    assert split_records("") == []

def test_parse_program_line():
    # Sanity
    prog = parse_program_line("83101,1,FALL,Obligatory")
    assert prog == {"number": "83101", "year": "1", "semester": "FALL", "requirement": "Obligatory"}
    # Negative
    with pytest.raises(ValueError):
        parse_program_line("83101,5,WINT,Wrong") # Invalid year/semester

# ===========================================================================
# 2. Record Parsing (Courses & Dates)
# ===========================================================================

def test_parse_record():
    result = parse_record(VALID_RECORD)
    assert result["name"] == "Physics 1"
    assert len(result["programs"]) == 1
    assert result["evaluation"] == "Exam"

    with pytest.raises(ValueError):
        parse_record("Too\nFew\nLines")

def test_parse_date_line():
    # Range with comment
    res = parse_date_line("02-03-2026, 04-03-2026 Purim")
    assert res["start_date"] == "02-03-2026"
    assert res["comment"] == "Purim"
    # Negative
    with pytest.raises(ValueError):
        parse_date_line("32-01-2026") # Invalid day

def test_parse_period_record():
    res = parse_period_record(VALID_PERIOD)
    assert res["semester"] == "FALL"
    assert res["moed"] == "Aleph"
    assert len(res["exclusions"]) == 1
    assert res["exclusions"][0]["comment"] == "Saturday"

# ===========================================================================
# 3. User Selection & Global State
# ===========================================================================

def test_valid_program_numbers():
    assert "83101" in VALID_PROGRAM_NUMBERS
    assert len(VALID_PROGRAM_NUMBERS) == 10

def test_parse_user_selection():
    assert parse_user_selection("83101, 83102") == ["83101", "83102"]
    # Boundary: 5 is OK, 6 is not
    parse_user_selection("83101, 83102, 83103, 83104, 83105")
    with pytest.raises(ValueError):
        parse_user_selection("83101, 83102, 83103, 83104, 83105, 83107")
    with pytest.raises(ValueError):
        parse_user_selection("83101, 83101")

# ===========================================================================
# 4. High-Level Integration (FileParser)
# ===========================================================================

class TestFileParserLogic:
    def test_parse_catalog_text_integration(self):
        text = f"{RECORD_SEPARATOR}\n{VALID_RECORD}\n{RECORD_SEPARATOR}"
        catalog = parse_catalog_text(text)
        assert len(catalog) == 1
        assert catalog[0]["number"] == "83102"

    def test_parse_catalog_text_rejects_duplicate_course_numbers(self):
        duplicate_record = "Digital Systems\n83102\nProf. Weiss\n83102,1,FALL,Obligatory\nExam"
        text = f"{RECORD_SEPARATOR}\n{VALID_RECORD}\n{RECORD_SEPARATOR}\n{duplicate_record}"

        with pytest.raises(ValueError):
            parse_catalog_text(text)
