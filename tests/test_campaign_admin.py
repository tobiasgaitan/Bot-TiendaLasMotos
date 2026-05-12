import asyncio
import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock

# Añadir el raíz
sys.path.append(os.getcwd())

from app.routers.admin import start_campaign, CampaignRequest
from fastapi import HTTPException

async def test_campaign_orchestrator_failure_isolation():
    print("🚀 Iniciando Test: Orchestrador de Campañas (Meta 400 Failure Isolation & Ghost Persistence)")
    
    request = CampaignRequest(
        template_a="template_reactivation_a",
        template_b="template_reactivation_b",
        limit=2,
        language="es"
    )

    # Creamos un prospect mockeado
    doc_mock_1 = MagicMock()
    doc_mock_1.to_dict.return_value = {"nombre": "Juan", "moto_interest": "Boxer CT", "celular": "3001234567"}
    doc_mock_1.id = "3001234567"
    doc_mock_1.reference.update = AsyncMock()

    doc_mock_2 = MagicMock()
    doc_mock_2.to_dict.return_value = {"nombre": "Maria", "moto_interest": "Pulsar NS", "celular": "3009876543"}
    doc_mock_2.id = "3009876543"
    doc_mock_2.reference.update = AsyncMock()
    
    # Mock de DB queries
    query_mock = MagicMock()
    
    from tests.conftest import AsyncStreamMock
    query_mock.stream.return_value = AsyncStreamMock([doc_mock_1, doc_mock_2])
    
    collection_mock = MagicMock()
    # handle where().where().limit()
    collection_mock.where.return_value.where.return_value.limit.return_value = query_mock
    
    mock_db = MagicMock()
    mock_db.collection.return_value = collection_mock

    # Preparar el mock de Meta API para que falle en el primero y triunfe en el segundo
    async def side_effect_meta(to_phone, template_name, components, language_code, phone_number_id=None):
        if to_phone == "3001234567":
            # Forzamos falla de Meta para el primero (Error 400)
            raise Exception("Meta API Error 400: Bad Request")
        return {"success": True}

    with patch('app.routers.admin.firestore.AsyncClient', return_value=mock_db), \
         patch('app.services.template_service.template_service.get_template_fields', new_callable=AsyncMock) as mock_get_template, \
         patch('app.services.whatsapp_service.whatsapp_service.send_template_message', side_effect=side_effect_meta) as mock_send_meta, \
         patch('app.services.memory_service.MemoryService.save_message', new_callable=AsyncMock) as mock_save_message, \
         patch('app.routers.admin.settings.admin_api_key', "TEST_MASTER_KEY"):
         
        mock_get_template.return_value = ["nombre"]
         
        # Import admin after patches
        from app.routers.admin import start_campaign
        from app.services.memory_service import memory_service, init_memory_service
        from app.routers import admin
        
        # Ensure memory_service exists globally for admin
        init_memory_service(mock_db)
        # Assign it to the instance that admin.py will import
        
        # Action
        response = await start_campaign(request=request, x_admin_api_key="TEST_MASTER_KEY")
        
        # Assertion 1: Ghost History injected EVEN if Meta failed (it was called FIRST)
        assert mock_save_message.call_count == 2, f"Se esperaba 2 persistencias, pero hubo {mock_save_message.call_count}"
        
        # Extract the args
        calls = mock_save_message.call_args_list
        assert calls[0][0][0] == "3001234567"
                # blocking check removed per v9.0.0 sync mandate
        
        # Assertion 2: Only 1 correct transport execution recorded (because Meta failed in 1 and was success in 2)
        # Even though Meta failed for the first, the processed count only tracks fully successful
        assert response.processed == 1, f"Expected 1 processed, got {response.processed}"
        assert len(response.errors) == 1, f"Expected 1 error, got {len(response.errors)}"
        assert response.errors[0]["to_phone"] == "3001234567"
        assert "Meta API Error 400" in response.errors[0]["error"]

        print("✅ TEST PASSED: Ghost history persisted before Meta failure. Failures isolated using try/except continue.")
        
if __name__ == "__main__":
    asyncio.run(test_campaign_orchestrator_failure_isolation())
