import pytest
from datetime import datetime
from decimal import Decimal
from src.models.transaction import Transaction
from src.models.account import Account

@pytest.fixture
def sample_transaction_data():
    """Sample transaction data for testing."""
    return {
        'Transaction Date': '04/02/2025',
        'Post Date': '04/02/2025',
        'Description': 'OPENAI',
        'Category': 'Software',
        'Type': 'Sale',
        'Amount': -29.99,
        'Memo': 'Monthly subscription'
    }

@pytest.fixture
def sample_account():
    """Sample account for testing."""
    return Account(
        number="7410",
        name="Software & Subscriptions"
    )

def test_transaction_creation(sample_transaction_data):
    """Test creating a transaction from dictionary data."""
    transaction = Transaction.from_dict(sample_transaction_data)
    
    assert transaction.transaction_date == datetime(2025, 4, 2)
    assert transaction.post_date == datetime(2025, 4, 2)
    assert transaction.description == "OPENAI"
    assert transaction.category == "Software"
    assert transaction.type == "Sale"
    assert transaction.amount == Decimal("-29.99")
    assert transaction.memo == "Monthly subscription"
    
    # Check default values
    assert transaction.matched_account is None
    assert transaction.match_confidence == 0.0
    assert transaction.alternative_matches == []

def test_transaction_to_dict(sample_transaction_data):
    """Test converting transaction back to dictionary format."""
    transaction = Transaction.from_dict(sample_transaction_data)
    dict_format = transaction.to_dict()
    
    # Check original fields
    assert dict_format['Transaction Date'] == '04/02/2025'
    assert dict_format['Post Date'] == '04/02/2025'
    assert dict_format['Description'] == 'OPENAI'
    assert dict_format['Category'] == 'Software'
    assert dict_format['Type'] == 'Sale'
    assert dict_format['Amount'] == '-29.99'
    assert dict_format['Memo'] == 'Monthly subscription'
    
    # No matching info should be present
    assert 'Account Number' not in dict_format
    assert 'Match Confidence' not in dict_format

def test_transaction_matching(sample_transaction_data, sample_account):
    """Test adding matches to a transaction."""
    transaction = Transaction.from_dict(sample_transaction_data)
    
    # Add primary match
    transaction.add_match(sample_account, 0.95)
    assert transaction.matched_account == sample_account
    assert transaction.match_confidence == 0.95
    assert len(transaction.alternative_matches) == 0
    
    # Add lower confidence match
    alt_account = Account(number="6510", name="Dues & Subscriptions")
    transaction.add_match(alt_account, 0.85)
    assert transaction.matched_account == sample_account  # Should keep higher confidence match
    assert len(transaction.alternative_matches) == 1
    assert transaction.alternative_matches[0] == (alt_account, 0.85)
    
    # Add higher confidence match
    better_account = Account(number="7411", name="Cloud Services")
    transaction.add_match(better_account, 0.98)
    assert transaction.matched_account == better_account
    assert transaction.match_confidence == 0.98
    assert len(transaction.alternative_matches) == 2
    assert transaction.alternative_matches[0] == (sample_account, 0.95)

def test_transaction_needs_review(sample_transaction_data, sample_account):
    """Test conditions that require manual review."""
    transaction = Transaction.from_dict(sample_transaction_data)
    
    # Unmatched transaction needs review
    assert transaction.needs_review
    
    # Low confidence match needs review
    transaction.add_match(sample_account, 0.65)
    assert transaction.needs_review
    
    # High confidence match doesn't need review
    transaction.add_match(sample_account, 0.85)
    assert not transaction.needs_review
    
    # Multiple similar confidence matches need review
    alt_account = Account(number="6510", name="Dues & Subscriptions")
    transaction.add_match(alt_account, 0.82)  # Within 10% of top match
    assert transaction.needs_review

def test_transaction_optional_fields():
    """Test handling of missing optional fields."""
    minimal_data = {
        'Transaction Date': '04/02/2025',
        'Post Date': '04/02/2025',
        'Description': 'OPENAI',
        'Type': 'Sale',
        'Amount': -29.99
    }
    
    transaction = Transaction.from_dict(minimal_data)
    assert transaction.category is None
    assert transaction.memo is None
    
    dict_format = transaction.to_dict()
    assert dict_format['Category'] == ''
    assert dict_format['Memo'] == '' 