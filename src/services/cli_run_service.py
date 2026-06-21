"""Services that adapt desktop run requests to the existing v1 CLI."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Sequence

from src.services.scheduler_input_state import SchedulerInputState


VALID_CLI_MODES = {"period", "complete-count", "complete-write", "auto"}


@dataclass(frozen=True)
class CliRunConfig:
    """Application-level description of a scheduler CLI run."""

    project_root: Path
    mode: str = "auto"
    stream_schedules: bool = False
    lazy_schedules: bool = False
    python_executable: str = field(default_factory=lambda: sys.executable)
    output_config: Path | None = None
    source_type: str | None = None
    period_indexes: Sequence[int] = ()
    max_systems: int | None = None
    time_limit_seconds: float | None = None
    course_file: Path | None = None
    dates_file: Path | None = None
    constraints_file: Path | None = None
    user_file: Path | None = None


@dataclass(frozen=True)
class SchedulerRunForm:
    """Raw values collected from the desktop input screen."""

    project_root: Path
    mode: str
    output_config_text: str
    period_indexes_text: str
    max_systems_text: str
    time_limit_text: str
    course_file_text: str
    dates_file_text: str


class SchedulerRunConfigBuilder:
    """Build a validated run config from UI text fields and selected programs."""

    def __init__(self, input_state: SchedulerInputState) -> None:
        self._input_state = input_state

    def build(self, form: SchedulerRunForm) -> CliRunConfig:
        period_indexes = _parse_period_indexes(form.period_indexes_text)
        max_systems = _parse_optional_int(
            form.max_systems_text,
            "Max systems",
            minimum=1,
            maximum=10_000_000,
        )
        time_limit = float(
            _parse_required_int(
                form.time_limit_text,
                "Auto time limit",
                minimum=1,
                maximum=3600,
            )
        )
        selected_programs_file = self._input_state.write_selected_programs_file()
        runtime_courses_file = self._input_state.write_courses_file()
        runtime_dates_file = self._input_state.write_exam_dates_file()
        # Always write this file; disabled constraints are stored as "-".
        runtime_constraints_file = self._input_state.write_constraints_file()

        return CliRunConfig(
            project_root=form.project_root,
            mode=form.mode,
            stream_schedules=form.mode in {"auto", "complete-write"},
            lazy_schedules=form.mode in {"auto", "complete-write"},
            output_config=_path_or_none(form.output_config_text),
            period_indexes=period_indexes,
            max_systems=max_systems,
            time_limit_seconds=time_limit,
            course_file=runtime_courses_file or _path_or_none(form.course_file_text),
            dates_file=runtime_dates_file or _path_or_none(form.dates_file_text),
            # Passing a file keeps GUI runs on the same V1 parsing path.
            constraints_file=runtime_constraints_file,
            user_file=selected_programs_file,
        )


class CliCommandBuilder(Protocol):
    """Build an executable command for a scheduler run."""

    def build_command(self, config: CliRunConfig) -> tuple[str, list[str]]:
        """Return the program path and arguments for the run."""


class V1CliRunAdapter:
    """Adapter for the current v1.0 command-line entry point."""

    def build_command(self, config: CliRunConfig) -> tuple[str, list[str]]:
        return build_cli_arguments(config)


def resolve_cli_output_file(config: CliRunConfig) -> Path:
    """Return the text file path that the current CLI run writes to."""
    output_config = config.output_config or config.project_root / "config.json"

    try:
        config_data = json.loads(output_config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return config.project_root / "outputs" / "master_schedule.txt"

    settings = config_data.get("output_settings", {})
    base_directory = Path(settings.get("base_directory", "outputs"))
    if not base_directory.is_absolute():
        base_directory = config.project_root / base_directory

    filename = str(settings.get("master_filename", "master_schedule")).split(".")[0]
    return base_directory / f"{filename}.txt"


def build_cli_arguments(config: CliRunConfig) -> tuple[str, list[str]]:
    """Build the external command used by the desktop process runner."""
    if config.mode not in VALID_CLI_MODES:
        raise ValueError(f"Unsupported CLI mode: {config.mode}")

    main_script = config.project_root / "main.py"
    output_config = config.output_config or config.project_root / "config.json"
    program = config.python_executable or sys.executable

    args = [
        "-u",
        str(main_script),
        "--mode",
        config.mode,
        "--output-config",
        str(output_config),
    ]

    if config.source_type:
        args.extend(["--source-type", config.source_type])

    for period_index in config.period_indexes:
        args.extend(["--period-index", str(period_index)])

    if config.mode == "complete-write" and config.max_systems is not None:
        args.extend(["--max-systems", str(config.max_systems)])

    if config.mode == "auto" and config.time_limit_seconds is not None:
        args.extend(["--time-limit", str(config.time_limit_seconds)])

    if config.lazy_schedules and config.mode in {"auto", "complete-write"}:
        # Lazy mode keeps big output responsive by generating the next page only on demand.
        args.append("--lazy-schedules")
    elif config.stream_schedules and config.mode in {"auto", "complete-write"}:
        # Streaming mode is still useful for callers that want continuous stdout output.
        args.append("--stream-schedules")

    if config.course_file is not None:
        args.extend(["--course-file", str(config.course_file)])
    if config.dates_file is not None:
        args.extend(["--dates-file", str(config.dates_file)])
    if config.constraints_file is not None:
        # The backend will parse and validate this before scheduling starts.
        args.extend(["--constraints-file", str(config.constraints_file)])
    if config.user_file is not None:
        args.extend(["--user-file", str(config.user_file)])

    return program, args


def _path_or_none(text: str) -> Path | None:
    stripped = text.strip()
    return Path(stripped) if stripped else None


def _parse_period_indexes(text: str) -> tuple[int, ...]:
    stripped = text.strip()
    if not stripped:
        return ()

    indexes: list[int] = []
    for token in stripped.split(","):
        value = token.strip()
        if not value:
            continue
        try:
            index = int(value)
        except ValueError as exc:
            raise ValueError("Period indexes must be comma-separated integers.") from exc
        if index < 0:
            raise ValueError("Period indexes must be zero or greater.")
        indexes.append(index)

    return tuple(indexes)


def _parse_optional_int(
    text: str,
    field_name: str,
    minimum: int,
    maximum: int,
) -> int | None:
    stripped = text.strip()
    if not stripped:
        return None
    return _parse_required_int(stripped, field_name, minimum, maximum)


def _parse_required_int(
    text: str,
    field_name: str,
    minimum: int,
    maximum: int,
) -> int:
    stripped = text.strip()
    try:
        value = int(stripped)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a whole number.") from exc

    if value < minimum or value > maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}.")

    return value
