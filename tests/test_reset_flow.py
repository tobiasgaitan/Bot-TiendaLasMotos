import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.memory_service import MemoryService

@pytest.fixture
def memory_service():
    mock_db = MagicMock()
    return MemoryService(db=mock_db)


@pytest.mark.asyncio
async def test_create_prospect_initializes_habeas_data_false(memory_service):
    """
    Test que verifica que create_prospect_if_missing inicializa explícitamente
    habeas_data en False usando la llave canónica (v7.7.0).
    
    WHY async: create_prospect_if_missing es un coroutine — llamarlo sin await
    no ejecuta el código interno y el set() nunca se llama.
    """
    # Mock doc snapshot: prospect does not exist yet
    mock_doc_snap = MagicMock()
    mock_doc_snap.exists = False

    # Mock doc reference with async get()
    mock_doc_ref = AsyncMock()
    mock_doc_ref.get.return_value = mock_doc_snap
    mock_doc_ref.set = AsyncMock()

    # Mock zombie session purge (mensajeria path)
    mock_session_ref = AsyncMock()
    mock_session_ref.delete = AsyncMock()

    # Wire up _db.collection().document() chains
    def collection_side_effect(name):
        col_mock = MagicMock()
        if name == "prospectos":
            col_mock.document.return_value = mock_doc_ref
        elif name == "mensajeria":
            # mensajeria/whatsapp/sesiones/{phone}
            col_mock.document.return_value.collection.return_value.document.return_value = mock_session_ref
        return col_mock

    memory_service._db.collection.side_effect = collection_side_effect

    await memory_service.create_prospect_if_missing("3227303760")

    # Verify set() was called with canonical keys
    mock_doc_ref.set.assert_called_once()
    call_args = mock_doc_ref.set.call_args
    data = call_args[0][0]  # positional arg

    # Canonical key (v7.7.0): habeas_data — NOT habeas_data_accepted
    assert "habeas_data" in data, "Must use canonical key 'habeas_data', not legacy alias"
    assert data["habeas_data"] is False, "habeas_data debe ser False al crear un prospecto"
    assert data["habeas_data_sent"] is False, "habeas_data_sent debe ser False al crear un prospecto"
    assert "3227303760" in data["celular"], "celular debe contener el número del prospecto"


def test_merge_after_reset_does_not_latch_true(memory_service):
    """
    Test que verifica que si el dato actual es False (post-reset), la IA no lo autocompleta como True.
    Uses canonical key 'habeas_data' (v7.7.0).
    """
    current_data = {
        "habeas_data": False,       # Estado explícito tras reset (canonical key)
        "habeas_data_sent": False
    }
    
    incoming_extracted = {
        "habeas_data": False        # Canonical key
    }
    
    merged = memory_service._merge_extracted_data(current_data, incoming_extracted)
    
    # Debe permanecer en False porque existing_val era False (no se activa el latch)
    assert merged["habeas_data"] is False


def test_merge_still_latches_true_if_already_true(memory_service):
    """
    Test de regresión: El latch debe seguir funcionando si el valor ya era True.
    Uses canonical key 'habeas_data' (v7.7.0).
    """
    current_data = {
        "habeas_data": True         # Canonical key — already accepted
    }
    incoming_extracted = {
        "habeas_data": False        # AI attempts to rollback — latch must block
    }
    merged = memory_service._merge_extracted_data(current_data, incoming_extracted)
    assert merged["habeas_data"] is True, "El latch debe mantener True si el valor existente era True"
