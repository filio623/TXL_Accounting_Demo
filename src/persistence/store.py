from abc import ABC, abstractmethod
from typing import Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class PersistenceStore(ABC):
    """Abstract base class for persistence stores."""

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        # Ensure the directory exists
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
             logger.error(f"Error creating directory {self.file_path.parent}: {e}")
             # Decide how to handle this - maybe raise the error?
             # For now, log and continue, assuming the path might still be writable.

    @abstractmethod
    def save(self, data: Any) -> None:
        """Save data to the persistence file."""
        pass

    @abstractmethod
    def load(self) -> Any:
        """Load data from the persistence file."""
        pass 