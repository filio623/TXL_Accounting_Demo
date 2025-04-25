import logging
from typing import List, Optional
import os # Import os to potentially use os.getenv
import re # Need re for parsing
# Import load_dotenv
from dotenv import load_dotenv
# Import OpenAI library
from openai import OpenAI, OpenAIError

from .matcher import Matcher
from ..models.transaction import Transaction
from ..models.account import Account, ChartOfAccounts
# We will need an LLM client library later, e.g.:
# from openai import OpenAI 

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

class LLMMatcher(Matcher):
    """
    Matcher that uses a Large Language Model (LLM) to match transactions.
    Basic implementation using OpenAI API.
    """
    
    def __init__(self, 
                 chart_of_accounts: ChartOfAccounts, 
                 llm_model_name: str = "gpt-4o-mini", # Updated default model
                 api_key: Optional[str] = None, # Allow passing key directly (e.g., for testing) but prefer env var
                 max_prompt_tokens: int = 4000 # Placeholder limit
                ):
        """
        Initialize the LLM matcher.
        Loads API key from environment variable OPENAI_API_KEY if not passed directly.
        Initializes the OpenAI client.
        
        Args:
            chart_of_accounts: The chart of accounts to match against.
            llm_model_name: Name of the LLM model to use.
            api_key: Optional API key. If None, attempts to load from OPENAI_API_KEY env var.
            max_prompt_tokens: Estimated max tokens for the prompt.
        """
        super().__init__(chart_of_accounts)
        self.model_name = llm_model_name
        self.max_prompt_tokens = max_prompt_tokens
        self.client = None # Initialize client as None
        
        # Determine the API key to use
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if not self._api_key:
            logger.error("OpenAI API key not found. Set OPENAI_API_KEY environment variable or pass via config/init. LLM Matcher will be disabled.")
        else:
            logger.info("OpenAI API key loaded successfully.")
            # Initialize the LLM client
            try:
                self.client = OpenAI(api_key=self._api_key)
                logger.info(f"LLMMatcher initialized OpenAI client for model: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                # Client remains None, LLM calls will fail gracefully

        logger.info(f"LLMMatcher configured for model: {self.model_name}")
    
    def _create_prompt(self, transaction: Transaction) -> str:
        """Create the prompt for the LLM, emphasizing single account number output."""
        # Simplified prompt focusing on just the account number output
        prompt = f"""
        Analyze the following bank transaction and the provided chart of accounts (leaf nodes only).
        Respond with ONLY the 4-digit account number from the chart that is the single best match.
        Do not include any other text, explanation, or formatting.
        
        Chart of Accounts (Leaf Nodes):
        """
        leaf_accounts_str = "\n".join([f"- {acc.number}: {acc.full_name}" for acc in self.chart_of_accounts.get_leaf_accounts()])
        prompt += leaf_accounts_str
        
        prompt += f"""
        
        Transaction:
        - Description: {transaction.description}
        - Amount: {transaction.amount}
        - Type: {transaction.type}
        - Category: {transaction.category}
        
        Account Number:""" # End prompt clearly asking for the number
        
        # TODO: Token counting/truncation is still important for production
        return prompt
        
    def _call_llm_api(self, prompt: str) -> Optional[str]:
        """Call the OpenAI API and get the response."""
        if not self.client: # Check if client was initialized successfully
             logger.error("Cannot call LLM API: OpenAI client not initialized (check API key and initialization logs).")
             return None
             
        logger.debug(f"Sending prompt to {self.model_name}...") # Log before call
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10, # Should be enough for just an account number
                temperature=0.1, 
                n=1, 
                stop=None 
            )
            llm_output = response.choices[0].message.content.strip()
            logger.debug(f"LLM Raw Output: {llm_output}")
            return llm_output
        except OpenAIError as e: # Catch specific OpenAI errors
            logger.error(f"OpenAI API error: {e} (Status code: {e.status_code}, Type: {e.type})")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling LLM API: {e}")
            return None

    def _parse_llm_response(self, llm_output: str) -> Optional[str]:
        """Parse the LLM response, expecting just an account number."""
        # Trim potential whitespace/newlines
        parsed_number = llm_output.strip()
        
        # Basic validation: check if it looks like a number and exists in CoA
        if re.fullmatch(r"\d+", parsed_number): # Check if it contains only digits
            # Check if this number actually exists in our chart of accounts
            # Note: This requires access to chart_of_accounts, which the base Matcher has
            if self.chart_of_accounts.find_account(parsed_number):
                 logger.debug(f"Parsed account number '{parsed_number}' and verified it exists.")
                 return parsed_number
            else:
                 logger.warning(f"LLM output '{parsed_number}' looks like an account number but doesn't exist in Chart of Accounts.")
                 return None
        else:
            logger.warning(f"LLM output '{parsed_number}' is not a valid account number format.")
            return None

    def match_transaction(self, transaction: Transaction) -> None:
        """
        Match a single transaction using the LLM.
        Updates the transaction with match results if successful.
        
        Args:
            transaction: The transaction to match
        """
        logger.info(f"LLMMatcher attempting to match transaction: '{transaction.description}'")
        # 1. Create prompt
        prompt = self._create_prompt(transaction)
        
        # 2. Call LLM API
        llm_output = self._call_llm_api(prompt)
        
        # 3. Parse response
        if not llm_output:
            logger.warning(f"LLM API call failed or returned no output for: {transaction.description}")
            return 
            
        account_number = self._parse_llm_response(llm_output)
        
        # 4. Find account and update transaction
        if account_number:
            matched_account = self.chart_of_accounts.find_account(account_number)
            if matched_account and matched_account.is_leaf:
                # Use placeholder confidence for now
                confidence = self.get_match_confidence(transaction, matched_account)
                # Important: Check if LLM match is better than existing match (if any)
                # This prevents overwriting a high-confidence rule match with a lower-confidence LLM match
                if not transaction.is_matched or confidence > transaction.match_confidence:
                    logger.info(f"LLM applying match for '{transaction.description}' -> {account_number} (Confidence: {confidence:.2f})")
                    transaction.add_match(matched_account, confidence)
                    # TODO: Add logic to add the previous match (if any) to alternatives?
                else:
                     logger.info(f"LLM suggested match {account_number} ({confidence:.2f}) for '{transaction.description}', but existing match ({transaction.matched_account.number} @ {transaction.match_confidence:.2f}) is better. Ignoring LLM.")
            elif matched_account:
                 logger.warning(f"LLM returned account {account_number} for '{transaction.description}', but it's not a leaf account.")
            else:
                # This case should be caught by the new _parse_llm_response logic, but kept as safety
                logger.warning(f"LLM returned account number {account_number} for '{transaction.description}', but it does not exist in the chart of accounts.")
        else:
            logger.warning(f"Failed to parse valid account number from LLM response for: {transaction.description}")
        
    def get_match_confidence(self, transaction: Transaction, account: Account) -> float:
        """
        (Placeholder) Calculate the confidence score for an LLM match.
        
        Args:
            transaction: The transaction to match
            account: The account the LLM matched against
            
        Returns:
            float: Confidence score between 0.0 and 1.0
        """
        # TODO: Implement confidence scoring for LLM.
        # This might involve:
        # - Asking the LLM for a confidence score directly (if supported)
        # - Analyzing the LLM's response (e.g., log probabilities if available)
        # - Using a fixed confidence score for any LLM match initially.
        # - Comparing LLM suggestion with rule-based suggestions.
        logger.warning("LLM confidence scoring not implemented yet. Returning default 0.75.")
        return 0.75 # Placeholder confidence
