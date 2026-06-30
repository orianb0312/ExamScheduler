"""Incrementally track the best generated schedule seen so far."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence

from src.services.schedule_output_service import ScheduleSystem
from src.sorting.schedule_priority import (
    DEFAULT_SORT_PRIORITY,
    SchedulePrioritySorter,
    normalize_sort_priority,
    sortable_exams_from_display_system,
)

ScoreProvider = Callable[[ScheduleSystem, tuple[str, ...]], tuple[float, ...]]


class ScheduleBestTracker:
    """Keep a rolling best schedule without copying or re-sorting all systems."""

    def __init__(
        self,
        sorter: SchedulePrioritySorter | None = None,
        score_provider: ScoreProvider | None = None,
    ) -> None:
        self._sorter = sorter or SchedulePrioritySorter()
        self._score_provider = score_provider
        self._priority: tuple[str, ...] = ()
        self._best_schedule: ScheduleSystem | None = None
        self._best_score: tuple[float, ...] = ()

    @property
    def priority(self) -> tuple[str, ...]:
        return self._priority

    @property
    def best_schedule(self) -> ScheduleSystem | None:
        return self._best_schedule

    def matches_priority(self, priority: Sequence[str]) -> bool:
        return self._priority == _effective_priority(priority)

    def reset(self, priority: Sequence[str] = ()) -> None:
        self._priority = _effective_priority(priority)
        self._best_schedule = None
        self._best_score = ()

    def rebuild(
        self,
        schedules: Iterable[ScheduleSystem],
        priority: Sequence[str],
    ) -> None:
        self.reset(priority)
        self.update_batch(schedules)

    def update_batch(self, schedules: Iterable[ScheduleSystem]) -> None:
        for schedule in schedules:
            self._consider(schedule)

    def _consider(self, schedule: ScheduleSystem) -> None:
        if self._score_provider is None:
            score = self._sorter.score_tuple(
                sortable_exams_from_display_system(schedule),
                self._priority,
            )
        else:
            score = self._score_provider(schedule, self._priority)
        if self._best_schedule is None or score > self._best_score:
            self._best_schedule = schedule
            self._best_score = score


def _effective_priority(priority: Sequence[str]) -> tuple[str, ...]:
    clean_priority = normalize_sort_priority(priority)
    return clean_priority or DEFAULT_SORT_PRIORITY
