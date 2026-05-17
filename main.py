import argparse
from pathlib import Path

from src.workflow import (
    run_complete_auto_workflow,
    run_complete_count_workflow,
    run_complete_write_workflow,
    run_v1_workflow,
)


ROOT_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate V1.0 exam schedules from input files.")
    parser.add_argument(
        "--mode",
        choices=("period", "complete-count", "complete-write", "auto"),
        default="period",
        help=(
            "period writes schedules per exam period; complete-count reports the Cartesian "
            "complete-system count; complete-write writes complete systems; auto writes as "
            "many complete systems as fit in the time limit."
        ),
    )
    parser.add_argument(
        "--course-file",
        type=Path,
        default=ROOT_DIR / "data" / "V1.0CourseDB.txt",
        help="Path to the course catalog file.",
    )
    parser.add_argument(
        "--dates-file",
        type=Path,
        default=ROOT_DIR / "data" / "V1.0 ExamDates.txt",
        help="Path to the exam-period file.",
    )
    parser.add_argument(
        "--user-file",
        type=Path,
        default=ROOT_DIR / "data" / "Programs.txt",
        help="Path to the selected-programs file.",
    )
    parser.add_argument(
        "--output-config",
        type=Path,
        default=ROOT_DIR / "config.json",
        help="Path to the output-manager JSON config.",
    )
    parser.add_argument(
        "--period-index",
        type=int,
        action="append",
        help="Zero-based period index to run. Repeat this flag to run several periods. Defaults to all periods.",
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.mode == "period":
        result = run_v1_workflow(
            course_file=args.course_file,
            dates_file=args.dates_file,
            user_file=args.user_file,
            output_config=args.output_config,
            period_indexes=args.period_index,
        )
        _print_period_result(result)
        return 0

    if args.mode == "complete-count":
        result = run_complete_count_workflow(
            course_file=args.course_file,
            dates_file=args.dates_file,
            user_file=args.user_file,
            period_indexes=args.period_index,
        )
        _print_complete_result(result)
        return 0

    if args.mode == "complete-write":
        result = run_complete_write_workflow(
            course_file=args.course_file,
            dates_file=args.dates_file,
            user_file=args.user_file,
            output_config=args.output_config,
            period_indexes=args.period_index,
            max_systems=args.max_systems,
        )
        _print_complete_result(result)
        return 0

    result = run_complete_auto_workflow(
        course_file=args.course_file,
        dates_file=args.dates_file,
        user_file=args.user_file,
        output_config=args.output_config,
        period_indexes=args.period_index,
        time_limit_seconds=args.time_limit,
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
