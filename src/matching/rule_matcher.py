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

logger = logging.getLogger(__name__)

class RuleMatcher(Matcher):
    """
    Rule-based matcher that uses pattern matching and rules to match transactions to accounts.
    Uses RuleStore to load/save rules.
    """
    
    def __init__(self, chart_of_accounts: ChartOfAccounts, rule_store_path: str | Path = "data/rules.json"):
        """
        Initialize the rule matcher with a chart of accounts and load rules.
        
        Args:
            chart_of_accounts: The chart of accounts to match against.
            rule_store_path: Path to the JSON file for storing/loading rules.
        """
        super().__init__(chart_of_accounts)
        self.rule_store = RuleStore(rule_store_path)
        self.rules: Dict[str, List[Tuple[str, float]]] = self._load_or_initialize_rules()
    
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
        Match a transaction to accounts using regex rules.
        Updates the transaction with match results.
        
        Args:
            transaction: The transaction to match
        """
        best_match = None
        best_confidence = 0.0
        alternative_matches = []
        
        # Check each account against our rules
        for account in self.chart_of_accounts.get_leaf_accounts():
            confidence = self.get_match_confidence(transaction, account)
            if confidence > 0:
                if confidence > best_confidence:
                    # If we found a better match, move the current best to alternatives
                    if best_match:
                        alternative_matches.append((best_match, best_confidence))
                    best_match = account
                    best_confidence = confidence
                elif confidence > 0.3:  # Only keep alternatives with >30% confidence
                    alternative_matches.append((account, confidence))
        
        # Update the transaction with the match results
        if best_match:
            transaction.add_match(best_match, best_confidence)
            # Sort alternatives by confidence and keep top 3
            alternative_matches.sort(key=lambda x: x[1], reverse=True)
            transaction.alternative_matches = alternative_matches[:3]
    
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
