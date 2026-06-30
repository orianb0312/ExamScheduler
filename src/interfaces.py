"""Shared backend interfaces used by schedulers and rule implementations."""

from abc import ABC, abstractmethod
from typing import Dict


class ISchedulingRule(ABC):
    """Polymorphic contract for V1 and Stage 3 scheduling constraints."""

    @abstractmethod
    def is_valid(self, attempt_state: Dict) -> bool:
        """Returns True if the current scheduling attempt is valid under this rule."""
        pass
