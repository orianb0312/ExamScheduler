import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from src.parser.IParser import IParser
from src.parser.file_parser import FileParser
from src.rules.ai_copilot_rule import AICopilotRule
from src.services.ai_constraint_export_service import export_ai_constraint
from src.workflow import (
    load_domain_context,
    run_complete_auto_workflow,
    run_complete_auto_stream_workflow,
    run_complete_count_workflow,
    run_complete_lazy_stream_workflow,
    run_complete_write_stream_workflow,
    run_complete_write_workflow,
    run_v1_workflow,
)
from src.analytics.exporters import SUPPORTED_ANALYTICS_FORMATS
from src.services.analytics_export_service import (
    DEFAULT_ANALYTICS_SCHEDULE_LIMIT,
    ScheduleAnalyticsExportService,
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
    parser.add_argument(
        "--stream-schedules",
        action="store_true",
        help="Stream complete schedule systems to stdout for the desktop UI.",
    )
    parser.add_argument(
        "--lazy-schedules",
        action="store_true",
        help="Generate the first schedule page, then wait for NEXT commands on stdin.",
    )
    parser.add_argument(
        "--export-analytics",
        action="store_true",
        help=(
            "After a file-writing schedule run, export deterministic analytics "
            "beside the generated schedule file."
        ),
    )
    parser.add_argument(
        "--analytics-format",
        "--analytics-formats",
        dest="analytics_formats",
        action="append",
        default=[],
        help=(
            "Analytics export format. Repeat the flag or pass comma-separated "
            f"values. Supported: {', '.join(SUPPORTED_ANALYTICS_FORMATS)}."
        ),
    )
    parser.add_argument(
        "--analytics-output-dir",
        type=Path,
        default=None,
        help="Directory for analytics exports. Defaults to the schedule output directory.",
    )
    parser.add_argument(
        "--analytics-base-filename",
        type=str,
        default=None,
        help="Base filename for analytics exports, without an extension.",
    )
    parser.add_argument(
        "--analytics-max-schedules",
        type=int,
        default=DEFAULT_ANALYTICS_SCHEDULE_LIMIT,
        help="Maximum schedules to include in a post-run analytics export.",
    )

    # Optional manual file overrides from the CLI - passed as kwargs to the workflow
    parser.add_argument("--course-file", type=Path, default=None)
    parser.add_argument("--dates-file", type=Path, default=None)
    # Optional V1 constraints file, using the same $$$$ chunk format as the GUI writes.
    parser.add_argument("--constraints-file", type=Path, default=None)
    parser.add_argument(
        "--ai-rules-file",
        type=Path,
        default=None,
        help="Absolute path to validated active AI scheduling rules.",
    )
    ai_constraint_source = parser.add_mutually_exclusive_group()
    ai_constraint_source.add_argument(
        "--ai-constraint-json",
        default=None,
        help="Validated JSON object produced by the local AI constraint parser.",
    )
    ai_constraint_source.add_argument(
        "--ai-constraint-json-file",
        type=Path,
        default=None,
        help="File containing one JSON object produced by the local AI parser.",
    )
    parser.add_argument(
        "--export-ai-constraint-file",
        type=Path,
        default=None,
        help="Export the parsed AI constraint JSON as a validated AI rules file.",
    )
    parser.add_argument(
        "--sorting-file",
        "--sort-file",
        dest="sorting_file",
        type=Path,
        default=None,
        help="Optional V1 file describing the multi-criteria sorting priority.",
    )
    parser.add_argument("--user-file", type=Path, default=None)

    return parser.parse_args()


def run_cli() -> int:
    """Run the CLI entry point and convert failures into readable messages."""
    try:
        return main()
    except SystemExit:
        # Let argparse keep its standard help and validation behavior.
        raise
    except KeyboardInterrupt:
        print("Error: Scheduling was cancelled.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {_format_cli_error(exc)}", file=sys.stderr)
        return 1


def _format_cli_error(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        missing_path = exc.filename or str(exc)
        return f"Required file was not found: {missing_path}"

    if isinstance(exc, json.JSONDecodeError):
        return (
            "Invalid JSON configuration: "
            f"{exc.msg} at line {exc.lineno}, column {exc.colno}."
        )

    if isinstance(exc, KeyError):
        return f"Missing required input: {exc}"

    if isinstance(exc, OSError):
        return f"File system error: {exc}"

    message = str(exc).strip()
    if message:
        return message

    return exc.__class__.__name__


def main() -> int:
    args = parse_args()

    if args.export_ai_constraint_file is not None:
        raw_ai_constraint = args.ai_constraint_json
        if args.ai_constraint_json_file is not None:
            raw_ai_constraint = args.ai_constraint_json_file.read_text(
                encoding="utf-8"
            )
        if raw_ai_constraint is None:
            raise ValueError(
                "--ai-constraint-json or --ai-constraint-json-file is required "
                "when exporting an AI constraint."
            )
        output_path = export_ai_constraint(
            raw_ai_constraint,
            args.export_ai_constraint_file,
            AICopilotRule.validate_rule_record,
        )
        print(f"AI constraint file: {output_path}")
        return 0

    # Create a dynamic CLI overrides dictionary to forward into the workflows.
    # Pack the explicit file paths so the workflow can prioritize them over the config file values.
    cli_overrides = {
        "course_file": args.course_file,
        "dates_file": args.dates_file,
        # Keep this with the other file overrides so config and CLI behave alike.
        "constraints_file": args.constraints_file,
        "ai_rules_file": args.ai_rules_file,
        "sorting_file": args.sorting_file,
        "user_file": args.user_file,
    }

    # Load the config temporarily just to determine which Parser to instantiate in main.
    # The workflow itself will handle full configuration parsing and data loading later.
    with open(args.output_config, encoding="utf-8") as fh:
        config_data = json.load(fh)

    source_type = args.source_type or config_data.get("source_type", "file")
    parser = get_parser(source_type)

    _validate_analytics_request(args)

    # Route execution to the appropriate workflow based on the chosen mode
    if args.mode == "period":
        result = run_v1_workflow(
            output_config=args.output_config,
            period_indexes=args.period_index,
            parser=parser,
            **cli_overrides,
        )
        _print_period_result(result)
        _export_analytics_if_requested(args, result.output_path, parser, cli_overrides)
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
        if args.lazy_schedules:
            _reject_streaming_analytics(args)
            run_complete_lazy_stream_workflow(
                output_config=args.output_config,
                period_indexes=args.period_index,
                max_systems=args.max_systems,
                input_stream=sys.stdin,
                output_stream=sys.stdout,
                progress_stream=sys.stderr,
                parser=parser,
                **cli_overrides,
            )
            return 0

        if args.stream_schedules:
            _reject_streaming_analytics(args)
            run_complete_write_stream_workflow(
                output_config=args.output_config,
                period_indexes=args.period_index,
                max_systems=args.max_systems,
                output_stream=sys.stdout,
                progress_stream=sys.stderr,
                parser=parser,
                **cli_overrides,
            )
            return 0

        result = run_complete_write_workflow(
            output_config=args.output_config,
            period_indexes=args.period_index,
            max_systems=args.max_systems,
            parser=parser,
            **cli_overrides,
        )
        _print_complete_result(result)
        if result.output_path is not None:
            _export_analytics_if_requested(
                args,
                result.output_path,
                parser,
                cli_overrides,
            )
        return 0

    # Fallback to auto mode
    if args.lazy_schedules:
        _reject_streaming_analytics(args)
        run_complete_lazy_stream_workflow(
            output_config=args.output_config,
            period_indexes=args.period_index,
            time_limit_seconds=args.time_limit,
            input_stream=sys.stdin,
            output_stream=sys.stdout,
            progress_stream=sys.stderr,
            parser=parser,
            **cli_overrides,
        )
        return 0

    if args.stream_schedules:
        _reject_streaming_analytics(args)
        run_complete_auto_stream_workflow(
            output_config=args.output_config,
            period_indexes=args.period_index,
            time_limit_seconds=args.time_limit,
            output_stream=sys.stdout,
            progress_stream=sys.stderr,
            parser=parser,
            **cli_overrides,
        )
        return 0

    result = run_complete_auto_workflow(
        output_config=args.output_config,
        period_indexes=args.period_index,
        time_limit_seconds=args.time_limit,
        parser=parser,
        **cli_overrides,
    )
    _print_complete_result(result)
    if result.output_path is not None:
        _export_analytics_if_requested(args, result.output_path, parser, cli_overrides)
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


def _export_analytics_if_requested(
    args: argparse.Namespace,
    schedule_output_path: Path,
    parser: IParser,
    cli_overrides: Dict[str, Any],
) -> None:
    if not _analytics_export_requested(args):
        return

    formats = _parse_analytics_formats(args.analytics_formats)
    # Reload the same input files so post-run analytics use the same courses and priorities.
    context = load_domain_context(
        args.output_config,
        parser=parser,
        **cli_overrides,
    )
    export_service = ScheduleAnalyticsExportService()
    reports, reached_limit = export_service.reports_from_output_file(
        schedule_output_path,
        courses=context.courses,
        selected_program_ids=context.selected_programs,
        active_priorities=context.sort_priority,
        max_schedules=args.analytics_max_schedules,
    )

    output_dir = args.analytics_output_dir or schedule_output_path.parent
    base_filename = (
        args.analytics_base_filename
        or f"{schedule_output_path.stem}_analytics"
    )
    written_paths = export_service.export_reports(
        reports,
        formats,
        output_dir,
        base_filename,
    )

    for path in written_paths:
        print(f"Analytics file: {path}")
    if reached_limit:
        print(
            "Analytics export limited to the first "
            f"{args.analytics_max_schedules:,} schedules."
        )


def _analytics_export_requested(args: argparse.Namespace) -> bool:
    return bool(args.export_analytics or args.analytics_formats)


def _validate_analytics_request(args: argparse.Namespace) -> None:
    if not _analytics_export_requested(args):
        return

    # Fail before scheduling work starts if the requested export can never be written.
    _parse_analytics_formats(args.analytics_formats)

    if args.mode == "complete-count":
        raise ValueError("Analytics export requires a schedule output file.")

    if args.stream_schedules or args.lazy_schedules:
        _reject_streaming_analytics(args)


def _parse_analytics_formats(values: list[str]) -> tuple[str, ...]:
    tokens: list[str] = []
    for value in values:
        tokens.extend(part.strip() for part in str(value).split(",") if part.strip())

    if not tokens:
        return SUPPORTED_ANALYTICS_FORMATS

    clean: list[str] = []
    for token in tokens:
        normalized = token.strip().casefold().lstrip(".")
        if normalized == "text":
            normalized = "txt"
        if normalized not in SUPPORTED_ANALYTICS_FORMATS:
            valid = ", ".join(SUPPORTED_ANALYTICS_FORMATS)
            raise ValueError(
                f"Unsupported analytics format '{token}'. Valid: {valid}."
            )
        if normalized not in clean:
            clean.append(normalized)
    return tuple(clean)


def _reject_streaming_analytics(args: argparse.Namespace) -> None:
    if _analytics_export_requested(args):
        raise ValueError(
            "Analytics export is available for file-writing runs only. "
            "Run without --stream-schedules or --lazy-schedules."
        )


if __name__ == "__main__":
    raise SystemExit(run_cli())
