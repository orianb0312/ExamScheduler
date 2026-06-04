"""Adapters for schedule text produced by the existing CLI output path."""

from __future__ import annotations

import re
from dataclasses import dataclass


_MARKER_PATTERN = re.compile(r"(?m)^(Complete System|Schedule) #(?P<number>\d+)\s*$")
_MAX_PREFIX_BUFFER = 64


@dataclass(frozen=True)
class ScheduleSystem:
    """One schedule system streamed from the CLI stdout pipe."""

    number: int
    text: str


class StdoutScheduleParser:
    """Stateful parser for schedule blocks that may arrive in partial chunks."""

    def __init__(self) -> None:
        self._buffer = ""

    def feed(self, text: str) -> list[ScheduleSystem]:
        """Consume a stdout chunk and return newly completed systems."""
        if not text:
            return []

        self._buffer += text
        self._drop_text_before_first_marker()
        return self._extract_complete_blocks(keep_last=True)

    def flush(self) -> list[ScheduleSystem]:
        """Return any final block left after the process exits."""
        systems = self._extract_complete_blocks(keep_last=False)
        self._buffer = ""
        return systems

    def reset(self) -> None:
        self._buffer = ""

    def _drop_text_before_first_marker(self) -> None:
        match = _MARKER_PATTERN.search(self._buffer)
        if match:
            if match.start() > 0:
                self._buffer = self._buffer[match.start():]
            return

        if len(self._buffer) > _MAX_PREFIX_BUFFER:
            self._buffer = self._buffer[-_MAX_PREFIX_BUFFER:]

    def _extract_complete_blocks(self, keep_last: bool) -> list[ScheduleSystem]:
        matches = list(_MARKER_PATTERN.finditer(self._buffer))
        if not matches:
            return []

        limit = len(matches) - 1 if keep_last else len(matches)
        systems: list[ScheduleSystem] = []

        for index in range(limit):
            start = matches[index].start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(self._buffer)
            system = self._build_system(matches[index], self._buffer[start:end])
            if system is not None:
                systems.append(system)

        if keep_last:
            self._buffer = self._buffer[matches[-1].start():]
        else:
            self._buffer = ""

        return systems

    @staticmethod
    def _build_system(match: re.Match[str], block: str) -> ScheduleSystem | None:
        text = block.strip()
        if not text:
            return None
        return ScheduleSystem(number=int(match.group("number")), text=text)
