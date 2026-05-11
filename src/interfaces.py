from abc import ABC, abstractmethod
from typing import Dict
from datetime import date

class ISchedulingRule(ABC):
    @abstractmethod
    def is_valid(self, attempt_state: Dict) -> bool:
        """Returns True if the current scheduling attempt is valid under this rule."""
        pass