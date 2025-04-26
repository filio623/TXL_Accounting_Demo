import json
import logging
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from .store import PersistenceStore

logger = logging.getLogger(__name__)

# Define the structure of the rules data for JSON serialization
# Format: List of rule objects, where each object has keys like 
# 'condition_type', 'condition_value', 'account_number', 'priority'
RulesData = List[Dict[str, str | int | float]] 


class RuleStore(PersistenceStore):
    """Handles saving and loading of matching rules using JSON format."""

    def __init__(self, file_path: str | Path = "data/rules.json"):
        super().__init__(file_path)
        logger.info(f"RuleStore initialized with file path: {self.file_path.resolve()}")

    def save(self, rules: RulesData) -> None:
        """
        Save the current matching rules (list of rule objects) to a JSON file.

        Args:
            rules: List of rule dictionaries.
        """
        # Assuming the input 'rules' is already in the correct list-of-dicts format
        try:
            with open(self.file_path, 'w') as f:
                json.dump(rules, f, indent=4) # Save the list directly
            logger.info(f"Successfully saved {len(rules)} rules to {self.file_path}")
        except IOError as e:
            logger.error(f"Error saving rules to {self.file_path}: {e}")
            # Consider re-raising or handling more gracefully
        except Exception as e:
            logger.error(f"An unexpected error occurred while saving rules: {e}")

    def load(self) -> Optional[RulesData]:
        """
        Load matching rules from the JSON file specified during initialization.
        Expects a JSON array of rule objects.

        Returns:
            A list of rule dictionaries, 
            an empty list if the file doesn't exist or is empty, 
            or None if loading fails due to JSON errors or other IO issues.
        """
        if not self.file_path.exists():
            logger.warning(f"Rules file not found at {self.file_path}. No rules loaded.")
            return [] # Return empty list if file doesn't exist

        try:
            with open(self.file_path, 'r') as f:
                # Handle potentially empty file
                content = f.read()
                if not content.strip():
                    logger.warning(f"Rules file {self.file_path} is empty. Returning empty list.")
                    return []
                
                rules_data: RulesData = json.loads(content) # Use json.loads on read content

            # Basic validation: Check if it's a list
            if not isinstance(rules_data, list):
                 logger.error(f"Error loading rules: Expected a list in {self.file_path}, but got {type(rules_data).__name__}. Returning None.")
                 return None

            # Optional: Add more validation for each rule object if needed here
            # e.g., check for required keys ('condition_type', 'condition_value', etc.)

            logger.info(f"Successfully loaded {len(rules_data)} rules from {self.file_path}")
            return rules_data # Return the list directly
            
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {self.file_path}: {e}")
            return None # Indicate failure
        except IOError as e:
            logger.error(f"Error reading rules file {self.file_path}: {e}")
            return None # Indicate failure
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading rules: {e}", exc_info=True) # Add exc_info for detail
            return None # Indicate failure
