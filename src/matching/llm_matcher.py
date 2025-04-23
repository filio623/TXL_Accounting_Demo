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
        """(Placeholder) Create the prompt for the LLM."""
        # TODO: Implement prompt engineering. Include:
        # - Clear instructions for the task (match to ONE account number)
        # - Transaction details (description, amount, type, maybe date)
        # - Relevant parts of the chart of accounts (maybe just leaf nodes or relevant branches?)
        # - Desired output format (e.g., JSON with account number and confidence)
        # - Need to be mindful of token limits.
        
        prompt = f"""
        You are an expert accounting assistant. Your task is to match the following 
        bank transaction to the most appropriate account from the provided chart of accounts.
        Only respond with the single, most likely account number.
        
        Chart of Accounts (Leaf Nodes):
        """
        # Simplistic approach: list all leaf accounts. Might exceed token limits for large charts.
        leaf_accounts_str = "\n".join([f"- {acc.number}: {acc.full_name}" for acc in self.chart_of_accounts.get_leaf_accounts()])
        prompt += leaf_accounts_str
        
        prompt += f"""
        
        Transaction:
        - Description: {transaction.description}
        - Amount: {transaction.amount}
        - Type: {transaction.type}
        - Category: {transaction.category}
        
        Respond ONLY with the most likely account number (e.g., 6010).
        Account Number: """
        
        # TODO: Add token counting and truncation logic if necessary
        # estimated_tokens = len(prompt) / 4 # Very rough estimate
        # if estimated_tokens > self.max_prompt_tokens:
        #     logger.warning("Estimated prompt tokens exceed limit. Consider truncating chart of accounts.")
            # Implement truncation logic
        
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
                max_tokens=20, # Increased slightly for robustness
                temperature=0.1, # Low temperature for deterministic account number
                n=1, # Request only one completion
                stop=None # Let model decide when to stop (or set specific stop sequences)
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
        """Parse the LLM response to extract the account number."""
        # Attempt to extract a sequence of digits (account number)
        match = re.search(r'\b(\d{4,})\b', llm_output) # Look for 4+ digits as a word
        if match:
            account_number = match.group(1)
            logger.debug(f"Parsed account number '{account_number}' from LLM output.")
            return account_number
        
        logger.warning(f"Could not parse account number (\d{{4,}}) from LLM output: {llm_output}")
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
                logger.warning(f"LLM returned account number {account_number} for '{transaction.description}', but it does not exist in the chart of accounts.")
        else:
            logger.warning(f"Failed to parse account number from LLM response for: {transaction.description}")
        
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
