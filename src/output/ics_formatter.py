from typing import Dict, List, Optional
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import uuid
from icalendar import Calendar, Event

from src.output.i_output_formatter import IOutputFormatter
from src.output.output_models import ScheduledExam, Semester, Term


class ICSFormatter(IOutputFormatter):
    """
    Concrete strategy for exporting the exam schedule to an RFC 5545 compliant .ics format.
    Uses the external 'icalendar' library to handle structural integrity and compliant line-folding.
    Supports both publishing new schedules and revoking/cancelling previously exported ones.
    """

    def __init__(self, is_cancellation: bool = False):
        self.timezone = ZoneInfo("Asia/Jerusalem")
        self.is_cancellation = is_cancellation

    def get_extension(self) -> str:
        return ".ics"

    def format(self, structured_data: Optional[Dict[Semester, Dict[Term, List[ScheduledExam]]]]) -> str:
        if not structured_data:
            return ""

        cal = Calendar()
        cal.add('version', '2.0')
        cal.add('prodid', '-//Bar Ilan Engineering Faculty//ExamScheduler V4.0//EN')
        cal.add('calscale', 'GREGORIAN')

        # Toggle the METHOD parameter based on the cancellation flag
        calendar_method = "CANCEL" if self.is_cancellation else "PUBLISH"
        cal.add('method', calendar_method)

        for semester, terms in structured_data.items():
            for term, exams in terms.items():
                for exam in exams:
                    event = self._build_event(exam)
                    cal.add_component(event)

        # icalendar's to_ical() automatically executes strict RFC 5545 line folding (75 octets)
        # and outputs raw bytes, which we decode to safely return a UTF-8 encoded string.
        return cal.to_ical().decode('utf-8')

    def _build_event(self, exam: ScheduledExam) -> Event:
        event = Event()

        # 1. Deterministic UID Generation (CRITICAL for cancellation)
        # By using uuid5, the same course on the same date will ALWAYS generate the exact same UID.
        unique_string = f"{exam.course_id}-{exam.exam_date.strftime('%Y%m%d')}"
        generated_uid = f"{uuid.uuid5(uuid.NAMESPACE_DNS, unique_string)}@examscheduler.local"
        event.add('uid', generated_uid)

        # DTSTAMP must always be provided in UTC time
        dtstamp = datetime.now(ZoneInfo("UTC"))
        event.add('dtstamp', dtstamp)

        # 2. Add Cancellation Status if requested
        if self.is_cancellation:
            event.add('status', 'CANCELLED')

        summary_text = f"Exam: {exam.course_name} ({exam.course_id}) - {exam.term.value}"
        event.add('summary', summary_text)

        description_text = f"Instructor: {exam.instructor}\nSemester: {exam.semester.value}"
        event.add('description', description_text)

        # 3. Timezone & Explicit Structuring (Including specific hours functionality)
        if getattr(exam, 'start_time', None) is not None and getattr(exam, 'end_time', None) is not None:
            start_dt = datetime.combine(exam.exam_date, exam.start_time).replace(tzinfo=self.timezone)
            end_dt = datetime.combine(exam.exam_date, exam.end_time).replace(tzinfo=self.timezone)
            event.add('dtstart', start_dt)
            event.add('dtend', end_dt)
        else:
            # All-day fallback: icalendar automatically maps date objects to VALUE=DATE parameters.
            event.add('dtstart', exam.exam_date)
            # According to RFC 5545, DTEND for all-day events is non-inclusive, so we add exactly 1 day.
            event.add('dtend', exam.exam_date + timedelta(days=1))

        return event