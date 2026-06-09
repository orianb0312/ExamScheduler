"""Write the currently selected schedule to a readable text file."""

from __future__ import annotations

from pathlib import Path

from src.services.schedule_output_service import ScheduleExamDisplay, ScheduleSystem


class SelectedScheduleTextFormatter:
    """Format one UI-selected schedule without regenerating scheduler output."""

    def get_extension(self) -> str:
        return ".txt"

    def format(self, schedule: ScheduleSystem) -> str:
        body = (
            self._format_periods(schedule)
            if schedule.periods
            else schedule.text.strip()
        )
        if not body:
            raise ValueError("The selected schedule has no readable content.")

        return "\n".join(
            [
                "SELECTED EXAM SCHEDULE",
                "=" * 65,
                "",
                body,
                "",
            ]
        )

    def _format_periods(self, schedule: ScheduleSystem) -> str:
        lines = [f"{schedule.label} #{schedule.number}", ""]

        for period in schedule.periods:
            lines.append(f"=== SEMESTER: {period.semester_label} ===")
            lines.append(f"  [TERM: {period.term_label}]")
            lines.append("  " + "-" * 40)

            if not period.exams:
                lines.append("  No exams scheduled for this period.")
            else:
                for exam in sorted(period.exams, key=_exam_sort_key):
                    lines.append("  " + _format_exam_line(exam))

            lines.append("")

        return "\n".join(lines).rstrip()


class SelectedScheduleFileWriter:
    """Save one selected schedule to disk using an injected text formatter."""

    def __init__(self, formatter: SelectedScheduleTextFormatter | None = None) -> None:
        self._formatter = formatter or SelectedScheduleTextFormatter()

    @property
    def file_filter(self) -> str:
        return "Text Files (*.txt);;All Files (*)"

    def suggested_filename(self, schedule: ScheduleSystem) -> str:
        return f"schedule_{schedule.number}{self._formatter.get_extension()}"

    def write(self, schedule: ScheduleSystem | None, destination: str | Path) -> Path:
        if schedule is None:
            raise ValueError("No schedule is currently selected.")

        output_path = self._normalize_destination(destination)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self._formatter.format(schedule), encoding="utf-8")
        return output_path

    def _normalize_destination(self, destination: str | Path) -> Path:
        output_path = Path(destination)
        if output_path.suffix:
            return output_path
        return output_path.with_suffix(self._formatter.get_extension())


def _exam_sort_key(exam: ScheduleExamDisplay) -> tuple[str, str]:
    date_key = exam.exam_date.isoformat() if exam.exam_date is not None else ""
    return (date_key, exam.course_name.casefold())


def _format_exam_line(exam: ScheduleExamDisplay) -> str:
    date_text = exam.exam_date.isoformat() if exam.exam_date is not None else "No date"
    course_text = exam.course_name
    if exam.course_id is not None:
        course_text = f"{course_text} ({exam.course_id})"

    parts = [course_text, date_text, exam.instructor]
    if exam.program_ids:
        parts.append(
            "Programs: "
            + ", ".join(str(program_id) for program_id in exam.program_ids)
        )
    if exam.requirement_types:
        parts.append("Requirements: " + ", ".join(exam.requirement_types))

    return " | ".join(parts)
