import re
from typing import List, Dict, Pattern, Tuple
import logging
from decimal import Decimal

from .matcher import Matcher
from ..models.transaction import Transaction
from ..models.account import Account, ChartOfAccounts

logger = logging.getLogger(__name__)

class RuleMatcher(Matcher):
    """
    Rule-based matcher that uses pattern matching and rules to match transactions to accounts.
    """
    
    def __init__(self, chart_of_accounts: ChartOfAccounts):
        """
        Initialize the rule matcher with a chart of accounts.
        
        Args:
            chart_of_accounts: The chart of accounts to match against
        """
        super().__init__(chart_of_accounts)
        self.rules: Dict[str, List[Tuple[str, float]]] = {}  # account_number -> [(pattern, confidence), ...]
        self._initialize_rules()
    
    def _initialize_rules(self) -> None:
        """Initialize matching rules for each account."""
        for account in self.chart_of_accounts.get_leaf_accounts():
            self.rules[account.number] = []
            # Add default rules based on account name and number
            self.rules[account.number].append((account.name, 0.8))
            self.rules[account.number].append((account.number, 0.9))
    
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
        Calculate the confidence score for a potential match using rules.
        
        Args:
            transaction: The transaction to match
            account: The account to match against
            
        Returns:
            float: Confidence score between 0.0 and 1.0
        """
        if not self._validate_match(transaction, account):
            return 0.0

        max_confidence = 0.0
        for pattern, base_confidence in self.rules[account.number]:
            try:
                if re.search(pattern, transaction.description, re.IGNORECASE):
                    max_confidence = max(max_confidence, base_confidence)
            except re.error:
                continue  # Skip invalid regex patterns

        return max_confidence
    
    def add_rule(self, account: Account, pattern: str, confidence: float) -> None:
        """
        Add a custom matching rule for an account.
        
        Args:
            account: The account to add the rule for
            pattern: The regex pattern to match against
            confidence: Base confidence score for this rule (default: 0.8)
        """
        if not self._validate_match(None, account):
            return

        try:
            # Validate the regex pattern
            re.compile(pattern)
            self.rules[account.number].append((pattern, confidence))
        except re.error:
            pass  # Skip invalid regex patterns
