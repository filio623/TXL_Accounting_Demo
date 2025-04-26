import re
from typing import List, Dict, Pattern, Tuple, Optional
import logging
from decimal import Decimal
from pathlib import Path

from .matcher import Matcher
from .confidence import calculate_rule_based_confidence
from ..models.transaction import Transaction, MatchSource
from ..models.account import Account, ChartOfAccounts
from ..persistence.rule_store import RuleStore
from ..persistence.mapping_store import MappingStore, MappingData

logger = logging.getLogger(__name__)

class RuleMatcher(Matcher):
    """
    Enhanced rule-based matcher that checks mappings first, then applies rules.
    Uses RuleStore for rules and MappingStore for direct mappings.
    """
    
    # Define constants for default confidence scores based on rule type
    CONFIDENCE_EQUALS = 0.95
    CONFIDENCE_CONTAINS = 0.85
    # Add CONFIDENCE_REGEX if implementing regex rules
    
    def __init__(self,
                 chart_of_accounts: ChartOfAccounts,
                 rule_store_path: str | Path = "data/rules.json",
                 mapping_store_path: str | Path = "data/mappings.json",
                 mapping_confidence_threshold: float = 0.95):
        """
        Initialize the rule matcher, load rules and mappings.
        
        Args:
            chart_of_accounts: The chart of accounts to match against.
            rule_store_path: Path to the JSON file for storing/loading rules.
            mapping_store_path: Path to the JSON file for description-to-account mappings.
            mapping_confidence_threshold: Confidence score for direct mapping (acts as initial high score).
        """
        super().__init__(chart_of_accounts)
        self.rule_store = RuleStore(rule_store_path)
        self.mapping_store = MappingStore(mapping_store_path)
        # Load mappings first
        self.description_mappings = self._load_mappings()
        # Load rules after mappings
        self.rules: List[Dict] = self._load_or_initialize_rules() # Store rules as list of dicts
        # Note: We might process this list into a dict later for faster lookups if needed

        logger.info(f"RuleMatcher initialized. {len(self.rules)} rules loaded. {len(self.description_mappings)} mappings loaded.")

    def _load_mappings(self) -> Dict[str, str]:
        """Load mappings from the store."""
        loaded_mappings = self.mapping_store.load()
        if loaded_mappings is None: # Loading failed
            logger.error("Failed to load mappings from store. Initializing empty mappings.")
            return {}
        logger.info(f"Successfully loaded {len(loaded_mappings)} description mappings.")
        return loaded_mappings

    def _load_or_initialize_rules(self) -> List[Dict]: # Return type is List[Dict]
        """Load rules from RuleStore or initialize default structure."""
        loaded_rules = self.rule_store.load()
        
        if loaded_rules is None: # Error during loading
            logger.error("Failed to load rules from store due to errors. Initializing empty rules.")
            return [] # Return empty list
        elif isinstance(loaded_rules, list): # Successfully loaded a list
            logger.info(f"Successfully loaded {len(loaded_rules)} rules from {self.rule_store.file_path}")
            # Perform validation on each rule dict here if necessary
            # e.g., check for required keys
            valid_rules = []
            for rule in loaded_rules:
                if isinstance(rule, dict) and all(k in rule for k in ['condition_type', 'condition_value', 'account_number', 'priority']):
                    valid_rules.append(rule)
                else:
                    logger.warning(f"Skipping invalid rule format: {rule}")
            return valid_rules
        else:
            # This case should ideally not happen if RuleStore.load works correctly
            logger.warning(f"Loaded rules are not in the expected list format (got {type(loaded_rules).__name__}). Initializing empty rules.")
            return [] 

    def _apply_mapping(self, description: str) -> str:
        """Apply description mapping if available."""
        return self.description_mappings.get(description, description)

    def match_transaction(self, transaction: Transaction) -> None:
        """Match a transaction using mappings and rules."""
        
        mapped_description = self._apply_mapping(transaction.description)
        best_match_account: Optional[Account] = None
        highest_confidence: float = -1.0 # Use -1 to ensure first valid match is chosen
        highest_priority: int = -1

        # Iterate through the list of rules
        for rule in self.rules:
            match = False
            confidence = 0.0 # Default confidence for rules?
            priority = rule.get('priority', 0) # Default priority if missing
            condition_type = rule.get('condition_type')
            condition_value = rule.get('condition_value')
            account_number = rule.get('account_number')

            if not all([condition_type, condition_value, account_number]):
                logger.warning(f"Skipping rule due to missing fields: {rule}")
                continue

            # --- Rule Condition Matching Logic ---
            try:
                if condition_type == 'description_equals':
                    if mapped_description == condition_value:
                        match = True
                        confidence = self.CONFIDENCE_EQUALS
                elif condition_type == 'description_contains':
                    # Ensure condition_value is treated as string
                    if isinstance(condition_value, str) and condition_value in mapped_description:
                        match = True
                        confidence = self.CONFIDENCE_CONTAINS
                # Add elif for 'description_matches_regex' here if needed
                else:
                    logger.warning(f"Unsupported condition_type '{condition_type}' in rule: {rule}")
                    continue
            except Exception as e:
                logger.error(f"Error evaluating rule condition for rule {rule}: {e}", exc_info=True)
                continue
            # --- End Rule Condition Matching ---

            if match:
                # Find the account object using the correct method name
                potential_account = self.chart_of_accounts.find_account(str(account_number))
                if potential_account and self._validate_match(transaction, potential_account):
                    # Check priority and confidence
                    if priority > highest_priority:
                        highest_priority = priority
                        highest_confidence = confidence 
                        best_match_account = potential_account
                    elif priority == highest_priority and confidence > highest_confidence:
                        # If same priority, higher confidence wins
                        highest_confidence = confidence
                        best_match_account = potential_account
                        
        # Apply the best match found
        if best_match_account:
            transaction.add_match(best_match_account, highest_confidence, source=MatchSource.RULE) 
            # Note: add_match handles logic for primary vs alternative matches
            #       and MatchSource isn't part of its signature currently.
            # We might need to adjust Transaction.add_match or how we record source later.
            # logger.debug(f"Rule matched {transaction.description} to {best_match_account.number} (Conf: {highest_confidence:.2f}, Prio: {highest_priority})")
        # else: No rule match found
            # logger.debug(f"No rule match found for {transaction.description}")

    def get_match_confidence(self, transaction: Transaction, account: Account) -> float:
        """ 
        DEPRECATED/NEEDS REVIEW:
        Calculates confidence for a transaction against a *specific* account.
        The primary rule matching & confidence logic is now in `match_transaction`.
        This method needs review if account-specific confidence probing is needed.
        Returns 0.0 for now.
        """
        # TODO: Review if this method is needed. If so, rewrite to work with 
        # the self.rules list and define its specific purpose vs match_transaction.
        logger.debug(f"get_match_confidence called for Tx: {transaction.id} / Acc: {account.number} - Returning 0.0 (Method needs review)")
        return 0.0

    def add_rule(self, account: Account, pattern: str, confidence: float) -> None:
        """
        NEEDS IMPLEMENTATION:
        Adds a rule dynamically. Currently disabled as it needs updating for the 
        list-based rule structure (`self.rules`). Manual editing of rules.json is used.
        """
        # TODO: Implement this method to correctly append a rule dictionary 
        # to self.rules if dynamic rule addition is required.
        logger.warning(f"add_rule called for Acc: {account.number} - Method is currently disabled.")
        pass

    def _validate_match(self, transaction: Transaction, account: Account) -> bool:
        """
        Validate if a match is potentially valid based on basic rules.
        Checks if the account is a leaf node.
        
        Args:
            transaction: The transaction to validate.
            account: The account to validate against.
            
        Returns:
            bool: True if the match is potentially valid.
        """
        if account is None:
            logger.warning("_validate_match called with None account for Tx: {transaction.id}")
            return False
        if not account.is_leaf:
            # logger.debug(f"Validation failed for Tx: {transaction.id}: Account {account.number} is not a leaf account.")
            return False
        return True
