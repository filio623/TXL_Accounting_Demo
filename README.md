# TXL Accounting Demo

A transaction matching system that helps accountants match bank transactions to the appropriate accounts in a chart of accounts using rule-based matching.

## Overview

TXL Accounting Demo is designed to automate the process of matching bank transactions to the appropriate accounts in a chart of accounts. It uses a combination of rule-based matching and confidence scoring to suggest the most likely account for each transaction, reducing manual work for accountants.

## Features

- Import transactions from CSV or Excel files
- Match transactions to accounts using customizable rules
- Calculate confidence scores for matches
- Export matched transactions to CSV or Excel
- Comprehensive test suite for all components

## Project Structure

```
TXL_Accounting_Demo/
├── src/                      # Source code
│   ├── data/                 # Data processing
│   │   ├── input_processor.py  # Handles file input
│   │   └── output_generator.py # Handles file output
│   ├── matching/             # Matching algorithms
│   │   ├── matcher.py        # Base matcher class
│   │   └── rule_matcher.py   # Rule-based matcher
│   ├── models/               # Data models
│   │   ├── account.py        # Account and ChartOfAccounts
│   │   └── transaction.py    # Transaction model
│   └── utils/                # Utility functions
├── tests/                    # Test suite
│   ├── data/                 # Tests for data processing
│   ├── matching/             # Tests for matching algorithms
│   └── models/               # Tests for data models
├── .gitignore                # Git ignore file
├── BUILD_PLAN.md             # Development plan
├── README.md                 # This file
└── requirements.txt          # Project dependencies
```

## Program Flow

1. **Data Import**
   - User provides a CSV or Excel file containing transactions
   - `InputProcessor` reads and validates the data
   - Transactions are converted to `Transaction` objects

2. **Chart of Accounts**
   - The system loads a chart of accounts
   - Accounts are organized in a hierarchical structure
   - Each account has a number, name, and optional parent account

3. **Transaction Matching**
   - For each transaction, the `MatchingEngine` orchestrates the process:
     - **Pass 1 (Primary Matcher - typically `RuleMatcher`):**
       - Applies description mappings (e.g., `"Vendor LLC" -> "Vendor"`).
       - Evaluates predefined rules against the mapped description.
       - Selects the best rule match based on priority and confidence.
       - Updates the `Transaction` with the match (account, confidence, source=RULE).
     - **Pass 2 (Secondary Matcher - typically `LLMMatcher`, if enabled):**
       - Filters transactions that were not matched in Pass 1 or had confidence below a threshold.
       - For each filtered transaction:
         - Creates a prompt including transaction details and Chart of Accounts context.
         - Calls the LLM API.
         - Parses the response (account number and confidence score).
         - If the LLM match is valid and has confidence >= any existing match, updates the `Transaction` (account, confidence, source=LLM).

4. **Output Generation**
   - Matched transactions are exported to CSV or Excel using `OutputGenerator`.
   - Output includes transaction details and match information (Account Number, Name, Path, Confidence, Source).
   - Alternative matches (from `Transaction.add_match` logic) may also be included.

### Flowchart

This diagram shows the overall process flow.

```mermaid
graph TD
    Start([Start]) --> LoadConfig{Load Config/Data};
    LoadConfig -- Chart of Accounts --> InitMatchers[Initialize Matchers];
    LoadConfig -- Rules/Mappings --> InitMatchers;
    InitMatchers --> ReadInput[Read Input CSV];
    ReadInput -- Transactions List --> RunEngine[Run Matching Engine];

    subgraph Matching Engine
        RunEngine --> Pass1{Pass 1: RuleMatcher};
        Pass1 -- Updated Transactions --> CheckThreshold{Check Confidence < Threshold?};
        CheckThreshold -- Yes --> Pass2{Pass 2: LLMMatcher};
        CheckThreshold -- No --> CombineResults[Combine Results];
        Pass2 -- Updated Transactions --> CombineResults;
    end

    CombineResults -- Final Transactions --> GenerateOutput[Generate Output CSV];
    GenerateOutput --> End([End]);

    style Start fill:#ddd,stroke:#333,stroke-width:2px
    style End fill:#ddd,stroke:#333,stroke-width:2px
    style LoadConfig fill:#ffc,stroke:#333,stroke-width:2px
    style ReadInput fill:#ffc,stroke:#333,stroke-width:2px
    style GenerateOutput fill:#ffc,stroke:#333,stroke-width:2px
    style CheckThreshold fill:#cff,stroke:#333,stroke-width:2px
```

### High-Level Sequence Diagram

This diagram shows the main interaction between components.

