from typing import Tuple, Optional
import re

from ..models.transaction import Transaction
from ..models.account import Account

def calculate_rule_based_confidence(
    transaction: Transaction,
    account: Account,
    matched_rule: Optional[Tuple[str, float]] = None
) -> float:
    """
    Calculate confidence score based on the rule that matched.

    Args:
        transaction: The transaction being matched.
        account: The potential matching account.
        matched_rule: The specific rule (pattern, base_confidence) that matched, if any.

    Returns:
        Confidence score (0.0 to 1.0).
    """
    if not matched_rule:
        return 0.0

    pattern, base_confidence = matched_rule

    # Default confidence based on the rule itself
    confidence = base_confidence

    # Potential adjustments (example: slightly boost exact name/number matches)
    # Check if pattern matches account name exactly (case-insensitive)
    if pattern.lower() == account.name.lower() and re.fullmatch(re.escape(pattern), transaction.description, re.IGNORECASE):
         # Boost if the *entire* description matches the account name exactly
         confidence = min(1.0, base_confidence + 0.1)
    # Check if pattern matches account number exactly
    elif pattern == account.number and re.search(re.escape(pattern), transaction.description):
         # Boost if the account number is found
         confidence = min(1.0, base_confidence + 0.05)


    # Add more complex logic later (e.g., based on amount, type, category)

    return max(0.0, min(1.0, confidence)) # Ensure score is between 0 and 1
