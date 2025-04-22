from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import json
from pathlib import Path


@dataclass
class Account:
    """
    Represents an account in the chart of accounts.
    Supports hierarchical structure where accounts can have parent/child relationships.
    """
    number: str
    name: str
    children: List[Account] = field(default_factory=list)
    parent: Optional[Account] = None
    
    @property
    def full_name(self) -> str:
        """Returns the full account name including parent names."""
        if self.parent:
            return f"{self.parent.full_name} > {self.name}"
        return self.name
    
    @property
    def is_leaf(self) -> bool:
        """Returns True if this account has no children."""
        return len(self.children) == 0
    
    def add_child(self, child: Account) -> None:
        """Add a child account to this account."""
        child.parent = self
        self.children.append(child)
    
    def find_by_number(self, number: str) -> Optional[Account]:
        """Find an account by its number in this account's hierarchy."""
        if self.number == number:
            return self
        
        for child in self.children:
            result = child.find_by_number(number)
            if result:
                return result
        return None
    
    def to_dict(self) -> Dict:
        """Convert the account to a dictionary format."""
        result = {
            "number": self.number,
            "name": self.name
        }
        if self.children:
            result["children"] = [child.to_dict() for child in self.children]
        return result


class ChartOfAccounts:
    """
    Represents the entire chart of accounts structure.
    Provides methods for loading, searching, and managing accounts.
    """
    def __init__(self):
        self.accounts: List[Account] = []
        
    @classmethod
    def from_json_file(cls, file_path: str | Path) -> 'ChartOfAccounts':
        """Load chart of accounts from a JSON file."""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        chart = cls()
        for account_data in data.get("chartOfAccounts", []):
            chart.accounts.append(cls._create_account_from_dict(account_data))
        return chart
    
    @staticmethod
    def _create_account_from_dict(data: Dict) -> Account:
        """Recursively create Account objects from dictionary data."""
        account = Account(
            number=data["number"],
            name=data["name"]
        )
        
        for child_data in data.get("children", []):
            child = ChartOfAccounts._create_account_from_dict(child_data)
            account.add_child(child)
            
        return account
    
    def find_account(self, number: str) -> Optional[Account]:
        """Find an account by its number in the entire chart."""
        for account in self.accounts:
            result = account.find_by_number(number)
            if result:
                return result
        return None
    
    def get_leaf_accounts(self) -> List[Account]:
        """Get all leaf accounts (accounts with no children)."""
        def _get_leaves(account: Account) -> List[Account]:
            if account.is_leaf:
                return [account]
            leaves = []
            for child in account.children:
                leaves.extend(_get_leaves(child))
            return leaves
        
        leaves = []
        for account in self.accounts:
            leaves.extend(_get_leaves(account))
        return leaves
    
    def to_dict(self) -> Dict:
        """Convert the chart of accounts to a dictionary format."""
        return {
            "chartOfAccounts": [account.to_dict() for account in self.accounts]
        }
