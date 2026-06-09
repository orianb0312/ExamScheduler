import pytest
from datetime import date
from pathlib import Path

from src.models.enums import Semester, Term
from src.models.scheduling import ExamPeriod
from src.services.scheduler_input_state import SchedulerInputState
from src.services.cli_run_service import SchedulerRunConfigBuilder, SchedulerRunForm, build_cli_arguments


def test_cli_config_builder_rejects_empty_program_selection(tmp_path):
    """
    Edge Case Verification:
    Ensures that attempting to compile an external execution configuration profile
    fails gracefully with a ValueError when the user has not selected any study programs.
    """
    # Set up an isolated, temporary scratch directory path for dynamic input dumps
    runtime_dir = tmp_path / "runtime_inputs"
    input_state = SchedulerInputState(runtime_dir=runtime_dir)
    builder = SchedulerRunConfigBuilder(input_state)

    # Build a mock UI submission form containing an empty program selection vector
    form = SchedulerRunForm(
        project_root=tmp_path,
        mode="auto",
        output_config_text="",
        period_indexes_text="0",
        max_systems_text="",
        time_limit_text="30",
        course_file_text="",
        dates_file_text=""
    )

    # Enforce validation boundary condition: A clear error must block headless solver initialization
    with pytest.raises(ValueError, match="Select at least one study program"):
        builder.build(form)


def test_input_state_to_cli_arguments_generation_pipeline(tmp_path):
    """
    Full Pipeline Integration Test:
    Validates the complete lifecycle flow of mapping interactive UI adjustments
    (such as custom exam periods date boundaries and explicit day calendar exclusions)
    into transient text database disk writes, and successfully building the OS process arguments.
    """
    # Instantiate localized pipeline components pointing to the isolated virtual disk path
    runtime_dir = tmp_path / "runtime_inputs"
    input_state = SchedulerInputState(runtime_dir=runtime_dir)
    builder = SchedulerRunConfigBuilder(input_state)

    # Phase 1: Simulate active UI configuration choices by targeting specific curriculum codes
    input_state.set_selected_programs(["83101", "83102"])

    # Populate initial baseline exam calendar constraints matching production data structures
    mock_period = ExamPeriod(
        semester=Semester.FALL,
        term=Term.ALEPH,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 10)
    )
    input_state.set_exam_periods([mock_period])

    # Phase 2: Simulate interactive user layout manipulation via manual calendar panel clicks
    # Blacklist a specific calendar date block to prevent exam placements (simulate user exclusion click)
    input_state.exclude_day(period_index=0, day=date(2026, 1, 3))
    # Move the entire period date coordinate ranges outward (simulate user shifting date editors bounds)
    input_state.update_period_dates(period_index=0, start_date=date(2026, 1, 2), end_date=date(2026, 1, 12))

    # Phase 3: Trigger configuration builder to serialize runtime state files into the scratch workspace
    form = SchedulerRunForm(
        project_root=tmp_path,
        mode="complete-write",
        output_config_text=str(tmp_path / "config.json"),
        period_indexes_text="0",
        max_systems_text="500",
        time_limit_text="45",
        course_file_text="",
        dates_file_text=""
    )

    config = builder.build(form)

    # Verify that dynamic data synchronization blocks were dumped onto the local storage filesystem
    assert (runtime_dir / "ui_selected_programs.txt").is_file(), "Selected programs configuration must be saved to disk"
    assert (runtime_dir / "ui_exam_dates.txt").is_file(), "Modified exam dates layout grid must be saved to disk"

    # Phase 4: Construct the concrete unbuffered terminal argument array passed downstream to QProcess handles
    python_bin, args = build_cli_arguments(config)

    # Validate that execution switches, processing limits, and active file flags map securely
    assert "--mode" in args
    assert "complete-write" in args
    assert "--max-systems" in args
    assert "500" in args
    assert "--lazy-schedules" in args
    assert "--dates-file" in args
    assert str(
        runtime_dir / "ui_exam_dates.txt") in args, "The generated argument vector must point to the runtime date configuration file"