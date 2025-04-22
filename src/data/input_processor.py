from pathlib import Path
import pandas as pd
from typing import List, Dict, Any
import logging

from ..models.transaction import Transaction

logger = logging.getLogger(__name__)

class TransactionProcessor:
    """
    Handles reading and processing transaction data from CSV and Excel files.
    Supports validation and conversion to Transaction objects.
    """
    
    # Required columns in the input file
    REQUIRED_COLUMNS = {
        'Transaction Date',
        'Post Date',
        'Description',
        'Type',
        'Amount'
    }
    
    # Optional columns that might be present
    OPTIONAL_COLUMNS = {
        'Category',
        'Memo'
    }
    
    def __init__(self):
        """Initialize the processor."""
        pass
    
    def read_file(self, file_path: str | Path) -> List[Transaction]:
        """
        Read transactions from a CSV or Excel file.
        
        Args:
            file_path: Path to the input file
            
        Returns:
            List of Transaction objects
            
        Raises:
            ValueError: If file format is unsupported or required columns are missing
            FileNotFoundError: If the file doesn't exist
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Determine file type and read accordingly
        if file_path.suffix.lower() == '.csv':
            df = pd.read_csv(file_path)
        elif file_path.suffix.lower() in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")
        
        # Validate columns
        self._validate_columns(df.columns)
        
        # Convert DataFrame rows to Transaction objects
        transactions = []
        for _, row in df.iterrows():
            try:
                transaction = Transaction.from_dict(row.to_dict())
                transactions.append(transaction)
            except Exception as e:
                logger.warning(f"Skipping invalid row due to error: {e}")
                continue
        
        logger.info(f"Successfully read {len(transactions)} transactions from {file_path}")
        return transactions
    
    def _validate_columns(self, columns: pd.Index) -> None:
        """
        Validate that all required columns are present in the input file.
        
        Args:
            columns: Column names from the input file
            
        Raises:
            ValueError: If any required columns are missing
        """
        columns_set = set(columns)
        missing_required = self.REQUIRED_COLUMNS - columns_set
        
        if missing_required:
            raise ValueError(
                f"Missing required columns: {', '.join(missing_required)}"
            )
        
        # Log warning for missing optional columns
        missing_optional = self.OPTIONAL_COLUMNS - columns_set
        if missing_optional:
            logger.warning(
                f"Missing optional columns: {', '.join(missing_optional)}"
            )
    
    @staticmethod
    def get_sample_format() -> Dict[str, Any]:
        """
        Returns a sample format dictionary showing required and optional columns.
        Useful for generating template files or documentation.
        """
        return {
            'required_columns': list(TransactionProcessor.REQUIRED_COLUMNS),
            'optional_columns': list(TransactionProcessor.OPTIONAL_COLUMNS),
            'sample_row': {
                'Transaction Date': '04/02/2025',
                'Post Date': '04/02/2025',
                'Description': 'Sample Transaction',
                'Category': 'Shopping',
                'Type': 'Sale',
                'Amount': -42.99,
                'Memo': 'Optional memo field'
            }
        }
