import json
import logging
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from .store import PersistenceStore

logger = logging.getLogger(__name__)

# Define the structure of the rules data for JSON serialization
# Format: { "account_number": [["pattern1", confidence1], ["pattern2", confidence2]], ... }
RulesData = Dict[str, List[List]] # More specific would be List[List[str | float]], but List suffices


class RuleStore(PersistenceStore):
    """Handles saving and loading of matching rules using JSON format."""

    def __init__(self, file_path: str | Path = "data/rules.json"):
        super().__init__(file_path)
        logger.info(f"RuleStore initialized with file path: {self.file_path.resolve()}")

    def save(self, rules: Dict[str, List[Tuple[str, float]]]) -> None:
        """
        Save the current matching rules to a JSON file.

        Args:
            rules: Dictionary containing the rules {account_number: [(pattern, confidence), ...]}.
        """
        # Convert tuples to lists for JSON compatibility
        rules_data: RulesData = {
            acc_num: [[pattern, conf] for pattern, conf in rule_list]
            for acc_num, rule_list in rules.items()
        }
        try:
            with open(self.file_path, 'w') as f:
                json.dump(rules_data, f, indent=4)
            logger.info(f"Successfully saved {len(rules)} accounts' rules to {self.file_path}")
        except IOError as e:
            logger.error(f"Error saving rules to {self.file_path}: {e}")
            # Consider re-raising or handling more gracefully
        except Exception as e:
            logger.error(f"An unexpected error occurred while saving rules: {e}")

    def load(self) -> Optional[Dict[str, List[Tuple[str, float]]]]:
        """
        Load matching rules from the JSON file specified during initialization.

        Returns:
            A dictionary containing the loaded rules {account_number: [(pattern, confidence), ...]}, 
            an empty dictionary if the file doesn't exist, or None if loading fails due to errors.
        """
        if not self.file_path.exists():
            logger.warning(f"Rules file not found at {self.file_path}. No rules loaded.")
            return {} # Return empty dict if file doesn't exist

        try:
            with open(self.file_path, 'r') as f:
                rules_data: RulesData = json.load(f)

            # Convert loaded lists back to the expected tuple format
            rules: Dict[str, List[Tuple[str, float]]] = {}
            for acc_num, rule_list in rules_data.items():
                rules[acc_num] = []
                for item in rule_list:
                    if isinstance(item, list) and len(item) == 2 and isinstance(item[0], str) and isinstance(item[1], (int, float)):
                        # Ensure confidence is float
                        rules[acc_num].append((item[0], float(item[1])))
                    else:
                         logger.warning(f"Skipping invalid rule data format for account {acc_num}: {item}")

            logger.info(f"Successfully loaded rules for {len(rules)} accounts from {self.file_path}")
            return rules
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {self.file_path}: {e}")
            return None # Indicate failure
        except IOError as e:
            logger.error(f"Error reading rules file {self.file_path}: {e}")
            return None # Indicate failure
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading rules: {e}")
            return None # Indicate failure
