import pytest
import pandas as pd
from pathlib import Path
from src.data.input_processor import TransactionProcessor
from src.models.transaction import Transaction

@pytest.fixture
def sample_csv_data(tmp_path):
    """Create a sample CSV file for testing."""
    csv_content = """Transaction Date,Post Date,Description,Category,Type,Amount,Memo
04/02/2025,04/02/2025,OPENAI,Software,Sale,-29.99,Monthly subscription
03/28/2025,03/30/2025,WCI*PROGRESSIVEWASTEFL,Bills & Utilities,Sale,-61.50,
03/24/2025,03/25/2025,ALIEXPRESS,Shopping,Sale,-12.97,"""
    
    file_path = tmp_path / "transactions.csv"
    with open(file_path, 'w') as f:
        f.write(csv_content)
    return file_path

@pytest.fixture
def sample_excel_data(tmp_path):
    """Create a sample Excel file for testing."""
    df = pd.DataFrame([
        {
            'Transaction Date': '04/02/2025',
            'Post Date': '04/02/2025',
            'Description': 'OPENAI',
            'Category': 'Software',
            'Type': 'Sale',
            'Amount': -29.99,
            'Memo': 'Monthly subscription'
        }
    ])
    
    file_path = tmp_path / "transactions.xlsx"
    df.to_excel(file_path, index=False)
    return file_path

def test_read_csv_file(sample_csv_data):
    """Test reading transactions from CSV file."""
    processor = TransactionProcessor()
    transactions = processor.read_file(sample_csv_data)
    
    assert len(transactions) == 3
    assert all(isinstance(t, Transaction) for t in transactions)
    
    # Check first transaction
    t = transactions[0]
    assert t.description == "OPENAI"
    assert t.category == "Software"
    assert str(t.amount) == "-29.99"

def test_read_excel_file(sample_excel_data):
    """Test reading transactions from Excel file."""
    processor = TransactionProcessor()
    transactions = processor.read_file(sample_excel_data)
    
    assert len(transactions) == 1
    t = transactions[0]
    assert t.description == "OPENAI"
    assert t.category == "Software"
    assert str(t.amount) == "-29.99"

def test_invalid_file_format(tmp_path):
    """Test handling of invalid file formats."""
    # Create a text file with some content
    file_path = tmp_path / "invalid.txt"
    with open(file_path, 'w') as f:
        f.write("This is not a valid transaction file")
    
    processor = TransactionProcessor()
    with pytest.raises(ValueError) as exc_info:
        processor.read_file(file_path)
    assert "Unsupported file format" in str(exc_info.value)

def test_missing_required_columns(tmp_path):
    """Test handling of missing required columns."""
    # Create CSV with missing required column
    csv_content = """Post Date,Description,Type,Amount
04/02/2025,OPENAI,Sale,-29.99"""
    
    file_path = tmp_path / "invalid.csv"
    with open(file_path, 'w') as f:
        f.write(csv_content)
    
    processor = TransactionProcessor()
    with pytest.raises(ValueError) as exc_info:
        processor.read_file(file_path)
    assert "Missing required columns" in str(exc_info.value)

def test_sample_format():
    """Test the sample format helper method."""
    format_info = TransactionProcessor.get_sample_format()
    
    assert 'required_columns' in format_info
    assert 'optional_columns' in format_info
    assert 'sample_row' in format_info
    
    # Check required columns
    assert 'Transaction Date' in format_info['required_columns']
    assert 'Amount' in format_info['required_columns']
    
    # Check optional columns
    assert 'Category' in format_info['optional_columns']
    assert 'Memo' in format_info['optional_columns'] 