import logging
from typing import List, Optional, Tuple
import os # Import os to potentially use os.getenv
import re # Need re for parsing
# Import load_dotenv
from dotenv import load_dotenv
# Import OpenAI library
from openai import OpenAI, OpenAIError

from .matcher import Matcher
from ..models.transaction import Transaction, MatchSource # Import MatchSource
from ..models.account import Account, ChartOfAccounts
# We will need an LLM client library later, e.g.:
# from openai import OpenAI 

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

class LLMMatcher(Matcher):
    """
    Matches transactions using a Large Language Model (LLM) API (specifically OpenAI).

    This matcher is typically used as a secondary pass for transactions that
    could not be matched with high confidence by primary methods (e.g., rules).
    It constructs a prompt including transaction details and relevant chart of
    accounts information, calls the LLM API, parses the response (expecting
    an account number and confidence score), and updates the transaction.
    """
    
    DEFAULT_MODEL = "gpt-4o-mini" # Class constant for default model
    MAX_RESPONSE_TOKENS = 15 # Slightly more buffer for account + confidence
    DEFAULT_API_TIMEOUT = 30.0 # Default timeout for API calls (seconds)
    
    def __init__(self, 
                 chart_of_accounts: ChartOfAccounts, 
                 llm_model_name: str = DEFAULT_MODEL,
                 api_key: Optional[str] = None, 
                 max_prompt_tokens: Optional[int] = None, # Make optional, can be estimated
                 api_timeout: float = DEFAULT_API_TIMEOUT
                ):
        """
        Initializes the LLM Matcher.
        
        Sets up the OpenAI client using an API key provided directly or via the 
        OPENAI_API_KEY environment variable.
        
        Args:
            chart_of_accounts: The ChartOfAccounts instance.
            llm_model_name: The specific OpenAI model identifier to use (e.g., "gpt-4o-mini").
            api_key: The OpenAI API key. If None, it's read from the environment.
            max_prompt_tokens: (Optional) An estimated maximum token limit for prompts. 
                               Used primarily for future-proofing or cost estimation. 
                               Token counting/truncation is not yet implemented.
            api_timeout: Timeout duration in seconds for API calls.
        """
        super().__init__(chart_of_accounts)
        self.model_name = llm_model_name
        self.max_prompt_tokens = max_prompt_tokens # Store even if not used yet
        self.api_timeout = api_timeout
        self.client: Optional[OpenAI] = None # Explicitly type hint client
        
        # Load API Key
        resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_api_key:
            logger.error("OpenAI API key not provided or found in environment (OPENAI_API_KEY). LLM Matcher disabled.")
            return # Exit init if no key
            
        logger.info("OpenAI API key loaded.")
        
        # Initialize OpenAI Client
        try:
            self.client = OpenAI(
                api_key=resolved_api_key,
                timeout=self.api_timeout
            )
            logger.info(f"LLMMatcher initialized OpenAI client. Model: {self.model_name}, Timeout: {self.api_timeout}s")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
            self.client = None # Ensure client is None if init fails
    
    def _create_prompt(self, transaction: Transaction) -> Optional[str]:
        """
        Constructs the prompt to send to the LLM.

        Includes instructions, the list of valid leaf account numbers and names,
        and the details of the transaction to be categorized.
        Requests the best matching account number and a confidence score (0-100).
        
        Returns:
            The formatted prompt string, or None if an error occurs (e.g., no leaf accounts).
        """
        try:
            leaf_accounts = self.chart_of_accounts.get_leaf_accounts()
            if not leaf_accounts:
                logger.error("Cannot create LLM prompt: No leaf accounts found in Chart of Accounts.")
                return None
                
            leaf_accounts_str = "\n".join([
                f"- {acc.number}: {acc.full_name}" 
                for acc in leaf_accounts
            ])
            
            # Construct the prompt using f-string for clarity
            prompt = f"""
            You are an expert accounting assistant performing transaction categorization.
            Analyze the bank transaction provided below.
            Compare its details against the following Chart of Accounts (only leaf accounts are listed):
            
            Chart of Accounts (Leaf Nodes):
            {leaf_accounts_str}
            
            Transaction:
            - Date: {transaction.post_date.strftime('%Y-%m-%d')}
            - Description: {transaction.description}
            - Amount: {transaction.amount}
            - Type: {transaction.type}
            - Bank Category: {transaction.category or 'N/A'}
            
            Based on the transaction description and details, determine the single best matching 4-digit account number from the list above.
            Then, provide a confidence score (integer 0-100) indicating your certainty in this match.
            
            Instructions for your response:
            1. First line: ONLY the 4-digit account number.
            2. Second line: ONLY the integer confidence score (0-100).
            Do NOT include any other text, labels, explanations, or formatting.
            
            Account Number:
            Confidence Score (0-100):"""
            
            # Basic check for prompt length (more sophisticated token counting needed for production)
            # if self.max_prompt_tokens and len(prompt) > self.max_prompt_tokens * 0.8: # Heuristic
            #     logger.warning(f"Generated prompt length ({len(prompt)} chars) may exceed estimated token limit.")

            return prompt
            
        except Exception as e:
             logger.error(f"Error creating LLM prompt for transaction: {e}", exc_info=True)
             return None
        
    def _call_llm_api(self, prompt: str) -> Optional[str]:
        """
        Calls the configured OpenAI API endpoint (chat completions).
        
        Args:
            prompt: The formatted prompt string.
            
        Returns:
            The content of the LLM's response message as a string, or None if the API call fails.
        """
        if not self.client:
             logger.error("LLM API call skipped: OpenAI client is not initialized.")
             return None
             
        logger.debug(f"Sending prompt to {self.model_name} (max_tokens={self.MAX_RESPONSE_TOKENS}, temp=0.1)...")
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.MAX_RESPONSE_TOKENS, 
                temperature=0.1, # Low temperature for more deterministic output
                n=1, 
                stop=None # Let the model decide when to stop (should be after 2 lines)
            )
            # Ensure choices exist and message content is present
            if response.choices and response.choices[0].message and response.choices[0].message.content:
                llm_output = response.choices[0].message.content.strip()
                logger.debug(f"LLM Raw Output:\n{llm_output}")
                return llm_output
            else:
                logger.error("Invalid response structure received from OpenAI API.")
                logger.debug(f"Full API Response: {response}")
                return None
                
        except OpenAIError as e:
            logger.error(f"OpenAI API error during LLM call: {e} (Status: {getattr(e, 'status_code', 'N/A')}, Type: {getattr(e, 'type', 'N/A')})")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling OpenAI API: {e}", exc_info=True)
            return None

    def _parse_llm_response(self, llm_output: Optional[str]) -> Tuple[Optional[str], float]:
        """
        Parses the expected two-line response from the LLM.
        
        Line 1: Expected 4-digit account number.
        Line 2: Expected integer confidence score (0-100).
        
        Validates the account number against the Chart of Accounts and ensures it's a leaf.
        Converts the confidence score to a 0.0-1.0 float.
        
        Args:
            llm_output: The raw string output from the LLM API call.
            
        Returns:
            A tuple containing: (validated_account_number: Optional[str], confidence_score: float).
            Returns (None, 0.0) if parsing fails or validation checks do not pass.
        """
        if not llm_output:
            return None, 0.0
            
        account_number: Optional[str] = None
        confidence: float = 0.0
        
        try:
            lines = llm_output.strip().split('\n')
            if len(lines) >= 2:
                # --- Parse Account Number (Line 1) ---
                parsed_acc_num_str = lines[0].strip()
                # Regex now specifically looks for 4 digits
                if re.fullmatch(r"\d{4}", parsed_acc_num_str):
                    potential_account = self.chart_of_accounts.find_account(parsed_acc_num_str)
                    if potential_account and potential_account.is_leaf:
                        account_number = parsed_acc_num_str # Validated account number
                    elif potential_account: 
                         logger.warning(f"LLM returned account number '{parsed_acc_num_str}' which exists but is not a leaf account.")
                    else:
                         logger.warning(f"LLM returned account number '{parsed_acc_num_str}' which was not found in the Chart of Accounts.")
                else:
                    logger.warning(f"LLM output line 1 '{parsed_acc_num_str}' is not a valid 4-digit format.")
                    
                # --- Parse Confidence Score (Line 2) ---
                parsed_conf_str = lines[1].strip()
                if re.fullmatch(r"\d+", parsed_conf_str):
                    try:
                        parsed_conf_int = int(parsed_conf_str)
                        if 0 <= parsed_conf_int <= 100:
                            confidence = float(parsed_conf_int) / 100.0
                        else:
                            logger.warning(f"LLM confidence score '{parsed_conf_int}' out of range (0-100).")
                    except ValueError:
                         logger.warning(f"LLM confidence score '{parsed_conf_str}' could not be converted to integer.")
                else:
                     logger.warning(f"LLM confidence score '{parsed_conf_str}' is not a valid integer format.")
            else:
                 logger.warning(f"LLM output did not contain at least two lines. Raw Output: '{llm_output}'")
                 
        except Exception as e:
            logger.error(f"Error parsing LLM response text: '{llm_output}'. Error: {e}", exc_info=True)
            return None, 0.0 # Return default on unexpected parsing error
            
        # Final check: Only return confidence > 0 if we have a valid account number
        if account_number is None:
             logger.debug(f"Parsing failed to yield valid account number from LLM response: '{llm_output}'")
             return None, 0.0
             
        logger.debug(f"Successfully parsed LLM response: Account={account_number}, Confidence={confidence:.2f}")
        return account_number, confidence

    def match_transaction(self, transaction: Transaction) -> None:
        """
        Attempts to match a single transaction using the LLM API.
        
        This involves creating a prompt, calling the API, parsing the response,
        and potentially updating the transaction object if a valid match is found
        and its confidence is higher than any existing match.
        
        Args:
            transaction: The Transaction object to match.
        """
        # Skip if client failed to initialize
        if not self.client:
            logger.warning(f"Skipping LLM match for Tx '{transaction.description}': Client not initialized.")
            return
            
        logger.info(f"LLMMatcher attempting match for Tx '{transaction.description}' (ID: {transaction.id if hasattr(transaction, 'id') else 'N/A'})...")
        
        # 1. Create Prompt
        prompt = self._create_prompt(transaction)
        if not prompt:
            logger.error(f"Skipping LLM match for Tx '{transaction.description}': Failed to create prompt.")
            return
        
        # 2. Call LLM API
        llm_output = self._call_llm_api(prompt)
        if not llm_output:
            logger.warning(f"LLM API call failed or returned no output for Tx '{transaction.description}'.")
            return 
            
        # 3. Parse response (Account Number and Confidence)
        account_number, confidence = self._parse_llm_response(llm_output)
        
        # 4. Apply match if valid and better than existing
        if account_number:
            # Account number validity (existence, leaf node) is checked in _parse_llm_response
            matched_account = self.chart_of_accounts.find_account(account_number) 
            
            # Double-check account exists (should always pass if parser worked)
            if not matched_account:
                logger.error(f"Consistency Error: Parsed account {account_number} not found by find_account() for Tx '{transaction.description}'")
                return
                
            # Check if this LLM match is better than the transaction's current match (if any)
            if not transaction.is_matched or confidence >= transaction.match_confidence: 
                # Allow LLM to overwrite if confidence is equal (e.g., update source)
                log_prefix = "Overwriting existing match" if transaction.is_matched else "Applying new match"
                logger.info(f"LLM {log_prefix} for Tx '{transaction.description}': Acc={account_number}, Conf={confidence:.2f} (Prev: {transaction.match_confidence:.2f} via {transaction.match_source.name} if matched)")
                # Use the add_match method from Transaction, providing the source
                transaction.add_match(matched_account, confidence, source=MatchSource.LLM)
            else:
                 # LLM confidence is lower than existing match confidence
                 logger.info(f"LLM suggested Acc={account_number} (Conf={confidence:.2f}) for Tx '{transaction.description}', but existing match Acc={transaction.matched_account.number} (Conf={transaction.match_confidence:.2f}, Src={transaction.match_source.name}) is better. Ignoring LLM suggestion.")
        else:
            # Parsing failed to return a valid account number
            logger.warning(f"LLM match failed for Tx '{transaction.description}': No valid account number parsed from response.")

    # Placeholder implementation to satisfy the abstract base class
    def get_match_confidence(self, transaction: Transaction, account: Account) -> float:
        """
        DEPRECATED/NEEDS REVIEW:
        Placeholder to satisfy the Matcher base class abstract method requirement.
        Confidence for LLM matches is determined during the API call and parsing.
        Returns 0.0.
        """
        # TODO: Review if this method needs any specific logic or can be removed 
        # if the Matcher base class definition is changed.
        logger.debug(f"LLMMatcher.get_match_confidence called for Tx: {transaction.description} / Acc: {account.number} - Returning 0.0 (Method inactive)")
        return 0.0

    # _validate_match is inherited from Matcher base class if not overridden
