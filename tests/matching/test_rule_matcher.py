import pytest
from datetime import datetime
from decimal import Decimal

from src.models.account import Account, ChartOfAccounts
from src.models.transaction import Transaction
from src.matching.rule_matcher import RuleMatcher


@pytest.fixture
def chart_of_accounts():
    """Create a sample chart of accounts for testing."""
    chart = ChartOfAccounts()
    
    # Create a simple hierarchy
    root = Account("1000", "Root")
    child1 = Account("1100", "Child 1")
    child2 = Account("1200", "Child 2")
    grandchild = Account("1210", "Grandchild")
    
    child2.add_child(grandchild)
    root.add_child(child1)
    root.add_child(child2)
    
    chart.accounts.append(root)
    return chart


@pytest.fixture
def transactions():
    """Create sample transactions for testing."""
    return [
        Transaction(
            transaction_date=datetime(2024, 4, 1),
            post_date=datetime(2024, 4, 1),
            description="Payment to Child 1",
            category="Test",
            type="Sale",
            amount=Decimal("10.00")
        ),
        Transaction(
            transaction_date=datetime(2024, 4, 2),
            post_date=datetime(2024, 4, 2),
            description="Payment to Grandchild",
            category="Test",
            type="Sale",
            amount=Decimal("20.00")
        ),
        Transaction(
            transaction_date=datetime(2024, 4, 3),
            post_date=datetime(2024, 4, 3),
            description="Unrelated transaction",
            category="Test",
            type="Sale",
            amount=Decimal("30.00")
        )
    ]


def test_rule_matcher_initialization(chart_of_accounts):
    """Test that the rule matcher initializes correctly with default rules."""
    matcher = RuleMatcher(chart_of_accounts)
    
    # Check that rules were created for each leaf account
    leaf_accounts = chart_of_accounts.get_leaf_accounts()
    assert len(matcher.rules) == len(leaf_accounts)
    
    # Check that each account has at least 2 rules (name and number)
    for account in leaf_accounts:
        assert account.number in matcher.rules
        assert len(matcher.rules[account.number]) >= 2


def test_match_transaction(chart_of_accounts, transactions):
    """Test matching transactions using rules."""
    matcher = RuleMatcher(chart_of_accounts)
    
    # Match each transaction
    for transaction in transactions:
        matcher.match_transaction(transaction)
    
    # First transaction should match "Child 1"
    assert transactions[0].matched_account is not None
    assert transactions[0].matched_account.name == "Child 1"
    assert transactions[0].match_confidence > 0
    
    # Second transaction should match "Grandchild"
    assert transactions[1].matched_account is not None
    assert transactions[1].matched_account.name == "Grandchild"
    assert transactions[1].match_confidence > 0
    
    # Third transaction should not match
    assert transactions[2].matched_account is None
    assert transactions[2].match_confidence == 0.0


def test_get_match_confidence(chart_of_accounts, transactions):
    """Test confidence score calculation for different matches."""
    matcher = RuleMatcher(chart_of_accounts)
    
    # Get leaf accounts
    child1 = chart_of_accounts.find_account("1100")
    grandchild = chart_of_accounts.find_account("1210")
    
    # Test exact name match (should have high confidence)
    confidence = matcher.get_match_confidence(transactions[0], child1)
    assert confidence > 0.7  # Should be high confidence
    
    # Test partial match (should have lower confidence)
    confidence = matcher.get_match_confidence(transactions[2], child1)
    assert confidence == 0.0  # Should not match at all


def test_add_rule(chart_of_accounts):
    """Test adding custom rules."""
    matcher = RuleMatcher(chart_of_accounts)
    account = chart_of_accounts.get_leaf_accounts()[0]
    
    # Add a custom rule
    matcher.add_rule(account, r"custom.*pattern", 0.9)
    
    # Check that the rule was added
    assert len(matcher.rules[account.number]) >= 3  # Should have at least 3 rules now
    
    # Test the new rule
    transaction = Transaction(
        transaction_date=datetime(2024, 4, 1),
        post_date=datetime(2024, 4, 1),
        description="This is a custom pattern match",
        category="Test",
        type="Sale",
        amount=Decimal("10.00")
    )
    
    confidence = matcher.get_match_confidence(transaction, account)
    assert confidence > 0  # Should match the new rule


def test_invalid_rule(chart_of_accounts):
    """Test adding an invalid rule pattern."""
    matcher = RuleMatcher(chart_of_accounts)
    account = chart_of_accounts.get_leaf_accounts()[0]
    
    # Try to add an invalid regex pattern
    matcher.add_rule(account, "[invalid", 0.9)
    
    # The invalid rule should not be added
    assert len(matcher.rules[account.number]) == 2  # Should still only have default rules 