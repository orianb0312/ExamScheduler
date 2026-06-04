"""Validation for file selections made on the input screen."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileSelectionValidation:
    """Result of checking the two required scheduler input files."""

    errors: tuple[str, ...]
    can_load: bool

    @property
    def message(self) -> str:
        if not self.errors:
            return ""
        return " Error: " + " | ".join(self.errors)


class FileSelectionValidator:
    """Keep file-system validation outside the PyQt widget."""

    def validate(
        self,
        courses_path: str,
        exam_dates_path: str,
    ) -> FileSelectionValidation:
        errors: list[str] = []

        courses_selected = bool(courses_path)
        exam_dates_selected = bool(exam_dates_path)
        courses_exists = _is_existing_file(courses_path)
        exam_dates_exists = _is_existing_file(exam_dates_path)

        if courses_selected and not courses_exists:
            errors.append("Courses file path is invalid or does not exist.")
        if exam_dates_selected and not exam_dates_exists:
            errors.append("Exam Dates file path is invalid or does not exist.")

        return FileSelectionValidation(
            errors=tuple(errors),
            can_load=not errors and courses_exists and exam_dates_exists,
        )


def _is_existing_file(path: str) -> bool:
    return bool(path) and Path(path).is_file()
