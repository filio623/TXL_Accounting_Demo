import pytest
import json
from pathlib import Path

from src.persistence.mapping_store import MappingStore, MappingData


@pytest.fixture
def mapping_store(tmp_path: Path) -> MappingStore:
    """Provides a MappingStore instance using a temporary file path."""
    file_path = tmp_path / "test_mappings.json"
    return MappingStore(file_path)


def test_save_load_empty(mapping_store: MappingStore):
    """Test saving and loading an empty mapping dictionary."""
    empty_mappings: MappingData = {}
    mapping_store.save(empty_mappings)
    assert mapping_store.file_path.exists()
    
    loaded_mappings = mapping_store.load()
    assert loaded_mappings == {}


def test_save_load_basic(mapping_store: MappingStore):
    """Test saving and loading a basic mapping dictionary."""
    test_mappings: MappingData = {
        "STAPLES STORE 123": "6000",
        "AMAZON MKTPLACE": "6010",
        "UBER EATS": "5030"
    }
    mapping_store.save(test_mappings)
    assert mapping_store.file_path.exists()
    
    loaded_mappings = mapping_store.load()
    assert loaded_mappings == test_mappings


def test_load_non_existent(tmp_path: Path):
    """Test loading when the mapping file does not exist."""
    store = MappingStore(tmp_path / "non_existent_mappings.json")
    assert not store.file_path.exists()
    loaded_mappings = store.load()
    assert loaded_mappings == {}


def test_add_mapping_new(mapping_store: MappingStore):
    """Test adding a new mapping via add_mapping."""
    description = "NEW VENDOR INC"
    account_number = "7100"
    
    # Ensure it doesn't exist initially (load should return empty)
    initial_load = mapping_store.load()
    assert description not in initial_load
    
    mapping_store.add_mapping(description, account_number)
    
    # Load again and verify the new mapping is present
    final_load = mapping_store.load()
    assert final_load == {description: account_number}


def test_add_mapping_update(mapping_store: MappingStore):
    """Test updating an existing mapping via add_mapping."""
    description = "EXISTING VENDOR"
    initial_account = "8000"
    updated_account = "8001"
    
    # Add initial mapping
    mapping_store.add_mapping(description, initial_account)
    assert mapping_store.load() == {description: initial_account}
    
    # Update the mapping
    mapping_store.add_mapping(description, updated_account)
    
    # Verify the mapping was updated
    assert mapping_store.load() == {description: updated_account}

def test_add_mapping_multiple(mapping_store: MappingStore):
    """Test adding multiple mappings preserves existing ones."""
    mapping_store.add_mapping("Vendor A", "1111")
    mapping_store.add_mapping("Vendor B", "2222")
    mapping_store.add_mapping("Vendor C", "3333")
    
    expected_mappings = {
        "Vendor A": "1111",
        "Vendor B": "2222",
        "Vendor C": "3333"
    }
    assert mapping_store.load() == expected_mappings


def test_load_invalid_json_format(mapping_store: MappingStore):
    """Test loading a file with invalid JSON."""
    with open(mapping_store.file_path, 'w') as f:
        f.write("this is not valid json{")
    
    loaded_mappings = mapping_store.load()
    assert loaded_mappings is None # Should return None on JSON decode error


def test_load_invalid_data_type(mapping_store: MappingStore):
    """Test loading a file with incorrect data types (not Dict[str, str])."""
    invalid_data = ["list", "not", "a", "dict"]
    with open(mapping_store.file_path, 'w') as f:
        json.dump(invalid_data, f)
    
    loaded_mappings = mapping_store.load()
    assert loaded_mappings is None # Should return None on format validation error


def test_load_invalid_data_content(mapping_store: MappingStore):
    """Test loading a file with correct dict type but wrong content types."""
    invalid_data = {"Valid Key": 12345} # Value is not a string
    with open(mapping_store.file_path, 'w') as f:
        json.dump(invalid_data, f)
        
    loaded_mappings = mapping_store.load()
    assert loaded_mappings is None # Should return None on format validation error 