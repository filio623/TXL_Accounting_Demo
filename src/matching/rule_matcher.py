import re
from typing import List, Dict, Pattern, Tuple, Optional
import logging
from decimal import Decimal
from pathlib import Path

from .matcher import Matcher
from .confidence import calculate_rule_based_confidence
from ..models.transaction import Transaction
from ..models.account import Account, ChartOfAccounts
from ..persistence.rule_store import RuleStore
from ..persistence.mapping_store import MappingStore, MappingData

logger = logging.getLogger(__name__)

class RuleMatcher(Matcher):
    """
    Enhanced rule-based matcher that checks mappings first, then applies rules.
    Uses RuleStore for rules and MappingStore for direct mappings.
    """
    
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
        self.rules: Dict[str, List[Tuple[str, float]]] = self._load_or_initialize_rules()
        self.mappings: MappingData = self._load_mappings()
        self.mapping_confidence_threshold = max(0.0, min(1.0, mapping_confidence_threshold))
        
    def _load_mappings(self) -> MappingData:
        """Load mappings from the store."""
        loaded_mappings = self.mapping_store.load()
        if loaded_mappings is None: # Loading failed
            logger.error("Failed to load mappings from store. Initializing empty mappings.")
            return {}
        logger.info(f"Successfully loaded {len(loaded_mappings)} description mappings.")
        return loaded_mappings

    def _load_or_initialize_rules(self) -> Dict[str, List[Tuple[str, float]]]:
        """Load rules from the store or initialize defaults if loading fails or file is empty."""
        loaded_rules = self.rule_store.load()
        
        if loaded_rules is not None and loaded_rules: # Check if loaded successfully and is not empty
            logger.info(f"Successfully loaded {len(loaded_rules)} accounts' rules from {self.rule_store.file_path}")
            # Ensure all leaf accounts have at least an empty list in rules
            all_rules = loaded_rules
            for account in self.chart_of_accounts.get_leaf_accounts():
                if account.number not in all_rules:
                    all_rules[account.number] = []
            return all_rules
        elif loaded_rules == {}: # File didn't exist or was empty
             logger.info("No existing rules file found or file empty. Initializing default rules.")
             return self._initialize_default_rules()
        else: # Loading failed due to an error
            logger.error("Failed to load rules from store. Initializing default rules as fallback.")
            return self._initialize_default_rules()

    def _initialize_default_rules(self) -> Dict[str, List[Tuple[str, float]]]:
        """Initialize default matching rules for each account."""
        default_rules = {}
        for account in self.chart_of_accounts.get_leaf_accounts():
            rules_list = []
            # Add default rules based on account name and number
            rules_list.append((account.name, 0.8))
            rules_list.append((account.number, 0.9))
            default_rules[account.number] = rules_list
        return default_rules
    
    def save_rules(self) -> None:
        """Save the current state of the rules to the persistence store."""
        logger.info(f"Attempting to save rules to {self.rule_store.file_path}")
        self.rule_store.save(self.rules)

    def match_transaction(self, transaction: Transaction) -> None:
        """
        Match a transaction: check mappings, then apply rules, allowing rules to override mappings.
        Updates the transaction with the best match found.
        
        Args:
            transaction: The transaction to match
        """
        best_match: Optional[Account] = None
        best_confidence: float = 0.0
        alternative_matches: List[Tuple[Account, float]] = []

        # 1. Check Direct Mappings (Treat as initial best guess)
        mapped_account_number = self.mappings.get(transaction.description)
        if mapped_account_number:
            mapped_account = self.chart_of_accounts.find_account(mapped_account_number)
            if mapped_account and mapped_account.is_leaf:
                logger.debug(f"Mapping found for '{transaction.description}' -> {mapped_account.number}. Treating as initial match with confidence {self.mapping_confidence_threshold:.2f}")
                best_match = mapped_account
                best_confidence = self.mapping_confidence_threshold
                # Don't return yet, let rules potentially override
            elif mapped_account:
                 logger.warning(f"Mapping found for '{transaction.description}' to {mapped_account_number}, but it's not a leaf account. Ignoring mapping.")
            else:
                logger.warning(f"Mapping found for '{transaction.description}' to non-existent account {mapped_account_number}. Ignoring mapping.")

        # 2. Apply rules and compare with mapping confidence (if any)
        for account in self.chart_of_accounts.get_leaf_accounts():
            confidence = self.get_match_confidence(transaction, account)
            
            if confidence > best_confidence:
                # New best match found (either better than mapping or better than previous rule)
                if best_match: # Move the previous best (mapping or rule) to alternatives
                     alternative_matches.append((best_match, best_confidence))
                best_match = account
                best_confidence = confidence
                logger.debug(f"New best match found via rule for '{transaction.description}': {account.number} (Confidence: {confidence:.2f})")
            elif confidence > 0.3: # Consider as alternative if confidence is decent
                 # Avoid adding the initial mapped account as an alternative to itself if it wasn't overridden
                 if best_match != account:
                    alternative_matches.append((account, confidence))
        
        # Update the transaction with the final best match
        if best_match:
            transaction.add_match(best_match, best_confidence)
            # Sort alternatives and add to transaction
            alternative_matches.sort(key=lambda x: x[1], reverse=True)
            # Ensure we don't add the final best match as an alternative
            transaction.alternative_matches = [alt for alt in alternative_matches[:3] if alt[0] != best_match]

    def get_match_confidence(self, transaction: Transaction, account: Account) -> float:
        """
        Calculate the highest confidence score for a match using rules.
        Uses the centralized calculate_rule_based_confidence function.
        
        Args:
            transaction: The transaction to match
            account: The account to match against
            
        Returns:
            float: Highest confidence score found (0.0 to 1.0)
        """
        if not self._validate_match(transaction, account):
            return 0.0

        max_confidence = 0.0
        best_matching_rule = None

        # Find the rule with the highest base confidence that matches
        for rule in self.rules.get(account.number, []):
            pattern, base_confidence = rule
            try:
                if re.search(pattern, transaction.description, re.IGNORECASE):
                    # We found a match, calculate its specific confidence
                    current_confidence = calculate_rule_based_confidence(transaction, account, rule)
                    if current_confidence > max_confidence:
                        max_confidence = current_confidence
                        # We might want to store the *rule* that gave the best confidence later
                        # best_matching_rule = rule 
            except re.error as e:
                logger.warning(f"Skipping invalid regex pattern '{pattern}' for account {account.number}: {e}")
                continue

        return max_confidence
    
    def add_rule(self, account: Account, pattern: str, confidence: float) -> None:
        """
        Add a custom matching rule for an account.
        
        Args:
            account: The account to add the rule for
            pattern: The regex pattern to match against
            confidence: Base confidence score for this rule (default: 0.8)
        """
        if not account.is_leaf:
            logger.warning(f"Cannot add rule to non-leaf account: {account.number} - {account.name}")
            return

        try:
            # Validate the regex pattern
            re.compile(pattern)
            # Use setdefault to ensure the list exists before appending
            self.rules.setdefault(account.number, []).append((pattern, confidence))
            logger.info(f"Added rule for account {account.number}: pattern='{pattern}', confidence={confidence}")
        except re.error as e:
            logger.error(f"Invalid regex pattern '{pattern}' for account {account.number}: {e}")
