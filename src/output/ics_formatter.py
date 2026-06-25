from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
import uuid

from src.output.i_output_formatter import IOutputFormatter
from src.output.output_models import ScheduledExam
from src.models.enums import Semester, Term


class ICSFormatter(IOutputFormatter):
    """
    Concrete strategy for exporting the exam schedule to an RFC 5545 compliant .ics format natively.
    Can mix CANCELLED and CONFIRMED events in a single PUBLISH file to sync the calendar state.
    """

    # Month-view cells are width-limited, and the limit is visual, not a raw
    # character count: Hebrew glyphs render wider than Latin ones, so the same
    # character count overflows in Hebrew while still fitting in English.
    # We therefore budget per script.
    ENGLISH_MAX_CHARS = 26
    HEBREW_MAX_CHARS = 14

    def get_extension(self) -> str:
        return ".ics"

    @staticmethod
    def _contains_hebrew(text: str) -> bool:
        """True if the text has any Hebrew-block character (U+0590-U+05FF)."""
        return any("\u0590" <= ch <= "\u05FF" for ch in text)

    def _cell_budget(self, name: str) -> int:
        """Return the character budget for the month-view cell, by script."""
        return self.HEBREW_MAX_CHARS if self._contains_hebrew(name) else self.ENGLISH_MAX_CHARS

    def _shorten(self, name: str) -> str:
        """
        Trim a course name to fit a narrow month-view cell.

        Cuts on a word boundary when possible and appends an ellipsis so the
        student sees the name is truncated. The full name always remains in
        DESCRIPTION, visible on click.
        """
        budget = self._cell_budget(name)
        if len(name) <= budget:
            return name

        clipped = name[:budget].rstrip()
        # Prefer cutting at the last space so we don't split a word mid-way.
        last_space = clipped.rfind(" ")
        if last_space >= budget // 2:
            clipped = clipped[:last_space].rstrip()
        return f"{clipped}\u2026"

    def _summary_body(self, name: str, course_id: int) -> str:
        """
        Build the month-view cell label for a course.

        If the full 'name (id)' fits within the per-script cell budget, keep the
        id so the student can identify the course at a glance. If it does not fit,
        drop the id and fall back to the (possibly shortened) name alone, since the
        cell is too narrow to show both without an Outlook scrollbar. The full name
        and id always remain available in DESCRIPTION on click.
        """
        with_id = f"{name} ({course_id})"
        if len(with_id) <= self._cell_budget(name):
            return with_id
        return self._shorten(name)

    def _fold_line(self, line: str) -> List[str]:
        """
        Strictly enforces RFC 5545 line folding by splitting the line into
        chunks where each chunk's UTF-8 encoded length does not exceed 75 octets.
        Subsequent chunks are prefixed with a single space.
        """
        line_bytes = line.encode('utf-8')
        if len(line_bytes) <= 75:
            return [line]

        folded_lines = []

        # First line chunk (up to 75 bytes)
        chunk = line_bytes[:75]
        while True:
            try:
                folded_lines.append(chunk.decode('utf-8'))
                break
            except UnicodeDecodeError:
                chunk = chunk[:-1]

        # Subsequent chunks (up to 74 bytes + 1 space byte)
        remaining_bytes = line_bytes[len(chunk):]
        while remaining_bytes:
            chunk = remaining_bytes[:74]
            while True:
                try:
                    folded_lines.append(" " + chunk.decode('utf-8'))
                    break
                except UnicodeDecodeError:
                    chunk = chunk[:-1]
            remaining_bytes = remaining_bytes[len(chunk):]

        return folded_lines

    def format(
            self,
            publish_data: Optional[Dict[Semester, Dict[Term, List[ScheduledExam]]]] = None,
            cancel_data: Optional[Dict[Semester, Dict[Term, List[ScheduledExam]]]] = None
    ) -> str:
        if not publish_data and not cancel_data:
            return ""

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Bar Ilan Engineering Faculty//ExamScheduler V4.0//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH"
        ]

        dtstamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')

        def _add_events(data: Optional[Dict[Semester, Dict[Term, List[ScheduledExam]]]], is_cancellation: bool):
            if not data:
                return
            for semester, terms in data.items():
                for term, exams in terms.items():
                    for exam in exams:
                        unique_string = f"{exam.course_id}-{exam.exam_date.strftime('%Y%m%d')}"
                        generated_uid = f"{uuid.uuid5(uuid.NAMESPACE_DNS, unique_string)}@examscheduler.local"

                        # ORGANIZER line removed to stop Outlook from hiding the title
                        lines.extend([
                            "BEGIN:VEVENT",
                            f"UID:{generated_uid}",
                            f"DTSTAMP:{dtstamp}"
                        ])

                        if is_cancellation:
                            lines.extend(["STATUS:CANCELLED", "SEQUENCE:1"])
                            title_prefix = "[CANCELED] "
                        else:
                            lines.extend(["STATUS:CONFIRMED", "SEQUENCE:0"])
                            title_prefix = ""

                        term_display = str(exam.term.value).capitalize()

                        # SUMMARY is a narrow month-view cell. Show 'name (id)' when the
                        # whole thing fits the per-script budget; otherwise show just the
                        # (possibly shortened) name to avoid an Outlook scrollbar. The full
                        # name and id are always available in DESCRIPTION on click.
                        summary_title = f"{title_prefix}{self._summary_body(exam.course_name, exam.course_id)}"
                        lines.append(f"SUMMARY:{summary_title}")

                        # All the full detail is preserved here - full name, id, instructor, semester
                        full_exam_title = f"Exam: {exam.course_name} ({exam.course_id}) - {term_display}"
                        lines.append(
                            f"DESCRIPTION:{full_exam_title}\\n"
                            f"Instructor: {exam.instructor}\\n"
                            f"Semester: {exam.semester.value}"
                        )

                        if getattr(exam, 'start_time', None) is not None and getattr(exam, 'end_time',
                                                                                     None) is not None:
                            start_str = f"{exam.exam_date.strftime('%Y%m%d')}T{exam.start_time.strftime('%H%M%S')}"
                            end_str = f"{exam.exam_date.strftime('%Y%m%d')}T{exam.end_time.strftime('%H%M%S')}"
                            lines.append(f"DTSTART;TZID=Asia/Jerusalem:{start_str}")
                            lines.append(f"DTEND;TZID=Asia/Jerusalem:{end_str}")
                        else:
                            start_str = exam.exam_date.strftime("%Y%m%d")
                            end_str = (exam.exam_date + timedelta(days=1)).strftime("%Y%m%d")
                            lines.append(f"DTSTART;VALUE=DATE:{start_str}")
                            lines.append(f"DTEND;VALUE=DATE:{end_str}")

                        lines.append("END:VEVENT")

        # First add cancellations, then new published events
        _add_events(cancel_data, is_cancellation=True)
        _add_events(publish_data, is_cancellation=False)

        lines.append("END:VCALENDAR")

        # Hard line folding to protect Hebrew characters
        folded_lines = []
        for line in lines:
            folded_lines.extend(self._fold_line(line))

        return "\r\n".join(folded_lines)