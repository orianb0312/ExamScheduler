"""ReportLab PDF builder for deterministic analytics reports."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Sequence

from src.analytics.models import AnalyticsExam, ScheduleAnalyticsReport


@dataclass(frozen=True)
class PdfTableSpec:
    """One report table with fixed column widths."""

    title: str
    headers: Sequence[object]
    rows: Sequence[Sequence[object]]
    col_widths: Sequence[float]


class ReportLabAnalyticsPdfBuilder:
    """Create multi-page analytics PDFs with safe table pagination."""

    def write(
        self,
        reports: Sequence[ScheduleAnalyticsReport],
        destination: Path,
    ) -> Path:
        # Import locally so non-PDF analytics exports stay lightweight.
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import mm
            from reportlab.platypus import (
                CondPageBreak,
                KeepTogether,
                LongTable,
                PageBreak,
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                TableStyle,
            )
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "PDF analytics export requires ReportLab. "
                "Install the project dependencies from requirements.txt."
            ) from exc

        styles = getSampleStyleSheet()
        title_style = styles["Title"]
        heading_style = styles["Heading2"]
        body_style = ParagraphStyle(
            "AnalyticsBody",
            parent=styles["BodyText"],
            fontSize=9,
            leading=12,
            wordWrap="CJK",
        )
        cell_style = ParagraphStyle(
            "AnalyticsTableCell",
            parent=styles["BodyText"],
            fontSize=7,
            leading=9,
            wordWrap="CJK",
            splitLongWords=True,
        )
        header_style = ParagraphStyle(
            "AnalyticsTableHeader",
            parent=cell_style,
            fontName="Helvetica-Bold",
        )

        doc = SimpleDocTemplate(
            str(destination),
            pagesize=landscape(A4),
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            topMargin=14 * mm,
            bottomMargin=14 * mm,
            title="Deterministic Schedule Analytics",
        )
        story = [
            Paragraph("Deterministic Schedule Analytics", title_style),
            Spacer(1, 5 * mm),
        ]

        context = _ReportLabContext(
            Paragraph=Paragraph,
            Spacer=Spacer,
            CondPageBreak=CondPageBreak,
            KeepTogether=KeepTogether,
            LongTable=LongTable,
            TableStyle=TableStyle,
            colors=colors,
            heading_style=heading_style,
            body_style=body_style,
            cell_style=cell_style,
            header_style=header_style,
            mm=mm,
        )

        for index, report in enumerate(reports):
            if index:
                story.append(PageBreak())
            story.extend(self._report_story(report, context))

        doc.build(
            story,
            onFirstPage=self._draw_footer,
            onLaterPages=self._draw_footer,
        )
        return destination

    def _report_story(
        self,
        report: ScheduleAnalyticsReport,
        context: "_ReportLabContext",
    ) -> list[object]:
        # Build each report in the same order operators read the diagnostics.
        Paragraph = context.Paragraph
        Spacer = context.Spacer
        mm = context.mm
        story: list[object] = [
            Paragraph(_wrap(_schedule_name(report)), context.heading_style),
            Spacer(1, 2 * mm),
            Paragraph(
                _wrap(
                    f"Calculation mode: {report.calculation_mode}. "
                    f"Exam count: {report.exam_count}. "
                    "Active priorities: "
                    + (
                        ", ".join(report.active_priorities)
                        if report.active_priorities
                        else "none"
                    )
                ),
                context.body_style,
            ),
            Spacer(1, 3 * mm),
        ]

        for line in report.cross_sectional_insights:
            story.append(Paragraph(_wrap(line), context.body_style))
        story.append(Spacer(1, 3 * mm))

        for spec in self._table_specs(report, mm):
            story.extend(self._table_section(spec, context))

        story.append(
            # Keep the explanation heading with its first lines when a page is tight.
            context.KeepTogether(
                [
                    Paragraph("Functional Justification", context.heading_style),
                    *[
                        Paragraph(_wrap(line), context.body_style)
                        for line in report.functional_justification
                    ],
                ]
            )
        )
        story.append(Spacer(1, 2 * mm))

        return story

    def _table_specs(
        self,
        report: ScheduleAnalyticsReport,
        mm,
    ) -> tuple[PdfTableSpec, ...]:
        return (
            PdfTableSpec(
                title="Scheduled Exams",
                headers=(
                    "Date",
                    "Course",
                    "ID",
                    "Instructor",
                    "Period",
                    "Cohorts",
                ),
                rows=_exam_rows(report.scheduled_exams),
                col_widths=(28 * mm, 78 * mm, 18 * mm, 42 * mm, 34 * mm, 66 * mm),
            ),
            PdfTableSpec(
                title="Metric Values",
                headers=("#", "Metric", "Part", "Value"),
                rows=[
                    (
                        metric.priority_position,
                        f"{metric.title} ({metric.key})",
                        metric.document_ref,
                        _format_number(metric.value),
                    )
                    for metric in report.metric_values
                ]
                or [("", "No active sorting priorities selected", "", "")],
                col_widths=(12 * mm, 88 * mm, 24 * mm, 28 * mm),
            ),
            PdfTableSpec(
                title="Daily Density",
                headers=("Date", "Exams", "Density", "Cohort Pairs"),
                rows=[
                    (
                        row.exam_date.isoformat(),
                        row.exam_count,
                        f"{row.density_share:.3f}",
                        row.cohort_collision_pairs,
                    )
                    for row in report.daily_density
                ]
                or [("", "", "", "")],
                col_widths=(34 * mm, 22 * mm, 24 * mm, 34 * mm),
            ),
            PdfTableSpec(
                title="Cohort Matrix",
                headers=(
                    "Program",
                    "Year",
                    "Exams",
                    "Mandatory",
                    "Elective",
                    "Min Gap",
                    "Mandatory Min",
                    "Average Gap",
                ),
                rows=[
                    (
                        row.program_id,
                        row.year,
                        row.exam_count,
                        row.mandatory_count,
                        row.elective_count,
                        _optional(row.min_gap_days),
                        _optional(row.mandatory_min_gap_days),
                        _optional_float(row.average_gap_days),
                    )
                    for row in report.cohort_matrix
                ]
                or [("", "", "", "", "", "", "", "")],
                col_widths=(
                    24 * mm,
                    15 * mm,
                    16 * mm,
                    24 * mm,
                    20 * mm,
                    20 * mm,
                    28 * mm,
                    28 * mm,
                ),
            ),
            PdfTableSpec(
                title="Bottlenecks",
                headers=("Priority", "Category", "Label", "Value", "Pressure", "Detail"),
                rows=[
                    (
                        row.priority_key,
                        row.category,
                        row.label,
                        _format_number(row.metric_value),
                        f"{row.pressure_score:.3f}",
                        row.detail,
                    )
                    for row in report.bottlenecks
                ]
                or [("", "", "No bottleneck rows triggered", "", "", "")],
                col_widths=(30 * mm, 32 * mm, 58 * mm, 22 * mm, 22 * mm, 90 * mm),
            ),
        )

    def _table_section(
        self,
        spec: PdfTableSpec,
        context: "_ReportLabContext",
    ) -> list[object]:
        return [
            # Avoid orphaned section headings at the bottom of a page.
            context.CondPageBreak(32 * context.mm),
            context.Paragraph(_wrap(spec.title), context.heading_style),
            self._table(spec, context),
            context.Spacer(1, 4 * context.mm),
        ]

    def _table(self, spec: PdfTableSpec, context: "_ReportLabContext"):
        # LongTable repeats the header and splits by row when a table crosses pages.
        rows = _split_oversized_rows(spec.rows, spec.col_widths)
        table_rows = [
            [
                context.Paragraph(_wrap(value), context.header_style)
                for value in spec.headers
            ],
            *[
                [context.Paragraph(_wrap(value), context.cell_style) for value in row]
                for row in rows
            ],
        ]
        table = context.LongTable(
            table_rows,
            colWidths=list(spec.col_widths),
            repeatRows=1,
            splitByRow=1,
            hAlign="LEFT",
        )
        table.setStyle(
            context.TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        context.colors.HexColor("#e8edf5"),
                    ),
                    (
                        "TEXTCOLOR",
                        (0, 0),
                        (-1, 0),
                        context.colors.HexColor("#101820"),
                    ),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.25,
                        context.colors.HexColor("#9aa6b2"),
                    ),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        return table

    @staticmethod
    def _draw_footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColorRGB(0.35, 0.39, 0.45)
        canvas.drawRightString(
            doc.pagesize[0] - doc.rightMargin,
            7 * 2.834645669,
            f"Page {doc.page}",
        )
        canvas.drawString(
            doc.leftMargin,
            7 * 2.834645669,
            "Deterministic analytics - no language model evaluation",
        )
        canvas.restoreState()


@dataclass(frozen=True)
class _ReportLabContext:
    Paragraph: object
    Spacer: object
    CondPageBreak: object
    KeepTogether: object
    LongTable: object
    TableStyle: object
    colors: object
    heading_style: object
    body_style: object
    cell_style: object
    header_style: object
    mm: float


def _exam_rows(exams: Sequence[AnalyticsExam]) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    for exam in sorted(exams, key=lambda item: (item.exam_date, item.course_name.casefold())):
        rows.append(
            (
                exam.exam_date.isoformat(),
                exam.course_name,
                _optional(exam.course_id),
                exam.instructor,
                _period_text(exam),
                _cohort_text(exam),
            )
        )
    return rows or [("", "No scheduled exams were available", "", "", "", "")]


def _split_oversized_rows(
    rows: Sequence[Sequence[object]],
    col_widths: Sequence[float],
) -> list[tuple[object, ...]]:
    split_rows: list[tuple[object, ...]] = []
    max_chars = [_max_cell_chars(width) for width in col_widths]

    # ReportLab cannot split a single very tall row, so split long text first.
    for row in rows:
        cells = ["" if value is None else str(value) for value in row]
        chunks_by_cell = [
            _chunk_text(cell, max_chars[index])
            for index, cell in enumerate(cells)
        ]
        chunk_count = max(len(chunks) for chunks in chunks_by_cell)
        for chunk_index in range(chunk_count):
            split_rows.append(
                tuple(
                    chunks[chunk_index] if chunk_index < len(chunks) else ""
                    for chunks in chunks_by_cell
                )
            )
    return split_rows


def _chunk_text(value: str, max_chars: int) -> list[str]:
    if len(value) <= max_chars:
        return [value]

    words = value.split()
    if not words:
        return [value[index:index + max_chars] for index in range(0, len(value), max_chars)]

    chunks: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
        while len(word) > max_chars:
            chunks.append(word[:max_chars])
            word = word[max_chars:]
        current = word

    if current:
        chunks.append(current)
    return chunks or [""]


def _max_cell_chars(width_points: float) -> int:
    # Keep a row short enough that ReportLab can move it as a unit to the next page.
    return max(24, int(width_points / 3.8) * 8)


def _wrap(value: object) -> str:
    text = "" if value is None else str(value)
    return escape(text).replace("\n", "<br/>")


def _cohort_text(exam: AnalyticsExam) -> str:
    if not exam.cohorts:
        return ""
    return "; ".join(
        f"{cohort.program_id}/Y{cohort.year}/{cohort.requirement_type}"
        for cohort in exam.cohorts
    )


def _period_text(exam: AnalyticsExam) -> str:
    values = [value for value in (exam.semester_label, exam.term_label) if value]
    return " / ".join(values)


def _schedule_name(report: ScheduleAnalyticsReport) -> str:
    number = f" #{report.schedule_number}" if report.schedule_number is not None else ""
    return f"{report.schedule_label}{number}"


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _optional(value: object) -> str:
    return "" if value is None else str(value)


def _optional_float(value: float | None) -> str:
    return "" if value is None else _format_number(float(value))
