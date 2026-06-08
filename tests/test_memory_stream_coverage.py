import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.memory_service import MemoryService
from tests.conftest import AsyncStreamMock

@pytest.mark.asyncio
async def test_clear_memory_batch_execution():
    """
    Valida que clear_memory itere correctamente sobre el stream() 
    y ejecute las eliminaciones en un batch de Firestore.
    Ruta real: prospectos/[phone]/historial
    """
    mock_db = MagicMock()
    ms = MemoryService(db=mock_db)
    
    phone_number = "573001234567"
    
    # Mock de documentos a eliminar
    doc_1 = MagicMock()
    doc_1.reference = MagicMock()
    doc_2 = MagicMock()
    doc_2.reference = MagicMock()
    
    # Mock del flujo de Firestore
    stream_mock = AsyncStreamMock([doc_1, doc_2])
    
    # Mock de la cadena de colecciones: db.collection().document().collection().document().collection()
    # history_ref.stream()
    historial_collection_mock = MagicMock()
    historial_collection_mock.stream.return_value = stream_mock
    
    # Configuramos la ruta: collection("prospectos").document(phone).collection("historial")
    mock_db.collection.return_value.document.return_value.collection.return_value = historial_collection_mock
    
    # Mock del batch
    batch_mock = MagicMock()
    batch_mock.commit = AsyncMock()
    mock_db.batch.return_value = batch_mock
    
    success = await ms.clear_memory(phone_number)
    
    assert success is True
    # Debe haber llamado a delete para cada documento
    assert batch_mock.delete.call_count == 2
    # Debe haber hecho commit (una vez en el loop si >=400, y una vez al final)
    # En este caso 2 docs < 400, así que llama commit al final.
    batch_mock.commit.assert_called_once()

@pytest.mark.asyncio
async def test_get_chat_history_stream_iteration():
    """
    Valida que get_chat_history recupere los documentos del stream()
    y los transforme correctamente en una lista de diccionarios.
    """
    mock_db = MagicMock()
    ms = MemoryService(db=mock_db)
    
    phone_number = "573001234567"
    
    # Mock de documentos con datos
    doc_1 = MagicMock()
    doc_1.to_dict.return_value = {"role": "user", "content": "Hola", "timestamp": 1000}
    doc_2 = MagicMock()
    doc_2.to_dict.return_value = {"role": "assistant", "content": "¿Cómo estás?", "timestamp": 2000}
    
    stream_mock = AsyncStreamMock([doc_2, doc_1])
    
    # Mock de la consulta
    query_mock = MagicMock()
    query_mock.stream.return_value = stream_mock
    
    historial_collection_mock = MagicMock()
    historial_collection_mock.order_by.return_value.limit.return_value = query_mock
    
    # Configuramos la ruta: collection("prospectos").document(phone).collection("historial")
    mock_db.collection.return_value.document.return_value.collection.return_value = historial_collection_mock
    
    history = await ms.get_chat_history(phone_number, limit=10)
    
    assert len(history) == 2
    assert history[0]["content"] == "Hola"
    assert history[1]["content"] == "¿Cómo estás?"
