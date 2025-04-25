#!/usr/bin/env python3
"""
TXL Accounting Demo - Transaction Categorization System
Main orchestration script that coordinates the entire process.
"""

import argparse
import logging
import os
from pathlib import Path
from typing import Optional

from src.models.account import ChartOfAccounts
from src.data.input_processor import TransactionProcessor
# Import MatchingEngine from its new location
from src.matching.engine import MatchingEngine 
from src.matching.rule_matcher import RuleMatcher
# Import LLMMatcher
from src.matching.llm_matcher import LLMMatcher 
from src.data.output_generator import OutputGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Process transaction data and match to chart of accounts using rules and optionally LLM.'
    )
    parser.add_argument(
        'input_file',
        type=str,
        help='Path to input CSV/Excel file containing transactions'
    )
    parser.add_argument(
        '--chart-of-accounts', '-c',
        type=str,
        default='config/chart_of_accounts.json',
        help='Path to chart of accounts JSON file (default: config/chart_of_accounts.json)'
    )
    parser.add_argument(
        '--rule-store', '-r',
        type=str,
        default='data/rules.json',
        help='Path to rule store JSON file (default: data/rules.json)'
    )
    parser.add_argument(
        '--mapping-store', '-m',
        type=str,
        default='data/mappings.json',
        help='Path to mapping store JSON file (default: data/mappings.json)'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Path for output file. If not specified, will append "_categorized" to input filename'
    )
    parser.add_argument(
        '--use-llm', 
        action='store_true', 
        help='Enable second-pass matching using LLM for low-confidence/unmatched transactions.'
    )
    parser.add_argument(
        '--llm-threshold', 
        type=float, 
        default=0.80, 
        help='Confidence threshold (0.0-1.0) below which LLM matching is triggered (default: 0.80)'
    )
    # Add verbosity option?
    # parser.add_argument('-v', '--verbose', action='store_true', help='Increase output verbosity')
    
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
    
    # Validate llm_threshold
    if not (0.0 <= args.llm_threshold <= 1.0):
        logger.error(f"Invalid LLM threshold: {args.llm_threshold}. Must be between 0.0 and 1.0.")
        exit(1)
        
    # Load chart of accounts
    logger.info(f"Loading chart of accounts from {args.chart_of_accounts}...")
    try:
        chart = ChartOfAccounts.from_json_file(args.chart_of_accounts)
    except FileNotFoundError:
        logger.error(f"Chart of accounts file not found: {args.chart_of_accounts}")
        exit(1)
    except Exception as e:
        logger.error(f"Error loading chart of accounts: {e}", exc_info=True)
        exit(1)

    # Initialize components
    processor = TransactionProcessor()
    matcher_engine = MatchingEngine(chart) # Renamed variable for clarity
    output_gen = OutputGenerator()
    
    # --- Configure Matching Engine --- 
    # 1. Add Primary Matcher (RuleMatcher)
    logger.info(f"Initializing RuleMatcher with rules from {args.rule_store} and mappings from {args.mapping_store}")
    try:
        rule_matcher = RuleMatcher(
            chart_of_accounts=chart, 
            rule_store_path=args.rule_store, 
            mapping_store_path=args.mapping_store
            # Could add mapping_confidence_threshold arg here if needed
        )
        matcher_engine.add_matcher(rule_matcher)
    except Exception as e:
        logger.error(f"Error initializing RuleMatcher: {e}", exc_info=True)
        exit(1)
        
    # 2. Conditionally Add Secondary Matcher (LLMMatcher)
    if args.use_llm:
        logger.info("Initializing LLMMatcher (Note: API calls are currently placeholders)...")
        # Check for API key existence before initializing (LLMMatcher init handles loading)
        if not os.getenv("OPENAI_API_KEY"):
            logger.warning("OPENAI_API_KEY environment variable not set. LLM matching will be skipped.")
        else:
            try:
                # We pass api_key=None here, relying on LLMMatcher to load from env
                llm_matcher = LLMMatcher(chart_of_accounts=chart, api_key=None)
                matcher_engine.add_matcher(llm_matcher)
            except Exception as e:
                 logger.error(f"Error initializing LLMMatcher: {e}. LLM matching will be skipped.", exc_info=True)
                 # Continue without LLM matcher

    # Process input file
    logger.info(f"Processing input file: {args.input_file}")
    try:
        transactions = processor.read_file(args.input_file)
    except FileNotFoundError:
         logger.error(f"Input file not found: {args.input_file}")
         exit(1)
    except ValueError as e: # Handle unsupported format or missing columns
         logger.error(f"Error processing input file {args.input_file}: {e}")
         exit(1)
    except Exception as e:
        logger.error(f"Unexpected error reading input file: {e}", exc_info=True)
        exit(1)

    # Match transactions using the configured engine and threshold
    logger.info(f"Matching {len(transactions)} transactions to accounts...")
    try:
        matched_transactions = matcher_engine.process_transactions(
            transactions,
            secondary_confidence_threshold=args.llm_threshold
        )
    except Exception as e:
        logger.error(f"Error during transaction matching: {e}", exc_info=True)
        exit(1)

    # Generate output
    output_path = get_output_path(args.input_file, args.output)
    logger.info(f"Generating output file: {output_path}")
    try:
        output_gen.generate_file(matched_transactions, output_path)
    except Exception as e:
        logger.error(f"Error generating output file {output_path}: {e}", exc_info=True)
        exit(1)
        
    # TODO: Add option to save updated rules/mappings?
    # rule_matcher.save_rules() 
    
    logger.info("Processing complete!")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        # Catch any unexpected errors at the top level
        logger.critical(f"An unexpected critical error occurred: {e}", exc_info=True)
        exit(1) 