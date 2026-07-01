"""File exporters for deterministic schedule analytics reports."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, is_dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Protocol, Sequence

from src.analytics.models import ScheduleAnalyticsReport


SUPPORTED_ANALYTICS_FORMATS = ("json", "txt", "csv", "pdf")


class AnalyticsExporter(Protocol):
    """Strategy contract for analytics file writers."""

    extension: str

    def write(
        self,
        reports: Sequence[ScheduleAnalyticsReport],
        destination: Path,
    ) -> Path:
        """Write reports to destination and return the final path."""


class AnalyticsExportService:
    """Dispatch analytics reports to one or more local file formats."""

    def __init__(self) -> None:
        self._exporters: dict[str, AnalyticsExporter] = {
            "json": JsonAnalyticsExporter(),
            "txt": TextAnalyticsExporter(),
            "csv": CsvAnalyticsExporter(),
            "pdf": PdfAnalyticsExporter(),
        }

    def export(
        self,
        reports: Sequence[ScheduleAnalyticsReport],
        formats: Iterable[str],
        output_dir: str | Path,
        base_filename: str = "schedule_analytics",
    ) -> list[Path]:
        clean_reports = tuple(reports)
        if not clean_reports:
            raise ValueError("No schedule analytics reports were produced.")

        clean_formats = _normalize_formats(formats)
        # Resolve the folder and sanitize the name before any writer touches disk.
        output_path = Path(output_dir).resolve()
        output_path.mkdir(parents=True, exist_ok=True)
        filename = _safe_filename(base_filename)

        written_paths: list[Path] = []
        for format_name in clean_formats:
            exporter = self._exporters[format_name]
            destination = output_path / f"{filename}{exporter.extension}"
            written_paths.append(exporter.write(clean_reports, destination))
        return written_paths


class JsonAnalyticsExporter:
    """Write analytics as a machine-readable JSON document."""

    extension = ".json"

    def write(
        self,
        reports: Sequence[ScheduleAnalyticsReport],
        destination: Path,
    ) -> Path:
        payload = {
            "report_count": len(reports),
            "calculation_mode": "deterministic_rules",
            "reports": [_to_jsonable(report) for report in reports],
        }
        destination.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return destination


class TextAnalyticsExporter:
    """Write analytics as a readable diagnostic text file."""

    extension = ".txt"

    def write(
        self,
        reports: Sequence[ScheduleAnalyticsReport],
        destination: Path,
    ) -> Path:
        destination.write_text(self.format(reports), encoding="utf-8")
        return destination

    def format(self, reports: Sequence[ScheduleAnalyticsReport]) -> str:
        lines = [
            "DETERMINISTIC SCHEDULE ANALYTICS",
            "=" * 65,
            "",
        ]
        for report in reports:
            lines.extend(_format_text_report(report))
            lines.append("")
            lines.append("*" * 65)
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


class CsvAnalyticsExporter:
    """Write analytics sections into one CSV diagnostic log."""

    extension = ".csv"

    def write(
        self,
        reports: Sequence[ScheduleAnalyticsReport],
        destination: Path,
    ) -> Path:
        with destination.open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "section",
                    "schedule_number",
                    "schedule_label",
                    "field_1",
                    "field_2",
                    "field_3",
                    "field_4",
                    "field_5",
                    "field_6",
                    "field_7",
                    "field_8",
                ]
            )
            for report in reports:
                _write_csv_report(writer, report)
        return destination


class PdfAnalyticsExporter:
    """Write analytics as a multi-page ReportLab PDF."""

    extension = ".pdf"

    def write(
        self,
        reports: Sequence[ScheduleAnalyticsReport],
        destination: Path,
    ) -> Path:
        # Keep ReportLab isolated so JSON/TXT/CSV exports do not depend on it.
        from src.analytics.pdf_report import ReportLabAnalyticsPdfBuilder

        return ReportLabAnalyticsPdfBuilder().write(reports, destination)


def _format_text_report(report: ScheduleAnalyticsReport) -> list[str]:
    schedule_name = _schedule_name(report)
    lines = [
        schedule_name,
        "-" * len(schedule_name),
        f"Calculation mode: {report.calculation_mode}",
        f"Exam count: {report.exam_count}",
        "Active priorities: "
        + (", ".join(report.active_priorities) if report.active_priorities else "none"),
        "",
        "Scheduled exams:",
    ]
    for exam in sorted(
        report.scheduled_exams,
        key=lambda item: (item.exam_date, item.course_name.casefold()),
    ):
        lines.append(
            "  "
            f"{exam.exam_date.isoformat()} | {exam.course_name} | "
            f"{_optional(exam.course_id)} | {exam.instructor} | "
            f"{_period_text(exam)} | {_cohort_text(exam)}"
        )
    if not report.scheduled_exams:
        lines.append("  No scheduled exam rows were available.")

    lines.extend([
        "",
        "Cross-sectional insights:",
    ])
    lines.extend(f"  {line}" for line in report.cross_sectional_insights)
    if not report.cross_sectional_insights:
        lines.append("  No insight rows were produced.")

    lines.extend([
        "",
        "Metric values:",
    ])
    if report.metric_values:
        for metric in report.metric_values:
            lines.append(
                f"  {metric.priority_position}. {metric.key} "
                f"({metric.document_ref}): {_format_number(metric.value)}"
            )
    else:
        lines.append("  No active sorting priorities were selected.")

    lines.extend(["", "Daily density:"])
    for row in report.daily_density:
        lines.append(
            "  "
            f"{row.exam_date.isoformat()} | exams={row.exam_count} | "
            f"density={row.density_share:.3f} | "
            f"cohort-pairs={row.cohort_collision_pairs}"
        )

    lines.extend(["", "Cohort matrix:"])
    for row in report.cohort_matrix:
        lines.append(
            "  "
            f"program={row.program_id}, year={row.year} | "
            f"exams={row.exam_count} | mandatory={row.mandatory_count} | "
            f"elective={row.elective_count} | min-gap={_optional(row.min_gap_days)} | "
            f"mandatory-min-gap={_optional(row.mandatory_min_gap_days)}"
        )

    lines.extend(["", "Bottlenecks:"])
    if report.bottlenecks:
        for row in report.bottlenecks:
            lines.append(
                "  "
                f"[{row.priority_key}] {row.category}: {row.label} | "
                f"value={_format_number(row.metric_value)} | "
                f"pressure={row.pressure_score:.3f} | {row.detail}"
            )
    else:
        lines.append("  No bottleneck rows were triggered by active priorities.")

    lines.extend(["", "Diagnostics:"])
    lines.extend(f"  {line}" for line in report.diagnostics)

    lines.extend(["", "Functional justification:"])
    lines.extend(f"  {line}" for line in report.functional_justification)
    return lines


def _write_csv_report(writer: csv.writer, report: ScheduleAnalyticsReport) -> None:
    # A single section column keeps one CSV useful for both spreadsheets and logs.
    schedule_number = report.schedule_number or ""
    schedule_label = report.schedule_label
    writer.writerow(
        [
            "summary",
            schedule_number,
            schedule_label,
            "calculation_mode",
            report.calculation_mode,
            "exam_count",
            report.exam_count,
            "active_priorities",
            ";".join(report.active_priorities),
            "",
            "",
        ]
    )

    for exam in report.scheduled_exams:
        writer.writerow(
            [
                "scheduled_exam",
                schedule_number,
                schedule_label,
                exam.exam_date.isoformat(),
                exam.course_name,
                _optional(exam.course_id),
                exam.instructor,
                _period_text(exam),
                _cohort_text(exam),
                "",
                "",
            ]
        )

    for line in report.cross_sectional_insights:
        writer.writerow(
            [
                "cross_sectional_insight",
                schedule_number,
                schedule_label,
                line,
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ]
        )

    for metric in report.metric_values:
        writer.writerow(
            [
                "metric",
                schedule_number,
                schedule_label,
                metric.priority_position,
                metric.key,
                metric.title,
                metric.document_ref,
                _format_number(metric.value),
                "",
                "",
                "",
            ]
        )

    for line in report.functional_justification:
        writer.writerow(
            [
                "functional_justification",
                schedule_number,
                schedule_label,
                line,
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ]
        )

    for row in report.daily_density:
        writer.writerow(
            [
                "daily_density",
                schedule_number,
                schedule_label,
                row.exam_date.isoformat(),
                row.exam_count,
                f"{row.density_share:.6f}",
                row.cohort_collision_pairs,
                "",
                "",
                "",
                "",
            ]
        )

    for row in report.cohort_matrix:
        writer.writerow(
            [
                "cohort_matrix",
                schedule_number,
                schedule_label,
                row.program_id,
                row.year,
                row.exam_count,
                row.mandatory_count,
                row.elective_count,
                _optional(row.min_gap_days),
                _optional(row.mandatory_min_gap_days),
                _optional_float(row.average_gap_days),
            ]
        )

    for row in report.bottlenecks:
        writer.writerow(
            [
                "bottleneck",
                schedule_number,
                schedule_label,
                row.priority_position,
                row.priority_key,
                row.category,
                row.label,
                _format_number(row.metric_value),
                f"{row.pressure_score:.6f}",
                row.detail,
                "",
            ]
        )

    for line in report.diagnostics:
        writer.writerow(
            [
                "diagnostic",
                schedule_number,
                schedule_label,
                line,
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ]
        )


def _to_jsonable(value):
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, date):
        return value.isoformat()
    return value


def _normalize_formats(formats: Iterable[str]) -> tuple[str, ...]:
    clean_formats: list[str] = []
    for value in formats:
        clean = str(value).strip().casefold().lstrip(".")
        if clean == "text":
            clean = "txt"
        if clean not in SUPPORTED_ANALYTICS_FORMATS:
            valid = ", ".join(SUPPORTED_ANALYTICS_FORMATS)
            raise ValueError(f"Unsupported analytics format '{value}'. Valid: {valid}.")
        if clean not in clean_formats:
            clean_formats.append(clean)

    if not clean_formats:
        raise ValueError("At least one analytics export format is required.")
    return tuple(clean_formats)


def _safe_filename(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)).strip("._")
    return clean or "schedule_analytics"


def _schedule_name(report: ScheduleAnalyticsReport) -> str:
    number = f" #{report.schedule_number}" if report.schedule_number is not None else ""
    return f"{report.schedule_label}{number}"


def _cohort_text(exam) -> str:
    return "; ".join(
        f"{cohort.program_id}/Y{cohort.year}/{cohort.requirement_type}"
        for cohort in exam.cohorts
    )


def _period_text(exam) -> str:
    values = [value for value in (exam.semester_label, exam.term_label) if value]
    return " / ".join(values)


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _optional(value: object) -> str:
    return "" if value is None else str(value)


def _optional_float(value: float | None) -> str:
    return "" if value is None else _format_number(float(value))
