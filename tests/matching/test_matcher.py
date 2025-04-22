import pytest
from datetime import datetime
from decimal import Decimal

from src.models.account import Account, ChartOfAccounts
from src.models.transaction import Transaction
from src.matching.matcher import Matcher


class TestMatcher(Matcher):
    """Concrete implementation of Matcher for testing."""
    
    def match_transaction(self, transaction: Transaction) -> None:
        """Simple test implementation that matches based on description length."""
        for account in self.chart_of_accounts.get_leaf_accounts():
            if len(transaction.description) > 10:  # Arbitrary test logic
                transaction.add_match(account, 0.8)
                break
    
    def get_match_confidence(self, transaction: Transaction, account: Account) -> float:
        """Simple test implementation that returns fixed confidence."""
        return 0.8 if len(transaction.description) > 10 else 0.0


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
            description="Short desc",
            category="Test",
            type="Sale",
            amount=Decimal("10.00")
        ),
        Transaction(
            transaction_date=datetime(2024, 4, 2),
            post_date=datetime(2024, 4, 2),
            description="This is a longer description that should match",
            category="Test",
            type="Sale",
            amount=Decimal("20.00")
        )
    ]


def test_matcher_initialization(chart_of_accounts):
    """Test that the matcher initializes correctly."""
    matcher = TestMatcher(chart_of_accounts)
    assert matcher.chart_of_accounts == chart_of_accounts


def test_process_transactions(chart_of_accounts, transactions):
    """Test processing multiple transactions."""
    matcher = TestMatcher(chart_of_accounts)
    processed = matcher.process_transactions(transactions)
    
    assert len(processed) == 2
    assert processed[0].matched_account is None  # Short description, no match
    assert processed[1].matched_account is not None  # Long description, should match


def test_validate_match(chart_of_accounts, transactions):
    """Test the basic match validation."""
    matcher = TestMatcher(chart_of_accounts)
    
    # Test with leaf account (should pass)
    leaf_account = chart_of_accounts.get_leaf_accounts()[0]
    assert matcher._validate_match(transactions[0], leaf_account) is True
    
    # Test with non-leaf account (should fail)
    non_leaf = chart_of_accounts.accounts[0]
    assert matcher._validate_match(transactions[0], non_leaf) is False


def test_get_match_confidence(chart_of_accounts, transactions):
    """Test confidence score calculation."""
    matcher = TestMatcher(chart_of_accounts)
    account = chart_of_accounts.get_leaf_accounts()[0]
    
    # Test with short description (should return 0.0)
    confidence = matcher.get_match_confidence(transactions[0], account)
    assert confidence == 0.0
    
    # Test with long description (should return 0.8)
    confidence = matcher.get_match_confidence(transactions[1], account)
    assert confidence == 0.8 