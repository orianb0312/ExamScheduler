"""Selection rules for study programs in the desktop flow."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProgramSelectionPolicy:
    max_selected: int = 5
    limit_message: str = "You have reached the limit, you can select up to 5 study programs."

    def is_selection_count_allowed(self, selected_count: int) -> bool:
        return selected_count <= self.max_selected

    def is_limit_reached(self, selected_count: int) -> bool:
        return selected_count >= self.max_selected

    def message_for_count(self, selected_count: int) -> str:
        return self.limit_message if self.is_limit_reached(selected_count) else ""


DEFAULT_PROGRAM_SELECTION_POLICY = ProgramSelectionPolicy()
