"""UI-local cache for streamed schedule systems."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


DEFAULT_BATCH_SIZE = 1000


@dataclass(frozen=True)
class ScheduleSystem:
    """One schedule system streamed from the CLI stdout pipe."""

    number: int
    text: str


class ScheduleCache:
    """Store schedule systems in fixed-size batches for UI pagination."""

    def __init__(self, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        self.batch_size = batch_size
        self._batches: list[list[ScheduleSystem]] = []
        self._system_count = 0

    @property
    def system_count(self) -> int:
        return self._system_count

    @property
    def batch_count(self) -> int:
        return len(self._batches)

    def append(self, system: ScheduleSystem) -> None:
        if not self._batches or len(self._batches[-1]) >= self.batch_size:
            self._batches.append([])

        self._batches[-1].append(system)
        self._system_count += 1

    def extend(self, systems: Iterable[ScheduleSystem]) -> None:
        for system in systems:
            self.append(system)

    def get_batch(self, batch_index: int) -> list[ScheduleSystem]:
        """Return a zero-based batch copy."""
        if batch_index < 0 or batch_index >= self.batch_count:
            return []
        return list(self._batches[batch_index])

    def get_page(self, page_number: int) -> list[ScheduleSystem]:
        """Return a one-based page copy for UI controls."""
        return self.get_batch(page_number - 1)

    def clear(self) -> None:
        self._batches.clear()
        self._system_count = 0
