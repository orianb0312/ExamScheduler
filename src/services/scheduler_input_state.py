"""Application state used to prepare scheduler input from the UI."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence


class SchedulerInputState:
    """Keep selected programs and expose them through the existing file input flow."""

    def __init__(self, runtime_dir: Path) -> None:
        self._runtime_dir = runtime_dir
        self._selected_program_ids: tuple[str, ...] = ()

    @property
    def selected_program_ids(self) -> tuple[str, ...]:
        return self._selected_program_ids

    def set_selected_programs(self, program_ids: Sequence[str]) -> None:
        self._selected_program_ids = tuple(str(program_id) for program_id in program_ids)

    def write_selected_programs_file(self) -> Path:
        if not self._selected_program_ids:
            raise ValueError("Select at least one study program before generating schedules.")

        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        programs_file = self._runtime_dir / "ui_selected_programs.txt"
        programs_file.write_text(", ".join(self._selected_program_ids), encoding="utf-8")
        return programs_file
