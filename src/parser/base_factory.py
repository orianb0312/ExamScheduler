import json
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class BaseFactory(ABC, Generic[T]):
    """
    Template Method Pattern:
    Defines the skeleton of the build algorithm.
    Subclasses implement only the object-specific step.
    """

    def build_all(self, data_source: str | dict[str, Any], node_key: str) -> list[T]:
        """Template method for building all items from a parsed data node."""
        data = json.loads(data_source) if isinstance(data_source, str) else data_source
        return [self._build_one(item) for item in data[node_key]]

    @abstractmethod
    def _build_one(self, item_dict: dict) -> T:
        """Subclasses implement this step only."""
        pass
