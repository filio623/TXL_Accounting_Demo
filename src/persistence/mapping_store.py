import json
import logging
from typing import Dict, Optional
from pathlib import Path

from .store import PersistenceStore

logger = logging.getLogger(__name__)

# Define the structure of the mapping data for JSON serialization
# Format: { "Transaction Description": "Account Number", ... }
MappingData = Dict[str, str]

class MappingStore(PersistenceStore):
    """Handles saving and loading of transaction description to account mappings."""

    def __init__(self, file_path: str | Path = "data/mappings.json"):
        super().__init__(file_path)
        logger.info(f"MappingStore initialized with file path: {self.file_path.resolve()}")

    def save(self, mappings: MappingData) -> None:
        """
        Save the current description-to-account mappings to a JSON file.

        Args:
            mappings: Dictionary mapping transaction descriptions to account numbers.
        """
        try:
            with open(self.file_path, 'w') as f:
                json.dump(mappings, f, indent=4)
            logger.info(f"Successfully saved {len(mappings)} mappings to {self.file_path}")
        except IOError as e:
            logger.error(f"Error saving mappings to {self.file_path}: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while saving mappings: {e}")

    def load(self) -> Optional[MappingData]:
        """
        Load description-to-account mappings from the JSON file.

        Returns:
            A dictionary containing the loaded mappings, 
            an empty dictionary if the file doesn't exist, or None if loading fails.
        """
        if not self.file_path.exists():
            logger.warning(f"Mappings file not found at {self.file_path}. No mappings loaded.")
            return {} # Return empty dict if file doesn't exist

        try:
            with open(self.file_path, 'r') as f:
                mappings: MappingData = json.load(f)
            
            # Basic validation (ensure it's a dictionary of strings)
            if not isinstance(mappings, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in mappings.items()):
                logger.error(f"Invalid data format in mappings file {self.file_path}. Expected Dict[str, str].")
                return None # Indicate failure due to format

            logger.info(f"Successfully loaded {len(mappings)} mappings from {self.file_path}")
            return mappings
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {self.file_path}: {e}")
            return None # Indicate failure
        except IOError as e:
            logger.error(f"Error reading mappings file {self.file_path}: {e}")
            return None # Indicate failure
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading mappings: {e}")
            return None # Indicate failure

    def add_mapping(self, description: str, account_number: str) -> None:
        """
        Add or update a single mapping and save the entire store.
        Note: Loading and saving the entire file for each addition can be inefficient for large files.
        Consider batching updates or using a more robust storage mechanism if performance becomes an issue.

        Args:
            description: The transaction description.
            account_number: The corresponding account number.
        """
        mappings = self.load()
        if mappings is None:
            logger.error("Failed to load existing mappings. Cannot add new mapping.")
            return
        
        if description in mappings and mappings[description] != account_number:
            logger.info(f"Updating existing mapping for '{description}': {mappings[description]} -> {account_number}")
        elif description not in mappings:
            logger.info(f"Adding new mapping: '{description}' -> {account_number}")
        
        mappings[description] = account_number
        self.save(mappings)
