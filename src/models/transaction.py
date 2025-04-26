from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from decimal import Decimal
from enum import Enum, auto

from .account import Account

# Define Enum for match source
class MatchSource(Enum):
    MANUAL = auto()
    RULE = auto()
    MAPPING = auto() # If we distinguish mapping-only matches
    LLM = auto()
    UNKNOWN = auto()

@dataclass
class Transaction:
    """
    Represents a credit card transaction and its matched accounting categorization.
    """
    # Original transaction fields
    transaction_date: datetime
    post_date: datetime
    description: str
    category: Optional[str]
    type: str  # 'Sale', 'Payment', 'Return', etc.
    amount: Decimal
    memo: Optional[str] = None
    
    # Matched account information
    matched_account: Optional[Account] = None
    match_confidence: float = 0.0
    match_source: MatchSource = MatchSource.UNKNOWN
    alternative_matches: list[tuple[Account, float]] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict) -> Transaction:
        """Create a Transaction instance from a dictionary (e.g., CSV row)."""
        return cls(
            transaction_date=datetime.strptime(data['Transaction Date'], '%m/%d/%Y'),
            post_date=datetime.strptime(data['Post Date'], '%m/%d/%Y'),
            description=data['Description'],
            category=data.get('Category'),  # Using get() as it might be empty
            type=data['Type'],
            amount=Decimal(str(data['Amount'])),  # Convert to Decimal for precision
            memo=data.get('Memo')
        )
    
    def to_dict(self) -> dict:
        """Convert transaction to dictionary format for output."""
        base_dict = {
            'Transaction Date': self.transaction_date.strftime('%m/%d/%Y'),
            'Post Date': self.post_date.strftime('%m/%d/%Y'),
            'Description': self.description,
            'Category': self.category or '',
            'Type': self.type,
            'Amount': str(self.amount),
            'Memo': self.memo or '',
            'Match Source': self.match_source.name
        }
        
        # Add matched account information if available
        if self.matched_account:
            base_dict.update({
                'Account Number': self.matched_account.number,
                'Account Name': self.matched_account.name,
                'Account Full Path': self.matched_account.full_name,
                'Match Confidence': f"{self.match_confidence:.2%}"
            })
            
            # Add alternative matches if available
            if self.alternative_matches:
                alt_matches = []
                for account, confidence in self.alternative_matches:
                    alt_matches.append(
                        f"{account.number} - {account.name} ({confidence:.2%})"
                    )
                base_dict['Alternative Matches'] = '; '.join(alt_matches)
        
        return base_dict
    
    @property
    def is_matched(self) -> bool:
        """Check if the transaction has been matched to an account."""
        return self.matched_account is not None
    
    @property
    def needs_review(self) -> bool:
        """
        Determine if this transaction needs manual review.
        Currently returns True if:
        - Not matched to any account
        - Match confidence is below 70%
        - Has multiple high-confidence alternative matches
        """
        if not self.is_matched:
            return True
        
        if self.match_confidence < 0.7:
            return True
            
        # Check if there are alternative matches with similar confidence
        for _, confidence in self.alternative_matches:
            if confidence > self.match_confidence - 0.1:  # Within 10% of top match
                return True
                
        return False
    
    def add_match(self, account: Account, confidence: float, source: MatchSource = MatchSource.UNKNOWN) -> None:
        """
        Add or update the matched account, confidence score, and source.

        If the new match has higher confidence, it becomes the primary match
        and the old primary match (if any) moves to alternatives.
        Updates the match source regardless of confidence change.
        
        Args:
            account: The matched Account object.
            confidence: The confidence score (0.0-1.0) of the match.
            source: The source of the match (e.g., RULE, LLM).
        """
        if not self.matched_account or confidence > self.match_confidence:
            # If there was a previous match, add it to alternatives
            if self.matched_account:
                # Store previous match details before overwriting
                prev_match_details = (self.matched_account, self.match_confidence)
                # Don't add if it's the same account being re-matched with higher confidence
                if prev_match_details[0] != account:
                    self.alternative_matches.append(prev_match_details)
                    # Sort alternatives by confidence (highest first)
                    self.alternative_matches.sort(key=lambda x: x[1], reverse=True)
                    # Keep only top N alternatives (e.g., 3)
                    self.alternative_matches = self.alternative_matches[:3]
            
            # Update primary match details
            self.matched_account = account
            self.match_confidence = confidence
            self.match_source = source # Update source

        elif account != self.matched_account and confidence > 0.3:  # Only add different accounts as alternatives
            # Avoid adding duplicate alternatives
            is_already_alternative = any(alt[0] == account for alt in self.alternative_matches)
            if not is_already_alternative:
                self.alternative_matches.append((account, confidence))
                self.alternative_matches.sort(key=lambda x: x[1], reverse=True)
                self.alternative_matches = self.alternative_matches[:3]
        elif account == self.matched_account:
             # If the same account is suggested again (e.g., by LLM after a rule) 
             # but with lower/equal confidence, just update the source if it was UNKNOWN
             if self.match_source == MatchSource.UNKNOWN:
                 self.match_source = source
