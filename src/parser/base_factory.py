import json
from abc import ABC, abstractmethod
from typing import TypeVar, Generic

T = TypeVar("T")

class BaseFactory(ABC, Generic[T]):
    """
    Template Method Pattern:
    Defines the skeleton of the build algorithm.
    Subclasses implement only the object-specific step.
    """

    def build_all(self, json_str: str, node_key: str) -> list[T]:
        """Template method — the invariant algorithm."""
        data = json.loads(json_str)
        return [self._build_one(item) for item in data[node_key]]

    @abstractmethod
    def _build_one(self, item_dict: dict) -> T:
        """Subclasses implement this step only."""
        pass