import time
from datetime import date, timedelta
from typing import List, Dict, Optional
from src.models.academic import Course
from src.models.scheduling import ExamPeriod
from src.interfaces import ISchedulingRule


class Scheduler:
    """
    מנוע הליבה האחראי על יצירת מערכות בחינות.
    משתמש ב-Backtracking עם Heuristic מסוג MCV/MRV לשיפור ביצועים (EXS-32).
    """

    def __init__(self, rules: List[ISchedulingRule]):
        self.rules = rules
        self.all_valid_schedules: List[Dict[Course, date]] = []

    def run(self, courses: List[Course], period: ExamPeriod) -> List[Dict[Course, date]]:
        """
        מריץ את אלגוריתם החיפוש ומדפיס דוח ביצועים.
        """
        start_time = time.time()
        self.all_valid_schedules = []
        available_dates = self._get_available_dates(period)

        # התחלת החיפוש הרקורסיבי
        self._backtrack({}, courses, available_dates)

        duration = time.time() - start_time
        print(f"\n" + "=" * 40)
        print(f" PERFORMANCE REPORT (EXS-32)")
        print(f" - Execution Time: {duration:.4f} seconds")
        print(f" - Solutions Found: {len(self.all_valid_schedules)}")
        print(f" - Status: {'PASSED' if duration < 30 else 'FAILED'}")
        print("=" * 40 + "\n")

        return self.all_valid_schedules

    def _get_available_dates(self, period: ExamPeriod) -> List[date]:
        """מייצר את כל התאריכים הזמינים בתקופה, ללא החרגות."""
        available = []
        current = period.start_date
        while current <= period.end_date:
            if period.is_date_valid(current):
                available.append(current)
            current += timedelta(days=1)
        return available

    def _backtrack(self, current_state: Dict[Course, date], remaining_courses: List[Course],
                   available_dates: List[date]):
        # תנאי עצירה - כל הקורסים שובצו
        if not remaining_courses:
            self.all_valid_schedules.append(current_state.copy())
            return

        # בחירת הקורס הבא לפי MCV/MRV - הקורס עם הכי פחות אופציות
        course = self._get_mrv_course(remaining_courses, current_state, available_dates)
        next_remaining = [c for c in remaining_courses if c != course]

        for exam_date in available_dates:
            current_state[course] = exam_date

            # Pruning: המשך רק אם המצב הנוכחי חוקי
            if self._is_state_valid(current_state):
                self._backtrack(current_state, next_remaining, available_dates)

            # ניקוי המפתח מהמילון (Backtrack)
            current_state.pop(course, None)

    def _get_mrv_course(self, remaining_courses: List[Course], current_state: Dict[Course, date],
                        available_dates: List[date]) -> Course:
        """מזהה את הקורס שיהיה הכי קשה לשבץ כדי לצמצם את עץ החיפוש."""

        def count_valid_options(c):
            options = 0
            for d in available_dates:
                current_state[c] = d
                if self._is_state_valid(current_state):
                    options += 1
                current_state.pop(c, None)
            return options

        # החזרת הקורס עם מספר האופציות הקטן ביותר
        return min(remaining_courses, key=count_valid_options)

    def _is_state_valid(self, state: Dict[Course, date]) -> bool:
        """בודק את מצב השיבוץ הנוכחי מול כל החוקים."""
        for rule in self.rules:
            if not rule.is_valid(state):
                return False
        return True