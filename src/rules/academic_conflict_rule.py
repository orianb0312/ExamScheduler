from datetime import date
from typing import Dict, List
from src.interfaces import ISchedulingRule
from src.models.academic import Course, ProgramAffiliation
from src.models.enums import RequirementType


class AcademicConflictRule(ISchedulingRule):
    """
    מממש את חוק גרסה 1.0: אין לשבץ שתי בחינות מאותה שנה ובאותה תוכנית באותו יום,
    אלא אם שתי הבחינות הן של קורסי בחירה[cite: 27].
    """

    def is_valid(self, attempt_state: Dict[Course, date]) -> bool:
        # בדיקה רק עבור הקורסים ששובצו באותו תאריך בדיוק
        dates_to_courses = {}
        for course, exam_date in attempt_state.items():
            if exam_date not in dates_to_courses:
                dates_to_courses[exam_date] = []
            dates_to_courses[exam_date].append(course)

        for exam_date, courses in dates_to_courses.items():
            if len(courses) < 2:
                continue

            # בדיקת כל זוג קורסים שמשובצים באותו יום
            for i in range(len(courses)):
                for j in range(i + 1, len(courses)):
                    if self._has_critical_conflict(courses[i], courses[j]):
                        return False
        return True

    def _has_critical_conflict(self, c1: Course, c2: Course) -> bool:
        for aff1 in c1.affiliations:
            for aff2 in c2.affiliations:
                # בדיקה אם הם באותה תוכנית ובאותה שנה [cite: 27, 59]
                if aff1.program_id == aff2.program_id and aff1.year == aff2.year:
                    # התנגשות קריטית קיימת אם לפחות אחד מהם הוא חובה [cite: 27]
                    if (aff1.requirement_type == RequirementType.OBLIGATORY or
                            aff2.requirement_type == RequirementType.OBLIGATORY):
                        return True
        return False