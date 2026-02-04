
import logging
import sys
import os
from unittest.mock import MagicMock

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Add project root to path
sys.path.append(os.getcwd())

from app.services.config_loader import ConfigLoader as FinanceConfigLoader
from app.core.config_loader import ConfigLoader as CoreConfigLoader

def test_loaders():
    print("\n🧪 Testing Loaders Initialization...")
    
    # Mock Firestore
    mock_db = MagicMock()
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {"tasa_nmv_banco": 2.22}
    mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
    
    print("\n--- Initializing Core ConfigLoader ---")
    core_loader = CoreConfigLoader(mock_db)
    core_loader.load_all()
    
    print("\n--- Initializing Finance ConfigLoader ---")
    fin_loader = FinanceConfigLoader(mock_db)
    # Note: FinanceConfigLoader (app.services.config_loader) auto-loads in __init__
    
    print("\n--- Checking Values ---")
    print(f"Finance: {fin_loader.get_financial_config()}")

if __name__ == "__main__":
    test_loaders()
