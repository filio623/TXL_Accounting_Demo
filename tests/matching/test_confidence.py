import pytest
from decimal import Decimal
from datetime import datetime

from src.models.transaction import Transaction
from src.models.account import Account
from src.matching.confidence import calculate_rule_based_confidence

@pytest.fixture
def sample_account() -> Account:
    """Provides a sample Account for testing."""
    return Account(number="6000", name="Office Supplies")

@pytest.fixture
def sample_transaction() -> Transaction:
    """Provides a sample Transaction for testing."""
    return Transaction(
        transaction_date=datetime(2024, 1, 15),
        post_date=datetime(2024, 1, 16),
        description="STAPLES STORE 1234",
        category="Business",
        type="Sale",
        amount=Decimal("-55.25")
    )

def test_no_matched_rule(sample_transaction, sample_account):
    """Test confidence score when no rule matches."""
    assert calculate_rule_based_confidence(sample_transaction, sample_account, None) == 0.0

def test_basic_rule_match(sample_transaction, sample_account):
    """Test confidence score with a basic pattern match."""
    matched_rule = ("STAPLES", 0.7)
    confidence = calculate_rule_based_confidence(sample_transaction, sample_account, matched_rule)
    assert 0.69 < confidence < 0.71 # Should be close to base confidence

def test_exact_name_full_match(sample_account):
    """Test confidence boost for exact name match on full description."""
    transaction = Transaction(
        transaction_date=datetime(2024, 1, 15),
        post_date=datetime(2024, 1, 16),
        description="Office Supplies", # Exact match
        category="Business",
        type="Sale",
        amount=Decimal("-55.25")
    )
    matched_rule = ("Office Supplies", 0.8) # Rule pattern is the account name
    confidence = calculate_rule_based_confidence(transaction, sample_account, matched_rule)
    # Expect base_confidence + 0.1 boost
    assert 0.89 < confidence < 0.91

def test_exact_name_partial_match(sample_account):
    """Test no boost if name rule matches but not full description."""
    transaction = Transaction(
        transaction_date=datetime(2024, 1, 15),
        post_date=datetime(2024, 1, 16),
        description="Purchase of Office Supplies", # Partial match
        category="Business",
        type="Sale",
        amount=Decimal("-55.25")
    )
    matched_rule = ("Office Supplies", 0.8)
    confidence = calculate_rule_based_confidence(transaction, sample_account, matched_rule)
    # Expect only base_confidence (no boost for partial description match)
    assert 0.79 < confidence < 0.81

def test_account_number_match(sample_account):
    """Test confidence boost for account number match."""
    transaction = Transaction(
        transaction_date=datetime(2024, 1, 15),
        post_date=datetime(2024, 1, 16),
        description="Invoice #6000 Payment", # Contains account number
        category="Business",
        type="Sale",
        amount=Decimal("-55.25")
    )
    matched_rule = ("6000", 0.9) # Rule pattern is the account number
    confidence = calculate_rule_based_confidence(transaction, sample_account, matched_rule)
    # Expect base_confidence + 0.05 boost
    assert 0.94 < confidence < 0.96

def test_confidence_limits():
    """Test that confidence score remains within 0.0 and 1.0."""
    account = Account(number="1000", name="Test")
    transaction = Transaction(
        transaction_date=datetime(2024, 1, 15),
        post_date=datetime(2024, 1, 16),
        description="Test",
        category="Test",
        type="Sale",
        amount=Decimal("-10.00")
    )
    # Test high base confidence with boost
    high_rule = ("Test", 0.95)
    confidence_high = calculate_rule_based_confidence(transaction, account, high_rule)
    assert confidence_high == 1.0

    # Test low base confidence (should remain low)
    low_rule = ("SomethingElse", 0.1)
    confidence_low = calculate_rule_based_confidence(transaction, account, low_rule)
    assert 0.09 < confidence_low < 0.11 