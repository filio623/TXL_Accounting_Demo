import pytest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import pandas as pd

from src.models.account import Account
from src.models.transaction import Transaction
from src.data.output_generator import OutputGenerator


@pytest.fixture
def transactions():
    """Create sample transactions for testing."""
    account = Account("1000", "Test Account")
    return [
        Transaction(
            transaction_date=datetime(2024, 4, 1),
            post_date=datetime(2024, 4, 1),
            description="Test Transaction 1",
            category="Test",
            type="Sale",
            amount=Decimal("10.00"),
            matched_account=account
        ),
        Transaction(
            transaction_date=datetime(2024, 4, 2),
            post_date=datetime(2024, 4, 2),
            description="Test Transaction 2",
            category="Test",
            type="Sale",
            amount=Decimal("20.00"),
            matched_account=account
        )
    ]


@pytest.fixture
def output_generator():
    """Create an OutputGenerator instance."""
    return OutputGenerator()


def test_transactions_to_dataframe(output_generator, transactions):
    """Test converting transactions to DataFrame."""
    df = output_generator._transactions_to_dataframe(transactions)
    
    # Check DataFrame shape
    assert len(df) == 2
    assert "Transaction Date" in df.columns
    assert "Post Date" in df.columns
    assert "Description" in df.columns
    assert "Category" in df.columns
    assert "Type" in df.columns
    assert "Amount" in df.columns
    assert "Account Number" in df.columns
    
    # Check data types
    assert pd.api.types.is_datetime64_any_dtype(df["Transaction Date"])
    assert pd.api.types.is_datetime64_any_dtype(df["Post Date"])
    assert pd.api.types.is_string_dtype(df["Description"])
    assert pd.api.types.is_string_dtype(df["Category"])
    assert pd.api.types.is_string_dtype(df["Type"])
    assert pd.api.types.is_numeric_dtype(df["Amount"])


def test_generate_csv_file(output_generator, transactions, tmp_path):
    """Test generating a CSV file."""
    output_path = tmp_path / "test_output.csv"
    
    # Generate the file
    output_generator.generate_file(transactions, output_path)
    
    # Check that file exists
    assert output_path.exists()
    
    # Read the file back and verify contents
    df = pd.read_csv(output_path)
    assert len(df) == 2
    assert df["Description"].iloc[0] == "Test Transaction 1"
    assert df["Description"].iloc[1] == "Test Transaction 2"


def test_generate_excel_file(output_generator, transactions, tmp_path):
    """Test generating an Excel file."""
    output_path = tmp_path / "test_output.xlsx"
    
    # Generate the file
    output_generator.generate_file(transactions, output_path)
    
    # Check that file exists
    assert output_path.exists()
    
    # Read the file back and verify contents
    df = pd.read_excel(output_path)
    assert len(df) == 2
    assert df["Description"].iloc[0] == "Test Transaction 1"
    assert df["Description"].iloc[1] == "Test Transaction 2"


def test_unsupported_file_format(output_generator, transactions, tmp_path):
    """Test handling of unsupported file formats."""
    output_path = tmp_path / "test_output.txt"
    
    # Attempt to generate file with unsupported format
    with pytest.raises(OSError, match="Failed to generate output file"):
        output_generator.generate_file(transactions, output_path)


def test_empty_transactions(output_generator, tmp_path):
    """Test handling of empty transaction list."""
    output_path = tmp_path / "test_output.csv"
    
    # Generate file with empty transaction list
    output_generator.generate_file([], output_path)
    
    # Check that file exists and is empty (except header)
    assert output_path.exists()
    df = pd.read_csv(output_path)
    assert len(df) == 0


def test_get_sample_output(output_generator):
    """Test getting sample output DataFrame."""
    df = output_generator.get_sample_output()
    
    # Check DataFrame structure
    assert len(df) > 0
    assert "Transaction Date" in df.columns
    assert "Post Date" in df.columns
    assert "Description" in df.columns
    assert "Category" in df.columns
    assert "Type" in df.columns
    assert "Amount" in df.columns
    assert "Account Number" in df.columns
    
    # Check data types
    assert pd.api.types.is_datetime64_any_dtype(df["Transaction Date"])
    assert pd.api.types.is_datetime64_any_dtype(df["Post Date"])
    assert pd.api.types.is_string_dtype(df["Description"])
    assert pd.api.types.is_string_dtype(df["Category"])
    assert pd.api.types.is_string_dtype(df["Type"])
    assert pd.api.types.is_numeric_dtype(df["Amount"]) 