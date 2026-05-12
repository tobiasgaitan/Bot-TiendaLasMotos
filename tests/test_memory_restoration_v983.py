
import asyncio
import logging
import sys
import os
from unittest.mock import MagicMock, AsyncMock, ANY

# Configuración de logs para ver la trazabilidad
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TEST_V983")

# Añadir el path del proyecto para importar los servicios
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

async def run_test():
    logger.info("🚀 Iniciando Test de Restauración MemoryService v9.8.3 (REFINADO)")
    
    # 1. Mock de Firestore
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_doc = MagicMock()
    
    mock_db.collection.return_value = mock_collection
    mock_collection.document.return_value = mock_doc
    
    # Configurar snaps y refs
    mock_snap = MagicMock()
    mock_snap.exists = True
    mock_snap.to_dict.return_value = {"status": "PENDING", "celular": "+573001234567"}
    
    mock_doc.get = AsyncMock(return_value=mock_snap)
    mock_doc.update = AsyncMock()
    mock_doc.set = AsyncMock()
    mock_doc.delete = AsyncMock()
    
    # 2. Instanciar MemoryService
    from app.services.memory_service import MemoryService
    ms = MemoryService(mock_db)
    
    test_phone = "+573001234567"
    
    # --- TEST 1: transition_to_in_progress ---
    logger.info("🧪 TEST 1: transition_to_in_progress (PENDING -> IN_PROGRESS)")
    success = await ms.transition_to_in_progress(test_phone)
    
    if success:
        logger.info("✅ TEST 1: LOGIC PASSED")
    else:
        logger.error("❌ TEST 1: LOGIC FAILED")
        return False

    # Verificar que se llamó a update con el estado correcto (usando ANY para timestamps)
    mock_doc.update.assert_called_with({
        "status": "IN_PROGRESS",
        "updated_at": ANY,
        "fecha": ANY,
    })
    logger.info("✅ TEST 1: ASSERTION PASSED")

    # --- TEST 2: set_human_help_status ---
    logger.info("🧪 TEST 2: set_human_help_status (True)")
    mock_doc.update.reset_mock()
    success = await ms.set_human_help_status(test_phone, True)
    
    if success:
        logger.info("✅ TEST 2: LOGIC PASSED")
    else:
        logger.error("❌ TEST 2: LOGIC FAILED")
        return False
        
    mock_doc.update.assert_called_with({
        "human_help_requested": True,
        "updated_at": ANY,
        "fecha": ANY
    })
    logger.info("✅ TEST 2: ASSERTION PASSED")

    # --- TEST 3: create_prospect_if_missing (New Prospect) ---
    logger.info("🧪 TEST 3: create_prospect_if_missing")
    mock_snap.exists = False # Simular que no existe
    mock_doc.set.reset_mock()
    await ms.create_prospect_if_missing(test_phone)
    
    # Verificar que se inicializa en PENDING
    call_args = mock_doc.set.call_args[0][0]
    if call_args.get("status") == "PENDING":
        logger.info("✅ TEST 3: PASSED (Status initial is PENDING)")
    else:
        logger.error(f"❌ TEST 3: FAILED (Expected PENDING, got {call_args.get('status')})")
        return False

    logger.info("\n🏆 CERTIFICACIÓN V9.8.3: TOTAL PASS")
    return True

if __name__ == "__main__":
    # Mock firestore.SERVER_TIMESTAMP
    try:
        from google.cloud import firestore
        firestore.SERVER_TIMESTAMP = MagicMock()
    except ImportError:
        # If firestore is not available during mock setup
        pass
    
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    result = loop.run_until_complete(run_test())
    if not result:
        sys.exit(1)
