import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Asegurar que el path del proyecto esté disponible
sys.path.append(os.getcwd())

from app.services.memory_service import MemoryService

async def test_create_prospect_initializes_pending_status():
    """
    [SYNC-CRM] Test que verifica que create_prospect_if_missing inicializa
    el estado en 'PENDING' para sincronía con el Dashboard.
    """
    mock_db = MagicMock()
    memory_service = MemoryService(db=mock_db)
    
    # Mock doc snapshot: prospect does not exist
    mock_doc_snap = MagicMock()
    mock_doc_snap.exists = False

    # Mock doc reference
    mock_doc_ref = AsyncMock()
    mock_doc_ref.get.return_value = mock_doc_snap
    mock_doc_ref.set = AsyncMock()

    # Mock session purge
    mock_session_ref = AsyncMock()
    mock_session_ref.delete = AsyncMock()

    def collection_side_effect(name):
        col_mock = MagicMock()
        if name == "prospectos":
            col_mock.document.return_value = mock_doc_ref
        elif name == "mensajeria":
            col_mock.document.return_value.collection.return_value.document.return_value = mock_session_ref
        return col_mock

    memory_service._db.collection.side_effect = collection_side_effect

    await memory_service.create_prospect_if_missing("3227303760")

    # Verify set() call
    mock_doc_ref.set.assert_called_once()
    data = mock_doc_ref.set.call_args[0][0]
    
    if data.get("status") == "PENDING":
        print("✅ create_prospect_if_missing inicializa en PENDING")
    else:
        raise AssertionError(f"❌ [REGRESSION] Prospecto debe iniciar en estado PENDING, se obtuvo: {data.get('status')}")

async def test_transition_pending_to_in_progress():
    """
    [ARCH-BULK-META-010] Test de transición atómica PENDING -> IN_PROGRESS.
    """
    mock_db = MagicMock()
    memory_service = MemoryService(db=mock_db)
    phone = "3227303760"
    
    # Mock doc snap WITH status PENDING
    mock_doc_snap = MagicMock()
    mock_doc_snap.exists = True
    mock_doc_snap.to_dict.return_value = {"status": "PENDING"}

    mock_doc_ref = AsyncMock()
    mock_doc_ref.get.return_value = mock_doc_snap
    mock_doc_ref.update = AsyncMock()

    # Mock _find_prospect_ref (used inside the method)
    memory_service._find_prospect_ref = AsyncMock(return_value=mock_doc_ref)

    result = await memory_service.transition_to_in_progress(phone)

    if result is True:
        mock_doc_ref.update.assert_called_once()
        update_data = mock_doc_ref.update.call_args[0][0]
        if update_data["status"] == "IN_PROGRESS":
            print("✅ transition_to_in_progress funciona correctamente (PENDING -> IN_PROGRESS)")
        else:
            raise AssertionError(f"❌ Status incorrecto: {update_data['status']}")
    else:
        raise AssertionError("❌ Transición falló (result is False)")

async def test_update_whatsapp_status_top_level_sync():
    """
    [SYNC-CRM] Test que verifica la sincronía de campos de nivel superior en whatsapp_status.
    """
    mock_db = MagicMock()
    memory_service = MemoryService(db=mock_db)
    phone = "3227303760"
    wamid = "ABC.123"
    errors = [{"message": "Account not registered", "code": 131030}]

    mock_doc_ref = AsyncMock()
    mock_doc_ref.update = AsyncMock()
    memory_service._find_prospect_ref = AsyncMock(return_value=mock_doc_ref)

    await memory_service.update_whatsapp_status(
        phone_number=phone,
        status_value="failed",
        wamid=wamid,
        errors=errors
    )

    mock_doc_ref.update.assert_called_once()
    data = mock_doc_ref.update.call_args[0][0]
    
    if data["whatsapp_delivery_status"] == "failed" and data["last_whatsapp_error"] == "Account not registered":
        print("✅ update_whatsapp_status sincroniza campos top-level y maneja errores")
    else:
        raise AssertionError(f"❌ Sincronía top-level falló. Data: {data}")

async def run_all():
    print("🚀 Iniciando validación de restauración de memoria v9.8.2...\n")
    try:
        await test_create_prospect_initializes_pending_status()
        await test_transition_pending_to_in_progress()
        await test_update_whatsapp_status_top_level_sync()
        print("\n🏆 TODAS LAS PRUEBAS PASARON EXITOSAMENTE (Score: 1.000)")
    except Exception as e:
        print(f"\n❌ ERROR EN LA VALIDACIÓN: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_all())
