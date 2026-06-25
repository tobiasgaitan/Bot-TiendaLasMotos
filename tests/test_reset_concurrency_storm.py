import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.memory_service import MemoryService

@pytest.mark.asyncio
async def test_reset_concurrency_storm_and_metadata_fluidity():
    """
    [BOT-QA-LOOP-108] Test de estrés de concurrencia real.
    Verifica que una ráfaga de acuses de recibo (Meta API) inmediatamente posterior
    a un wipe nuclear (/reset) no aborte la inicialización ni genere strings vacíos
    o valores devueltos como None silenciosos en las llaves del CRM.
    """
    mock_db = MagicMock()
    memory_service = MemoryService(db=mock_db)
    phone = "+573192564288"
    
    # Simular que el documento fue borrado (exists = False)
    mock_doc_snap = MagicMock()
    mock_doc_snap.exists = False
    mock_doc_snap.to_dict.return_value = {}
    
    mock_doc_ref = AsyncMock()
    mock_doc_ref.get = AsyncMock(return_value=mock_doc_snap)
    mock_doc_ref.set = AsyncMock()
    
    memory_service._find_prospect_ref = AsyncMock(return_value=mock_doc_ref)
    memory_service.create_prospect_if_missing = AsyncMock()
    
    # Simular ráfaga concurrente de acuses (sent, delivered, read) en paralelo
    tasks = [
        memory_service.update_whatsapp_status(phone, "sent", "wamid.1"),
        memory_service.update_whatsapp_status(phone, "delivered", "wamid.2"),
        memory_service.update_whatsapp_status(phone, "read", "wamid.3")
    ]
    
    # Ejecución paralela pura
    await asyncio.gather(*tasks)
    
    # ASERCIONES RÍGIDAS DE CONTRATO DE PERSISTENCIA
    assert mock_doc_ref.set.call_count > 0, "❌ Error: No se forzó la persistencia atómica vía set con merge."
    
    # Extraer las llamadas reales enviadas a Firestore
    for call in mock_doc_ref.set.call_args_list:
        payload = call[0][0]
        # El payload de recuperación ante borrado nuclear DEBE contener las llaves mínimas canónicas del CRM
        assert payload.get("chatbot_status") == "ACTIVE", "❌ Regresión: chatbot_status no fue inicializado en ACTIVE."
        assert payload.get("status") == "PENDING", "❌ Regresión: status de nivel superior no fue anclado en PENDING."
        assert payload.get("celular") is not None, "❌ Regresión: La llave celular es None o string vacío."
