from pathlib import Path
import pandas as pd
import logging
from typing import List
from decimal import Decimal

from ..models.transaction import Transaction

logger = logging.getLogger(__name__)

class OutputGenerator:
    """
    Handles generating output files from processed transactions.
    Supports both CSV and Excel output formats.
    """
    
    def __init__(self):
        """Initialize the output generator."""
        pass
    
    def generate_file(self, transactions: List[Transaction], output_path: str | Path) -> None:
        """
        Generate an output file from the processed transactions.
        
        Args:
            transactions: List of processed transactions with matches
            output_path: Path where the output file should be saved
            
        Raises:
            ValueError: If the output format is not supported
            IOError: If there are issues writing the file
        """
        output_path = Path(output_path)
        
        # Convert transactions to DataFrame
        df = self._transactions_to_dataframe(transactions)
        
        # Determine output format and generate file
        try:
            if output_path.suffix.lower() == '.csv':
                df.to_csv(output_path, index=False)
            elif output_path.suffix.lower() in ['.xlsx', '.xls']:
                df.to_excel(output_path, index=False)
            else:
                raise ValueError(f"Unsupported output format: {output_path.suffix}")
                
            logger.info(f"Successfully generated output file: {output_path}")
            
        except Exception as e:
            logger.error(f"Error generating output file: {e}")
            raise IOError(f"Failed to generate output file: {e}")
    
    def _transactions_to_dataframe(self, transactions: List[Transaction]) -> pd.DataFrame:
        """
        Convert a list of transactions to a pandas DataFrame.
        
        Args:
            transactions: List of transactions to convert
            
        Returns:
            pd.DataFrame: DataFrame containing all transaction data
        """
        if not transactions:
            # Return empty DataFrame with correct columns
            return pd.DataFrame(columns=[
                "Transaction Date", "Post Date", "Description", "Category", "Type",
                "Amount", "Memo", "Account Number", "Account Name", "Account Full Path",
                "Match Confidence", "Alternative Matches"
            ])

        data = []
        for transaction in transactions:
            row = {
                "Transaction Date": pd.to_datetime(transaction.transaction_date),
                "Post Date": pd.to_datetime(transaction.post_date),
                "Description": transaction.description,
                "Category": transaction.category,
                "Type": transaction.type,
                "Amount": float(transaction.amount),  # Convert Decimal to float
                "Memo": transaction.memo or "",
                "Account Number": transaction.matched_account.number if transaction.matched_account else "",
                "Account Name": transaction.matched_account.name if transaction.matched_account else "",
                "Account Full Path": transaction.matched_account.full_name if transaction.matched_account else "",
                "Match Confidence": f"{transaction.match_confidence:.2%}",
                "Alternative Matches": ", ".join(
                    f"{match.number} - {match.name} ({confidence:.2%})"
                    for match, confidence in transaction.alternative_matches
                )
            }
            data.append(row)

        df = pd.DataFrame(data)
        
        # Ensure correct data types
        df["Transaction Date"] = pd.to_datetime(df["Transaction Date"])
        df["Post Date"] = pd.to_datetime(df["Post Date"])
        df["Amount"] = pd.to_numeric(df["Amount"])

        return df
    
    def get_sample_output(self) -> pd.DataFrame:
        """
        Returns a sample DataFrame showing the expected output format.
        Useful for documentation and testing.
        
        Returns:
            pd.DataFrame: Sample output DataFrame
        """
        # Create a sample transaction
        transaction = Transaction(
            transaction_date=pd.to_datetime("2024-04-02"),
            post_date=pd.to_datetime("2024-04-02"),
            description="Sample Transaction",
            category="Sample",
            type="Sale",
            amount=Decimal("100.00")
        )
        return self._transactions_to_dataframe([transaction])
