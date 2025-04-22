from abc import ABC, abstractmethod
from typing import List, Optional

from ..models.transaction import Transaction
from ..models.account import Account, ChartOfAccounts


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
        for transaction in transactions:
            self.match_transaction(transaction)
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
        if not account.is_leaf:
            return False  # Only match against leaf accounts
            
        # Add more validation rules as needed
        return True


class MatchingEngine:
    """
    Main matching engine that coordinates different matchers and manages the matching process.
    This is the primary interface used by the main application.
    """
    
    def __init__(self, chart_of_accounts: ChartOfAccounts):
        """
        Initialize the matching engine with a chart of accounts.
        
        Args:
            chart_of_accounts: The chart of accounts to match against
        """
        self.chart_of_accounts = chart_of_accounts
        self.matchers: List[Matcher] = []
    
    def add_matcher(self, matcher: Matcher) -> None:
        """
        Add a matcher to the engine.
        
        Args:
            matcher: The matcher to add
        """
        self.matchers.append(matcher)
    
    def process_transactions(self, transactions: List[Transaction]) -> List[Transaction]:
        """
        Process transactions through all registered matchers.
        Each matcher will attempt to match the transactions and update them with results.
        
        Args:
            transactions: List of transactions to process
            
        Returns:
            List[Transaction]: The processed transactions with matches
        """
        if not self.matchers:
            raise RuntimeError("No matchers registered with the engine")
            
        for matcher in self.matchers:
            matcher.process_transactions(transactions)
            
        return transactions
