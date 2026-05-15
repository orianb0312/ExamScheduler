from src.parser.base_factory import BaseFactory
from academic import (
    Course, ProgramAffiliation, Exam, Project, Attendance,
    Semester, RequirementType
)

EVALUATION_MAP = {
    "Exam":       Exam(),
    "Project":    Project(),
    "Attendance": Attendance(),
}

SEMESTER_MAP = {
    "FALL": Semester.FALL,
    "SPRI": Semester.SPRING,
    "SUMM": Semester.SUMMER,
}

REQUIREMENT_MAP = {
    "Obligatory": RequirementType.OBLIGATORY,
    "Elective":   RequirementType.ELECTIVE,
}


class CourseFactory(BaseFactory[Course]):
    """Builds Course objects from courses_node entries."""

    def _build_one(self, course_dict: dict) -> Course:
        course = Course(
            course_id=int(course_dict["number"]),
            name=course_dict["name"],
            instructor=course_dict["instructor"],
            evaluation=EVALUATION_MAP[course_dict["evaluation"]],
        )
        for program in course_dict.get("programs", []):
            course.add_affiliation(self._build_affiliation(program))
        return course

    def _build_affiliation(self, program_dict: dict) -> ProgramAffiliation:
        return ProgramAffiliation(
            program_id=int(program_dict["number"]),
            year=int(program_dict["year"]),
            semester=SEMESTER_MAP[program_dict["semester"]],
            requirement_type=REQUIREMENT_MAP[program_dict["requirement"]],
        )


def build_courses_from_json(json_str: str) -> list[Course]:
    return CourseFactory().build_all(json_str, "courses_node")