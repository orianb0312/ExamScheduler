import time
from datetime import date
from pathlib import Path
import pytest

from src.services.file_loading_service import FileLoadingService, DataLoadMode
from src.services.internal_data_store import InternalDataStore

# Well-formed lightweight mock databases matching production parser rules
COURSES_BASE = """$$$$
Calculus 1
10001
Dr. Ada Lovelace
83101,1,FALL,Obligatory
Exam
"""

# FIXED: Added the mandatory evaluation line 'Exam' to the Calculus 1 block
COURSES_UPDATE = """$$$$
Calculus 1
10001
Dr. Ada Lovelace
83102,1,FALL,Elective
Exam
$$$$
Physics 1
10002
Dr. Richard Feynman
83101,1,FALL,Obligatory
Exam
"""

EXAM_DATES_BASE = """$$$$
FALL,Aleph
01-01-2026, 10-01-2026
03-01-2026 Saturday
"""


def test_file_loading_and_cache_store_integration_pipeline(tmp_path):
    """
    Integration Test: Verifies continuous cross-layer operations between
    FileLoadingService and InternalDataStore utilizing real filesystem interaction.
    """
    # Initialize real files inside the isolated pytest tmp_path directory
    courses_file = tmp_path / "courses.txt"
    dates_file = tmp_path / "dates.txt"
    cache_file = tmp_path / "processed_input.json"

    courses_file.write_text(COURSES_BASE, encoding="utf-8")
    dates_file.write_text(EXAM_DATES_BASE, encoding="utf-8")

    # Wire up the services together using the local custom storage path
    store = InternalDataStore(storage_file=cache_file)
    service = FileLoadingService(internal_store=store)

    # -------------------------------------------------------------------------
    # Phase 1: Verify REPLACE mode populates memory and writes a valid cache file
    # -------------------------------------------------------------------------
    result = service.load_selected_files(courses_file, dates_file, DataLoadMode.REPLACE)

    assert result.added_course_count == 1
    assert service.loaded_data.course_count == 1
    assert cache_file.is_file(), "The system must dump compiled JSON onto the local storage disk"
    assert service.is_cache_stale(courses_file, dates_file) is False

    # -------------------------------------------------------------------------
    # Phase 2: Verify UPDATE mode merges data in memory without losing snapshot context
    # -------------------------------------------------------------------------
    # Modify the original file contents to add secondary update structures
    courses_file.write_text(COURSES_UPDATE, encoding="utf-8")

    # Executing an update should append new programs and combine courses with identical IDs
    update_result = service.load_selected_files(courses_file, dates_file, DataLoadMode.UPDATE)

    assert update_result.added_course_count == 1  # Physics 1 was added
    assert update_result.duplicate_course_count == 1  # Calculus 1 was merged

    # Check integrated cross-referencing values
    loaded_data = service.loaded_data
    assert loaded_data.course_count == 2

    # Calculus 1 (ID 10001) should now aggregate affiliations across multiple programs
    calculus_course = next(c for c in loaded_data.courses if c.course_id == 10001)
    assert len(calculus_course.affiliations) == 2

    # -------------------------------------------------------------------------
    # Phase 3: Verify cryptographic fingerprint tracking detects file modifications
    # -------------------------------------------------------------------------
    # Append content to force a SHA256 checksum mutation on the date configuration file
    dates_file.write_text(EXAM_DATES_BASE + "\n15-01-2026 Thursday\n", encoding="utf-8")

    # The caching service layers must recognize that the file footprint changed
    assert service.is_cache_stale(courses_file, dates_file) is True