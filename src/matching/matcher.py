from abc import ABC, abstractmethod
from typing import List, Optional, Type
import logging

from ..models.transaction import Transaction
from ..models.account import Account, ChartOfAccounts
# Import specific matcher types for isinstance checks
from .rule_matcher import RuleMatcher 
# Import LLMMatcher, handle potential circularity if needed or keep import local? For now, import.
from .llm_matcher import LLMMatcher

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
        for transaction in transactions:
            # Only attempt match if not already matched by a previous step in engine
            # (This might change based on engine strategy)
            if not transaction.is_matched:
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
    Supports a primary matcher (e.g., rules) and an optional secondary matcher (e.g., LLM).
    """
    
    def __init__(self, chart_of_accounts: ChartOfAccounts):
        """
        Initialize the matching engine with a chart of accounts.
        
        Args:
            chart_of_accounts: The chart of accounts to match against
        """
        self.chart_of_accounts = chart_of_accounts
        # Separate matchers for clarity in the process method
        self.primary_matcher: Optional[Matcher] = None
        self.secondary_matcher: Optional[Matcher] = None 
        # Store the added matcher types for logging/debugging
        self._matcher_types: List[str] = []

    def add_matcher(self, matcher: Matcher) -> None:
        """
        Add a matcher to the engine. Assumes the first added is primary,
        the second (if any) is secondary.
        
        Args:
            matcher: The matcher instance to add.
        """
        matcher_type_name = type(matcher).__name__
        if self.primary_matcher is None:
            self.primary_matcher = matcher
            self._matcher_types.append(f"Primary: {matcher_type_name}")
            logger.info(f"Added Primary Matcher: {matcher_type_name}")
        elif self.secondary_matcher is None:
            self.secondary_matcher = matcher
            self._matcher_types.append(f"Secondary: {matcher_type_name}")
            logger.info(f"Added Secondary Matcher: {matcher_type_name}")
        else:
            logger.warning(f"MatchingEngine currently only supports primary and secondary matchers. Ignoring additional matcher: {matcher_type_name}")

    def process_transactions(self, 
                             transactions: List[Transaction], 
                             secondary_confidence_threshold: float = 0.80
                            ) -> List[Transaction]:
        """
        Process transactions using a two-pass strategy if a secondary matcher is present.
        1. Runs the primary matcher on all transactions.
        2. Runs the secondary matcher on transactions below the confidence threshold.
        
        Args:
            transactions: List of transactions to process.
            secondary_confidence_threshold: Confidence threshold below which the secondary
                                             matcher is invoked.
                                             
        Returns:
            List[Transaction]: The processed transactions with matches.
        """
        if not self.primary_matcher:
            raise RuntimeError("No primary matcher registered with the engine")
        
        logger.info(f"Starting transaction processing using matchers: {', '.join(self._matcher_types)}")

        # --- Pass 1: Primary Matcher --- 
        logger.info(f"Running Pass 1: Primary Matcher ({type(self.primary_matcher).__name__})...")
        # Process all transactions with the primary matcher
        # Modify primary matcher's process_transactions to only process if not already matched (optional)
        self.primary_matcher.process_transactions(transactions)
        logger.info("Pass 1 complete.")

        # --- Pass 2: Secondary Matcher (Conditional) --- 
        if self.secondary_matcher:
            logger.info(f"Running Pass 2: Secondary Matcher ({type(self.secondary_matcher).__name__}) for transactions below {secondary_confidence_threshold:.0%} confidence...")
            # Identify transactions needing the second pass
            transactions_for_secondary_pass = [
                t for t in transactions 
                if not t.is_matched or t.match_confidence < secondary_confidence_threshold
            ]
            
            count = len(transactions_for_secondary_pass)
            if count > 0:
                 logger.info(f"Applying secondary matcher to {count} transactions.")
                 # Process only the subset with the secondary matcher
                 self.secondary_matcher.process_transactions(transactions_for_secondary_pass)
                 logger.info("Pass 2 complete.")
            else:
                logger.info("No transactions required secondary matching.")
        else:
            logger.info("No secondary matcher configured. Skipping Pass 2.")

        return transactions
