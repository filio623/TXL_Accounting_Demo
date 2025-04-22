#!/usr/bin/env python3
"""
TXL Accounting Demo - Transaction Categorization System
Main orchestration script that coordinates the entire process.
"""

import argparse
import logging
from pathlib import Path
from typing import Optional

from src.models.account import ChartOfAccounts
from src.data.input_processor import TransactionProcessor
from src.matching.matcher import MatchingEngine
from src.matching.rule_matcher import RuleMatcher
from src.data.output_generator import OutputGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Process transaction data and match to chart of accounts.'
    )
    parser.add_argument(
        'input_file',
        type=str,
        help='Path to input CSV/Excel file containing transactions'
    )
    parser.add_argument(
        '--chart-of-accounts',
        type=str,
        default='config/chart_of_accounts.json',
        help='Path to chart of accounts JSON file'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Path for output file. If not specified, will append "_categorized" to input filename'
    )
    return parser.parse_args()

def get_output_path(input_path: str, output_path: Optional[str] = None) -> Path:
    """Determine the output file path."""
    input_path = Path(input_path)
    if output_path:
        return Path(output_path)
    
    # Add '_categorized' before the file extension
    stem = input_path.stem + '_categorized'
    return input_path.with_name(stem + input_path.suffix)

def main():
    """Main execution function."""
    args = parse_arguments()
    
    # Load chart of accounts
    logger.info("Loading chart of accounts...")
    chart = ChartOfAccounts.from_json_file(args.chart_of_accounts)
    
    # Initialize components
    processor = TransactionProcessor()
    matcher = MatchingEngine(chart)
    output_gen = OutputGenerator()
    
    # Add rule-based matcher
    rule_matcher = RuleMatcher(chart)
    matcher.add_matcher(rule_matcher)
    
    # Process input file
    logger.info(f"Processing input file: {args.input_file}")
    transactions = processor.read_file(args.input_file)
    
    # Match transactions
    logger.info("Matching transactions to accounts...")
    matched_transactions = matcher.process_transactions(transactions)
    
    # Generate output
    output_path = get_output_path(args.input_file, args.output)
    logger.info(f"Generating output file: {output_path}")
    output_gen.generate_file(matched_transactions, output_path)
    
    logger.info("Processing complete!")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        exit(1) 