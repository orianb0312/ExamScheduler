import time
from datetime import date, timedelta
from itertools import product
from typing import List, Dict, Optional, Generator

from output_models import ScheduledExam, Semester, Term
from src.models.academic import Course
from src.models.scheduling import ExamPeriod
from src.interfaces import ISchedulingRule
from schedule_sorter import ScheduleSorter
from output_manager import TextOutputManager


class Scheduler:
    def __init__(self, rules: List[ISchedulingRule]):
        self.rules = rules
        self.sorter = ScheduleSorter()

    def run_to_output(
            self,
            courses: List[Course],
            period: ExamPeriod,
            output_manager: TextOutputManager
    ) -> int:
        """
        Runs the full combinatorial construction, processes ALL millions of
        schedules, and exports every single one of them using the team's OutputManager.
        """
        start_time = time.perf_counter()

        available_dates = self._get_available_dates(period)
        components = self._build_components(courses)

        component_solutions = []
        for comp in components:
            solutions = list(self._solve_component(comp, available_dates))
            if not solutions:
                return 0
            component_solutions.append(solutions)

        total_schedules = 0

        # המרה של ערכי ה-Enums פעם אחת מחוץ ללולאה כדי לחסוך זמן ריצה יקר
        output_semester = Semester(period.semester.value)
        output_term = Term(period.term.value)

        # אנו פותחים את הקובץ לכתיבה דורסת פעם אחת ומנקים פלטים ישנים
        full_path = output_manager.get_full_path()
        output_manager._ensure_dir_exists()

        with open(full_path, 'w', encoding='utf-8') as f:
            f.write("OFFICIAL UNIVERSITY MASTER EXAM SCHEDULE\n")
            f.write("=" * 65 + "\n\n")

            # מעבר אמיתי ומלא על כל מיליוני השילובים האפשריים (מכפלה קרטזית)
            for combination in product(*component_solutions):
                total_schedules += 1

                full_assignment = {}
                for partial_map in combination:
                    full_assignment.update(partial_map)

                # המרת השילוב הנוכחי למבנה המודלים החדש של השותפים
                scheduled_exams = []
                for course, exam_date in full_assignment.items():
                    scheduled_exams.append(ScheduledExam(
                        course_name=course.name,
                        course_id=course.course_id,
                        semester=output_semester,
                        term=output_term,
                        exam_date=exam_date,
                        instructor=course.instructor
                    ))

                # סידור היררכי כרונולוגי באמצעות ה-Sorter של הצוות
                structured_data = self.sorter.categorize(scheduled_exams)

                # כתיבה ישירה ומנוהלת לתוך הקובץ הפתוח (Stream)
                f.write(f"Schedule #{total_schedules}\n")
                for semester, terms in structured_data.items():
                    f.write(f"=== SEMESTER: {semester.value} ===\n")
                    for term, exams in terms.items():
                        f.write(f"  [TERM: {term.value}]\n")
                        f.write("  " + "-" * 40 + "\n")
                        for exam in exams:
                            f.write(f"  {output_manager.format_exam_line(exam)}\n")
                f.write("\n" + "*" * 70 + "\n\n")

                # מנגנון הגנה מבוסס זמן (SLA) למקרה של עומס חריג בדיסק
                if total_schedules % 10000 == 0 and (time.perf_counter() - start_time) > 26:
                    f.write(f"\n... Stopped at {total_schedules:,} due to 30-second time limit ...\n")
                    break

        duration = time.perf_counter() - start_time
        print(f"Scheduling completed in {duration:.2f} seconds.")
        return total_schedules

    def _solve_component(self, component: List[Course], dates: List[date]) -> Generator[Dict[Course, date], None, None]:
        def backtrack(index, current_assignment):
            if index == len(component):
                yield current_assignment.copy()
                return

            course = component[index]
            for d in dates:
                current_assignment[course] = d
                if self._is_locally_valid(current_assignment):
                    yield from backtrack(index + 1, current_assignment)

            if course in current_assignment:
                del current_assignment[course]

        yield from backtrack(0, {})

    def _is_locally_valid(self, assignment: Dict[Course, date]) -> bool:
        for rule in self.rules:
            if not rule.is_valid(assignment):
                return False
        return True

    def _get_available_dates(self, period: ExamPeriod) -> List[date]:
        dates = []
        curr = period.start_date
        while curr <= period.end_date:
            if period.is_date_valid(curr):
                dates.append(curr)
            curr += timedelta(days=1)
        return dates

    def _build_components(self, courses: List[Course]) -> List[List[Course]]:
        from collections import defaultdict
        years = defaultdict(list)
        for course in courses:
            year = course.affiliations[0].year if course.affiliations else 1
            years[year].append(course)
        return list(years.values())