import pytest
from datetime import datetime
from decimal import Decimal

from src.models.account import Account, ChartOfAccounts
from src.models.transaction import Transaction
from src.matching.rule_matcher import RuleMatcher
from src.persistence.mapping_store import MappingStore
from src.matching.confidence import calculate_rule_based_confidence


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


def test_rule_save_load(chart_of_accounts, tmp_path):
    """Test saving and loading rules using RuleStore."""
    # Use a temporary file path for the rule store
    rule_file = tmp_path / "test_rules.json"
    
    # Create first matcher instance
    matcher1 = RuleMatcher(chart_of_accounts, rule_store_path=rule_file)
    
    # Add a custom rule
    account_to_modify = chart_of_accounts.find_account("1100") # Child 1
    custom_pattern = "CUSTOM_RULE_XYZ"
    custom_confidence = 0.95
    
    # Verify the rule doesn't exist initially in the default rules
    assert not any(rule[0] == custom_pattern for rule in matcher1.rules[account_to_modify.number])
    
    matcher1.add_rule(account_to_modify, custom_pattern, custom_confidence)
    
    # Verify the rule was added to the current matcher
    assert any(rule[0] == custom_pattern and rule[1] == custom_confidence for rule in matcher1.rules[account_to_modify.number])

    # Save the rules
    matcher1.save_rules()
    
    # Ensure the file was created
    assert rule_file.exists()
    
    # Create a second matcher instance, loading from the same file
    matcher2 = RuleMatcher(chart_of_accounts, rule_store_path=rule_file)
    
    # Verify the custom rule was loaded correctly
    assert account_to_modify.number in matcher2.rules
    assert any(rule[0] == custom_pattern and rule[1] == custom_confidence for rule in matcher2.rules[account_to_modify.number])
    
    # Verify default rules are also present (unless overwritten by loaded rules)
    # In this case, default rules should still be there as we only added one.
    assert len(matcher2.rules[account_to_modify.number]) > 1
    # Check for one of the default rules specifically
    assert any(rule[0] == account_to_modify.name for rule in matcher2.rules[account_to_modify.number])


def test_match_with_direct_mapping(chart_of_accounts, tmp_path):
    """Test that a transaction initially matches using MappingStore if a mapping exists, 
       and confidence uses the mapping threshold if no rule overrides.
    """
    rule_file = tmp_path / "rules.json"
    mapping_file = tmp_path / "mappings.json"
    
    # Create a mapping
    description_to_map = "VENDOR ABC EXACT MATCH"
    target_account_number = "1100" # Child 1
    mappings = {description_to_map: target_account_number}
    
    # Save the mapping using MappingStore directly
    mapping_store = MappingStore(mapping_file)
    mapping_store.save(mappings)
    assert mapping_file.exists()
    
    # Initialize RuleMatcher - it should load the mapping
    # Use default mapping confidence threshold (0.95)
    matcher = RuleMatcher(chart_of_accounts, rule_store_path=rule_file, mapping_store_path=mapping_file)
    assert description_to_map in matcher.mappings
    
    # Create a transaction with the exact description
    # Ensure no default rule for Child 1 or Grandchild matches this description with > 0.95 confidence
    transaction = Transaction(
        transaction_date=datetime(2024, 4, 1),
        post_date=datetime(2024, 4, 1),
        description=description_to_map, # Matches mapping, not default rules
        category="Test",
        type="Sale",
        amount=Decimal("50.00")
    )
    
    # Match the transaction
    matcher.match_transaction(transaction)
    
    # Verify it matched the correct account via mapping
    assert transaction.is_matched
    assert transaction.matched_account is not None
    assert transaction.matched_account.number == target_account_number
    # Verify confidence is the mapping threshold, as no rule beat it
    assert transaction.match_confidence == pytest.approx(0.95)


def test_match_fallback_to_rules_when_no_mapping(chart_of_accounts, tmp_path):
    """Test that rule-based matching occurs when no mapping exists."""
    rule_file = tmp_path / "rules.json"
    mapping_file = tmp_path / "mappings.json"
    
    if mapping_file.exists():
        mapping_file.unlink()
        
    matcher = RuleMatcher(chart_of_accounts, rule_store_path=rule_file, mapping_store_path=mapping_file)
    assert not matcher.mappings
    
    transaction = Transaction(
        transaction_date=datetime(2024, 4, 1),
        post_date=datetime(2024, 4, 1),
        description="Payment for Child 1 services",
        category="Test",
        type="Sale",
        amount=Decimal("60.00")
    )
    
    target_account_number = "1100"
    target_account = chart_of_accounts.find_account(target_account_number)
    
    matcher.match_transaction(transaction)
    
    assert transaction.is_matched
    assert transaction.matched_account is not None
    assert transaction.matched_account.number == target_account_number
    # Confidence should be rule-based, compare against calculation
    expected_rule_confidence = calculate_rule_based_confidence(transaction, target_account, ("Child 1", 0.8))
    assert transaction.match_confidence == pytest.approx(expected_rule_confidence)
    # Verify it's below the mapping threshold used in the other test
    assert transaction.match_confidence < 0.95 


def test_rule_overrides_mapping(chart_of_accounts, tmp_path):
    """Test that a high-confidence rule can override a mapping."""
    rule_file = tmp_path / "rules.json"
    mapping_file = tmp_path / "mappings.json"

    mapped_description = "STAPLES STORE 123"
    mapped_account_num = "1100"  # Child 1 (e.g., general supplies mapping)
    rule_account_num = "1210"    # Grandchild (e.g., specific computer rule)
    rule_pattern = r"STAPLES.*COMPUTER"
    rule_confidence = 0.97 # Higher than default mapping threshold (0.95)

    # 1. Save the initial mapping
    mappings = {mapped_description: mapped_account_num}
    mapping_store = MappingStore(mapping_file)
    mapping_store.save(mappings)

    # 2. Initialize matcher (loads mapping, initializes default rules)
    matcher = RuleMatcher(chart_of_accounts, rule_store_path=rule_file, mapping_store_path=mapping_file)
    
    # 3. Add a high-confidence rule for the target account
    rule_account = chart_of_accounts.find_account(rule_account_num)
    matcher.add_rule(rule_account, rule_pattern, rule_confidence)
    # Optional: Save rules if needed, but not necessary for this test as matcher has it in memory
    # matcher.save_rules() 

    # 4. Create a transaction that matches BOTH the mapping description AND the specific rule
    transaction = Transaction(
        transaction_date=datetime(2024, 4, 1),
        post_date=datetime(2024, 4, 1),
        description="STAPLES STORE 123 PURCHASE OF COMPUTER", # Matches mapping AND rule
        category="Office Equipment",
        type="Sale",
        amount=Decimal("-1200.00")
    )

    # 5. Match the transaction
    matcher.match_transaction(transaction)

    # 6. Verify the RULE match won
    assert transaction.is_matched
    assert transaction.matched_account is not None
    # Check it matched the account targeted by the rule, NOT the mapping
    assert transaction.matched_account.number == rule_account_num 
    # Check the confidence score matches the rule's confidence (or close to it)
    assert transaction.match_confidence == pytest.approx(rule_confidence)

# Add import for calculate_rule_based_confidence if not already present at top
# from src.matching.confidence import calculate_rule_based_confidence 