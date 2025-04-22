import pytest
from src.models.account import Account, ChartOfAccounts
from pathlib import Path
import json

# Sample chart of accounts data for testing
SAMPLE_CHART = {
    "chartOfAccounts": [
        {
            "number": "6000",
            "name": "EXPENSES",
            "children": [
                {
                    "number": "6010",
                    "name": "Advertising & Marketing"
                },
                {
                    "number": "6510",
                    "name": "Dues & Subscriptions",
                    "children": [
                        {
                            "number": "6511",
                            "name": "Software Subscriptions"
                        }
                    ]
                }
            ]
        }
    ]
}

@pytest.fixture
def sample_chart_file(tmp_path):
    """Create a temporary chart of accounts file for testing."""
    file_path = tmp_path / "test_chart.json"
    with open(file_path, 'w') as f:
        json.dump(SAMPLE_CHART, f)
    return file_path

def test_account_creation():
    """Test basic account creation and properties."""
    account = Account(number="1000", name="Test Account")
    assert account.number == "1000"
    assert account.name == "Test Account"
    assert account.children == []
    assert account.parent is None
    assert account.is_leaf

def test_account_hierarchy():
    """Test parent-child relationships."""
    parent = Account(number="6000", name="EXPENSES")
    child = Account(number="6010", name="Advertising")
    grandchild = Account(number="6011", name="Online Ads")
    
    parent.add_child(child)
    child.add_child(grandchild)
    
    assert child.parent == parent
    assert grandchild.parent == child
    assert len(parent.children) == 1
    assert len(child.children) == 1
    assert not parent.is_leaf
    assert not child.is_leaf
    assert grandchild.is_leaf

def test_account_full_name():
    """Test full name generation with hierarchy."""
    parent = Account(number="6000", name="EXPENSES")
    child = Account(number="6010", name="Advertising")
    grandchild = Account(number="6011", name="Online Ads")
    
    parent.add_child(child)
    child.add_child(grandchild)
    
    assert parent.full_name == "EXPENSES"
    assert child.full_name == "EXPENSES > Advertising"
    assert grandchild.full_name == "EXPENSES > Advertising > Online Ads"

def test_find_by_number():
    """Test finding accounts by number."""
    parent = Account(number="6000", name="EXPENSES")
    child = Account(number="6010", name="Advertising")
    parent.add_child(child)
    
    assert parent.find_by_number("6000") == parent
    assert parent.find_by_number("6010") == child
    assert parent.find_by_number("9999") is None

def test_chart_of_accounts_loading(sample_chart_file):
    """Test loading chart of accounts from file."""
    chart = ChartOfAccounts.from_json_file(sample_chart_file)
    
    # Test basic structure
    assert len(chart.accounts) == 1
    root = chart.accounts[0]
    assert root.number == "6000"
    assert root.name == "EXPENSES"
    assert len(root.children) == 2
    
    # Test finding accounts
    assert chart.find_account("6000") is not None
    assert chart.find_account("6010") is not None
    assert chart.find_account("6511") is not None
    assert chart.find_account("9999") is None

def test_get_leaf_accounts(sample_chart_file):
    """Test getting all leaf accounts."""
    chart = ChartOfAccounts.from_json_file(sample_chart_file)
    leaves = chart.get_leaf_accounts()
    
    # Should find Advertising & Marketing and Software Subscriptions
    assert len(leaves) == 2
    leaf_numbers = {account.number for account in leaves}
    assert leaf_numbers == {"6010", "6511"}

def test_to_dict():
    """Test converting accounts back to dictionary format."""
    parent = Account(number="6000", name="EXPENSES")
    child = Account(number="6010", name="Advertising")
    parent.add_child(child)
    
    dict_format = parent.to_dict()
    assert dict_format["number"] == "6000"
    assert dict_format["name"] == "EXPENSES"
    assert len(dict_format["children"]) == 1
    assert dict_format["children"][0]["number"] == "6010"

def test_chart_to_dict(sample_chart_file):
    """Test converting entire chart to dictionary format."""
    chart = ChartOfAccounts.from_json_file(sample_chart_file)
    dict_format = chart.to_dict()
    
    assert dict_format == SAMPLE_CHART 