```mermaid
sequenceDiagram
    participant User
    participant main.py
    participant DataLoaders
    participant MatchingEngine
    participant RuleMatcher
    participant LLMMatcher
    participant OutputGenerator

    User->>main.py: Run Script (CSV, flags)
    main.py->>DataLoaders: Load CoA, Rules, Mappings
    DataLoaders-->>main.py: Config / Data
    main.py->>MatchingEngine: Initialize & Add Matchers
    main.py->>DataLoaders: Read Transactions (CSV)
    DataLoaders-->>main.py: Transaction List
    main.py->>MatchingEngine: process_transactions(List[Tx])

    MatchingEngine->>RuleMatcher: Pass 1: Process All Tx
    RuleMatcher-->>MatchingEngine: Tx Updated (Rule Matches)

    opt LLM Enabled
        MatchingEngine->>LLMMatcher: Pass 2: Process Filtered Tx
        LLMMatcher-->>MatchingEngine: Tx Updated (LLM Matches)
    end

    MatchingEngine-->>main.py: Final Processed Tx List
    main.py->>OutputGenerator: Generate Output File
    OutputGenerator-->>main.py: (File Written)
    main.py-->>User: Log Completion
```

### Detailed Sequence Diagram (with LLM enabled)

This diagram provides more detail on the internal calls.

```mermaid
sequenceDiagram
    participant User
    participant main.py
    participant TransactionProcessor
    participant ChartOfAccounts
    participant RuleStore
    participant MappingStore
    participant MatchingEngine
    participant RuleMatcher
    participant LLMMatcher
    participant OutputGenerator

    User->>main.py: Run script (input_file.csv, --use-llm)
    main.py->>ChartOfAccounts: Load from config/chart_of_accounts.json
    ChartOfAccounts-->>main.py: Chart instance
    main.py->>RuleMatcher: Initialize (passing Chart, store paths)
    RuleMatcher->>MappingStore: load()
    MappingStore-->>RuleMatcher: Mappings dict
    RuleMatcher->>RuleStore: load()
    RuleStore-->>RuleMatcher: Rules list
    RuleMatcher-->>main.py: RuleMatcher instance
    main.py->>LLMMatcher: Initialize (passing Chart)
    LLMMatcher-->>main.py: LLMMatcher instance
    main.py->>MatchingEngine: Initialize (passing Chart)
    MatchingEngine-->>main.py: Engine instance
    main.py->>MatchingEngine: add_matcher(RuleMatcher)
    main.py->>MatchingEngine: add_matcher(LLMMatcher)

    main.py->>TransactionProcessor: read_file(input_file.csv)
    TransactionProcessor-->>main.py: List[Transaction]
    main.py->>MatchingEngine: process_transactions(transactions, threshold)

    MatchingEngine->>RuleMatcher: process_transactions(transactions)
    loop For each Transaction
        RuleMatcher->>RuleMatcher: _apply_mapping(desc)
        RuleMatcher->>RuleMatcher: Evaluate rules against mapped_desc
        alt Rule Match Found (Priority/Confidence Check)
            RuleMatcher->>ChartOfAccounts: find_account(rule_acc_num)
            ChartOfAccounts-->>RuleMatcher: Account object
            RuleMatcher->>Transaction: add_match(account, confidence, MatchSource.RULE)
        end
    end
    RuleMatcher-->>MatchingEngine: (Transactions updated)

    MatchingEngine->>MatchingEngine: Filter transactions below threshold
    MatchingEngine->>LLMMatcher: process_transactions(filtered_transactions)
    loop For each Filtered Transaction
        LLMMatcher->>LLMMatcher: _create_prompt(transaction, chart)
        LLMMatcher->>LLMMatcher: _call_llm_api(prompt)
        LLMMatcher->>LLMMatcher: _parse_llm_response(api_output)
        opt Valid Account & Confidence Parsed
            LLMMatcher->>ChartOfAccounts: find_account(parsed_acc_num)
            ChartOfAccounts-->>LLMMatcher: Account object
            alt LLM Confidence >= Existing Confidence
                 LLMMatcher->>Transaction: add_match(account, confidence, MatchSource.LLM)
            end
        end
    end
    LLMMatcher-->>MatchingEngine: (Filtered transactions updated)

    MatchingEngine-->>main.py: List[Transaction] (updated)
    main.py->>OutputGenerator: generate_file(transactions, output_path)
    OutputGenerator-->>main.py: (File written)
    main.py-->>User: Log "Processing complete!"
```

## Getting Started

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/TXL_Accounting_Demo.git
   cd TXL_Accounting_Demo
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

### Usage

The command-line interface is currently under development. Once completed, you'll be able to:

1. Import transactions:
   ```
   python -m src.cli import --file transactions.csv
   ```

2. Match transactions:
   ```
   python -m src.cli match --chart chart_of_accounts.json
   ```

3. Export results:
   ```
   python -m src.cli export --output matched_transactions.xlsx
   ```

## Development

### Running Tests

```
python -m pytest tests/
```

### Adding New Features

1. Create a new branch for your feature
2. Implement the feature
3. Write tests for the feature
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Thanks to all contributors who have helped with this project
- Inspired by real-world accounting challenges 