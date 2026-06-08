import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.memory_service import MemoryService
from tests.conftest import AsyncStreamMock

@pytest.fixture
def memory_service():
    mock_db = MagicMock()
    return MemoryService(db=mock_db)


@pytest.mark.asyncio
async def test_create_prospect_initializes_habeas_data_accepted_false(memory_service):
    """
    Test que verifica que create_prospect_if_missing inicializa explícitamente
    habeas_data_accepted en False usando la llave canónica (v7.7.0).
    
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

    # Wire up _db.collection().document() chains
    def collection_side_effect(name):
        col_mock = MagicMock()
        if name == "prospectos":
            # Support both document-level and historial subcollection access
            doc_mock = MagicMock()
            doc_mock.get = mock_doc_ref.get
            doc_mock.set = mock_doc_ref.set
            # historial subcollection for clear_memory zombie purge
            historial_mock = MagicMock()
            historial_mock.stream.return_value = AsyncStreamMock([])
            doc_mock.collection.return_value = historial_mock
            col_mock.document.return_value = doc_mock
        return col_mock

    memory_service._db.collection.side_effect = collection_side_effect

    # Mock batch for clear_memory
    batch_mock = MagicMock()
    batch_mock.commit = AsyncMock()
    memory_service._db.batch.return_value = batch_mock

    await memory_service.create_prospect_if_missing("3227303760")

    # Verify set() was called with canonical keys
    mock_doc_ref.set.assert_called_once()
    call_args = mock_doc_ref.set.call_args
    data = call_args[0][0]  # positional arg

    # Canonical key (v7.7.0): habeas_data_accepted — NOT legacy 'habeas_data'
    assert "habeas_data_accepted" in data, "Must use canonical key 'habeas_data_accepted', not legacy alias"
    assert data["habeas_data_accepted"] is False, "habeas_data_accepted debe ser False al crear un prospecto"
    assert data["habeas_data_accepted_sent"] is False, "habeas_data_accepted_sent debe ser False al crear un prospecto"
    assert "3227303760" in data["celular"], "celular debe contener el número del prospecto"


def test_merge_after_reset_does_not_latch_true(memory_service):
    """
    Test que verifica que si el dato actual es False (post-reset), la IA no lo autocompleta como True.
    Uses canonical key 'habeas_data_accepted' (v7.7.0).
    """
    current_data = {
        "habeas_data_accepted": False,       # Estado explícito tras reset (canonical key)
        "habeas_data_accepted_sent": False
    }
    
    incoming_extracted = {
        "habeas_data_accepted": False        # Canonical key
    }
    
    merged = memory_service._merge_extracted_data(current_data, incoming_extracted)
    
    # Debe permanecer en False porque existing_val era False (no se activa el latch)
    assert merged["habeas_data_accepted"] is False


def test_merge_still_latches_true_if_already_true(memory_service):
    """
    Test de regresión: El latch debe seguir funcionando si el valor ya era True.
    Uses canonical key 'habeas_data_accepted' (v7.7.0).
    """
    current_data = {
        "habeas_data_accepted": True         # Canonical key — already accepted
    }
    incoming_extracted = {
        "habeas_data_accepted": False        # AI attempts to rollback — latch must block
    }
    merged = memory_service._merge_extracted_data(current_data, incoming_extracted)
    assert merged["habeas_data_accepted"] is True, "El latch debe mantener True si el valor existente era True"


@pytest.mark.asyncio
async def test_delete_prospect_completely_flow(memory_service):
    """
    Test que verifica el borrado completo del CRM (nuclear wipe).
    Debe limpiar memoria, borrar sesión y borrar el documento del prospecto.
    """
    phone = "3227303760"

    # Mock clear_memory
    memory_service.clear_memory = AsyncMock(return_value=True)
    
    # Setup document mocks for prospect
    mock_prospect_ref = MagicMock()
    mock_prospect_ref.id = "test_id"
    mock_prospect_ref.reference.delete = AsyncMock()
    mock_prospect_ref.delete = AsyncMock() # For direct document().delete() calls

    # prospectos_ref.where(...).get() mock
    mock_query = MagicMock()
    mock_query.get = AsyncMock(return_value=[mock_prospect_ref])

    def collection_side_effect(name):
        col_mock = MagicMock()
        if name == "prospectos":
            col_mock.where.return_value.limit.return_value = mock_query
            col_mock.document.return_value = mock_prospect_ref
        return col_mock

    memory_service._db.collection.side_effect = collection_side_effect
    
    # Execute
    result = await memory_service.delete_prospect_completely(phone)
    
    # Verify
    assert result is True
    memory_service.clear_memory.assert_called_once_with("+573227303760")
    mock_prospect_ref.reference.delete.assert_called_once()
