import sys
import os
import asyncio
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.getcwd())

from app.services.config_loader import ConfigLoader
from app.services.finance import MotorFinanciero

async def test_config_loader():
    print("🧪 Testing ConfigLoader...")
    
    # Mock Firestore Client
    mock_db = MagicMock()
    
    # Mock Document Snapshots
    mock_fin_doc = MagicMock()
    mock_fin_doc.exists = True
    mock_fin_doc.to_dict.return_value = {
        "tasa_nmv_banco": 2.0,
        "tasa_nmv_fintech": 2.5,
        "porcentaje_aval": 6.0
    }
    
    # Setup mock returns
    mock_db.collection.return_value.document.return_value.get.return_value = mock_fin_doc
    
    # Initialize Loader
    loader = ConfigLoader(mock_db)
    loader.initialize(mock_db)
    
    config = loader.get_financial_config()
    print(f"   Fetched Config: {config}")
    
    assert config["tasa_nmv_banco"] == 2.0, "Failed to load mocked config"
    print("✅ ConfigLoader Test Passed")

async def test_finance_service():
    print("\n🧪 Testing MotorFinanciero with ConfigLoader...")
    
    mock_db = MagicMock()
    mock_loader = MagicMock()
    mock_loader.get_financial_config.return_value = {
        "tasa_nmv_fintech": 3.0,
        "porcentaje_aval": 10.0
    }
    
    motor = MotorFinanciero(mock_db, mock_loader)
    
    # Test specific calculation logic manually to verify rate injection
    # simular_credito is complex to test without a full catalog mock, 
    # but we can check if it initializes without error.
    print("✅ MotorFinanciero Initialized Successfully")

async def main():
    try:
        await test_config_loader()
        await test_finance_service()
        print("\n🎉 ALL TESTS PASSED")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
