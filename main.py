import argparse
import json
from pathlib import Path
from typing import Any, Dict

from src.parser.IParser import IParser
from src.parser.file_parser import FileParser
from src.workflow import (
    run_complete_auto_workflow,
    run_complete_count_workflow,
    run_complete_write_workflow,
    run_v1_workflow,
)

ROOT_DIR = Path(__file__).resolve().parent


def get_parser(source_type: str) -> IParser:
    """Return the right IParser implementation for the given source type."""
    if source_type == "file":
        return FileParser()
    raise ValueError(f"Unknown source_type: '{source_type}'")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate V1.0 exam schedules.")
    parser.add_argument(
        "--mode",
        choices=("period", "complete-count", "complete-write", "auto"),
        default="period",
        help="Execution mode for the workflow.",
    )
    parser.add_argument(
        "--output-config",
        type=Path,
        default=ROOT_DIR / "config.json",
        help="Path to the JSON config containing source and output settings.",
    )
    parser.add_argument(
        "--source-type",
        type=str,
        default=None,
        help="Override the source_type specified in the config.json (e.g., 'file').",
    )
    parser.add_argument(
        "--period-index",
        type=int,
        action="append",
        help="Zero-based period index to run. Repeat this flag to run several periods.",
    )
    parser.add_argument(
        "--max-systems",
        type=int,
        default=None,
        help="Maximum complete systems to write in complete-write mode.",
    )
    parser.add_argument(
        "--time-limit",
        type=float,
        default=30.0,
        help="Time limit in seconds for auto mode.",
    )

    # Optional manual file overrides from the CLI - passed as kwargs to the workflow
    parser.add_argument("--course-file", type=Path, default=None)
    parser.add_argument("--dates-file", type=Path, default=None)
    parser.add_argument("--user-file", type=Path, default=None)

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Create a dynamic CLI overrides dictionary to forward into the workflows.
    # Pack the explicit file paths so the workflow can prioritize them over the config file values.
    cli_overrides = {
        "course_file": args.course_file,
        "dates_file": args.dates_file,
        "user_file": args.user_file,
    }

    # Load the config temporarily just to determine which Parser to instantiate in main.
    # The workflow itself will handle full configuration parsing and data loading later.
    with open(args.output_config, encoding="utf-8") as fh:
        config_data = json.load(fh)

    source_type = args.source_type or config_data.get("source_type", "file")
    parser = get_parser(source_type)

    # Route execution to the appropriate workflow based on the chosen mode
    if args.mode == "period":
        result = run_v1_workflow(
            output_config=args.output_config,
            period_indexes=args.period_index,
            parser=parser,
            **cli_overrides,
        )
        _print_period_result(result)
        return 0

    if args.mode == "complete-count":
        result = run_complete_count_workflow(
            output_config=args.output_config,
            period_indexes=args.period_index,
            parser=parser,
            **cli_overrides,
        )
        _print_complete_result(result)
        return 0

    if args.mode == "complete-write":
        result = run_complete_write_workflow(
            output_config=args.output_config,
            period_indexes=args.period_index,
            max_systems=args.max_systems,
            parser=parser,
            **cli_overrides,
        )
        _print_complete_result(result)
        return 0

    # Fallback to auto mode
    result = run_complete_auto_workflow(
        output_config=args.output_config,
        period_indexes=args.period_index,
        time_limit_seconds=args.time_limit,
        parser=parser,
        **cli_overrides,
    )
    _print_complete_result(result)
    return 0


def _print_period_result(result) -> None:
    print(f"Output file: {result.output_path}")
    for period in result.periods:
        print(
            f"{period.semester} / {period.term}: "
            f"{period.course_count} courses, {period.schedule_count:,} schedules"
        )
    print(f"Total schedules across periods: {result.total_schedules:,}")


def _print_complete_result(result) -> None:
    if result.output_path is not None:
        print(f"Output file: {result.output_path}")

    for index, (course_count, schedule_count) in enumerate(
            zip(result.period_course_counts, result.period_schedule_counts)
    ):
        print(
            f"Period #{index}: {course_count} courses, "
            f"{schedule_count:,} period schedules"
        )

    print(f"Complete systems: {result.complete_system_count:,}")
    print(f"Written systems: {result.written_system_count:,}")
    print(f"Elapsed seconds: {result.elapsed_seconds:.10f}")
    print(f"Truncated: {result.truncated}")
    if result.auto_limit_seconds is not None:
        print(f"Auto time limit: {result.auto_limit_seconds:.2f} seconds")


if __name__ == "__main__":
    raise SystemExit(main())