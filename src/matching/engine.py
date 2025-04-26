import logging
from typing import List, Optional, Type

# Import base Matcher class
from .matcher import Matcher
# Import specific matcher types
# These imports are needed for type hinting if used directly,
# but the engine primarily works with the base Matcher type.
# from .rule_matcher import RuleMatcher 
# from .llm_matcher import LLMMatcher

from ..models.transaction import Transaction
from ..models.account import ChartOfAccounts

logger = logging.getLogger(__name__)

class MatchingEngine:
    """
    Coordinates the transaction matching process using primary and secondary matchers.

    This engine manages a sequence of matching strategies, typically starting
    with a high-precision matcher (like rule-based) and optionally falling back
    to a broader matcher (like an LLM) for transactions that remain unmatched
    or have low confidence after the primary pass.
    """
    
    def __init__(self, chart_of_accounts: ChartOfAccounts):
        """
        Initializes the matching engine.
        
        Args:
            chart_of_accounts: The chart of accounts instance used by the matchers.
        """
        self.chart_of_accounts: ChartOfAccounts = chart_of_accounts
        self.primary_matcher: Optional[Matcher] = None
        self.secondary_matcher: Optional[Matcher] = None 
        self._matcher_types: List[str] = [] # For logging which matchers are active

    def add_matcher(self, matcher: Matcher) -> None:
        """
        Adds a matcher instance to the engine's processing sequence.
        
        The first matcher added becomes the primary matcher.
        The second matcher added becomes the secondary matcher.
        Currently, only two matchers are supported.
        
        Args:
            matcher: The matcher instance (e.g., RuleMatcher, LLMMatcher) to add.
        """
        matcher_type_name = type(matcher).__name__
        if self.primary_matcher is None:
            self.primary_matcher = matcher
            self._matcher_types.append(f"Primary: {matcher_type_name}")
            logger.info(f"Registered Primary Matcher: {matcher_type_name}")
        elif self.secondary_matcher is None:
            self.secondary_matcher = matcher
            self._matcher_types.append(f"Secondary: {matcher_type_name}")
            logger.info(f"Registered Secondary Matcher: {matcher_type_name}")
        else:
            logger.warning(f"MatchingEngine currently supports only primary and secondary matchers. "
                           f"Ignoring additional matcher: {matcher_type_name}")

    def process_transactions(
        self,
        transactions: List[Transaction],
        secondary_confidence_threshold: float = 0.80
    ) -> List[Transaction]:
        """
        Processes a list of transactions through the configured matching sequence.
        
        Pass 1: Runs the primary matcher on all transactions.
        Pass 2 (Optional): Runs the secondary matcher on transactions where the primary 
                          match resulted in a confidence score below the specified threshold 
                          or if the transaction remained unmatched.
        
        Args:
            transactions: The list of Transaction objects to process.
            secondary_confidence_threshold: The confidence score (0.0-1.0) threshold. 
                                             Transactions with confidence below this after 
                                             Pass 1 will be processed by the secondary matcher.
                                             
        Returns:
            The same list of Transaction objects, updated with match results 
            (matched_account, match_confidence) where applicable.
            
        Raises:
            RuntimeError: If no primary matcher has been added to the engine.
        """
        if not self.primary_matcher:
            logger.error("Cannot process transactions: No primary matcher has been registered.")
            raise RuntimeError("No primary matcher registered with the engine")
        
        active_matchers_str = ", ".join(self._matcher_types)
        logger.info(f"Starting transaction processing for {len(transactions)} transactions using matchers: {active_matchers_str}")

        # --- Pass 1: Primary Matcher --- 
        primary_matcher_name = type(self.primary_matcher).__name__
        logger.info(f"Running Pass 1: Primary Matcher ({primary_matcher_name})...")
        try:
            # Process all transactions with the primary matcher
            self.primary_matcher.process_transactions(transactions)
            logger.info("Pass 1 complete.")
        except Exception as e:
            logger.error(f"Error during Primary Matcher ({primary_matcher_name}) execution: {e}", exc_info=True)
            # Decide whether to continue to Pass 2 or re-raise depending on desired robustness
            # For now, we log the error and continue if possible

        # --- Pass 2: Secondary Matcher (Conditional) --- 
        if self.secondary_matcher:
            secondary_matcher_name = type(self.secondary_matcher).__name__
            logger.info(f"Running Pass 2: Secondary Matcher ({secondary_matcher_name}) for transactions below {secondary_confidence_threshold:.0%} confidence...")
            
            # Identify transactions needing the second pass
            transactions_for_secondary_pass = [
                t for t in transactions 
                if not t.is_matched or t.match_confidence < secondary_confidence_threshold
            ]
            
            count = len(transactions_for_secondary_pass)
            if count > 0:
                 logger.info(f"Applying secondary matcher to {count} transactions.")
                 try:
                     # Process only the subset with the secondary matcher
                     self.secondary_matcher.process_transactions(transactions_for_secondary_pass)
                     logger.info("Pass 2 complete.")
                 except Exception as e:
                    logger.error(f"Error during Secondary Matcher ({secondary_matcher_name}) execution: {e}", exc_info=True)
                    # Log error and continue, as primary matches might still be valid
            else:
                logger.info("Pass 2: No transactions required secondary matching.")
        else:
            logger.info("Pass 2: No secondary matcher configured. Skipping.")

        logger.info(f"Transaction processing finished for {len(transactions)} transactions.")
        return transactions 