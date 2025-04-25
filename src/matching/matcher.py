from abc import ABC, abstractmethod
from typing import List, Optional, Type
import logging

from ..models.transaction import Transaction
from ..models.account import Account, ChartOfAccounts

# Removed imports for RuleMatcher, LLMMatcher as MatchingEngine is moved

logger = logging.getLogger(__name__)


class Matcher(ABC):
    """
    Abstract base class for transaction matchers.
    Defines the interface that all matchers must implement.
    """
    
    def __init__(self, chart_of_accounts: ChartOfAccounts):
        """
        Initialize the matcher with a chart of accounts.
        
        Args:
            chart_of_accounts: The chart of accounts to match against
        """
        self.chart_of_accounts = chart_of_accounts
    
    @abstractmethod
    def match_transaction(self, transaction: Transaction) -> None:
        """
        Match a single transaction to one or more accounts.
        Updates the transaction with match results.
        
        Args:
            transaction: The transaction to match
        """
        pass
    
    def process_transactions(self, transactions: List[Transaction]) -> List[Transaction]:
        """
        Process multiple transactions and match them to accounts.
        Updates each transaction with match results.
        
        Args:
            transactions: List of transactions to match
            
        Returns:
            List[Transaction]: The processed transactions with matches
        """
        count = 0
        for transaction in transactions:
            # Check if already matched with sufficient confidence? 
            # Maybe the engine should pass only unmatched items?
            # For now, process all passed transactions.
            self.match_transaction(transaction)
            count += 1
        # logger.debug(f"{type(self).__name__} processed {count} transactions.") # Optional debug logging
        return transactions
    
    @abstractmethod
    def get_match_confidence(self, transaction: Transaction, account: Account) -> float:
        """
        Calculate the confidence score for a potential match.
        
        Args:
            transaction: The transaction to match
            account: The account to match against
            
        Returns:
            float: Confidence score between 0.0 and 1.0
        """
        pass
    
    def _validate_match(self, transaction: Transaction, account: Account) -> bool:
        """
        Validate if a match is potentially valid based on basic rules.
        Can be overridden by specific matchers for additional validation.
        
        Args:
            transaction: The transaction to validate
            account: The account to validate against
            
        Returns:
            bool: True if the match is potentially valid
        """
        # Basic validation rules that apply to all matchers
        if account is None:
             logger.warning("_validate_match called with None account")
             return False
        if not account.is_leaf:
            # logger.debug(f"Validation failed: Account {account.number} is not a leaf account.")
            return False  # Only match against leaf accounts
            
        # Add more validation rules as needed
        return True

# Removed MatchingEngine class definition
