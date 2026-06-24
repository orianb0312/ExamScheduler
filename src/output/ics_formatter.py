from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
import uuid

from src.output.i_output_formatter import IOutputFormatter
from src.output.output_models import ScheduledExam
from src.models.enums import Semester, Term

class ICSFormatter(IOutputFormatter):
    """
    Concrete strategy for exporting the exam schedule to an RFC 5545 compliant .ics format natively.
    Implements standard cancellation methodology using METHOD:CANCEL and SEQUENCE increment.
    """

    def __init__(self, is_cancellation: bool = False):
        self.is_cancellation = is_cancellation

    def get_extension(self) -> str:
        return ".ics"

    def format(self, structured_data: Optional[Dict[Semester, Dict[Term, List[ScheduledExam]]]]) -> str:
        if not structured_data:
            return ""

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Bar Ilan Engineering Faculty//ExamScheduler V4.0//EN",
            "CALSCALE:GREGORIAN",
            f"METHOD:{'CANCEL' if self.is_cancellation else 'PUBLISH'}"
        ]

        # Fix for Python 3.12+ DeprecationWarning: use timezone-aware datetime instead of utcnow()
        dtstamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')

        for semester, terms in structured_data.items():
            for term, exams in terms.items():
                for exam in exams:
                    # Deterministic UID Generation
                    unique_string = f"{exam.course_id}-{exam.exam_date.strftime('%Y%m%d')}"
                    generated_uid = f"{uuid.uuid5(uuid.NAMESPACE_DNS, unique_string)}@examscheduler.local"

                    lines.extend([
                        "BEGIN:VEVENT",
                        f"UID:{generated_uid}",
                        f"DTSTAMP:{dtstamp}",
                        "ORGANIZER;CN=Exam Scheduler:MAILTO:scheduler@biu.ac.il"
                    ])

                    if self.is_cancellation:
                        # Standard RFC 5545 revocation
                        lines.extend(["STATUS:CANCELLED", "SEQUENCE:1"])
                        title_prefix = "[CANCELED] "
                    else:
                        lines.extend(["STATUS:CONFIRMED", "SEQUENCE:0"])
                        title_prefix = ""

                    term_display = str(exam.term.value).capitalize()
                    lines.append(f"SUMMARY:{title_prefix}Exam: {exam.course_name} ({exam.course_id}) - {term_display}")
                    lines.append(f"DESCRIPTION:Instructor: {exam.instructor}\\nSemester: {exam.semester.value}")

                    if getattr(exam, 'start_time', None) is not None and getattr(exam, 'end_time', None) is not None:
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

        lines.append("END:VCALENDAR")
        return "\r\n".join(lines)