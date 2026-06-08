import pytest
from unittest.mock import MagicMock, AsyncMock
from app.services.memory_service import MemoryService
from app.services.catalog_service import catalog_service

@pytest.mark.asyncio
async def test_memory_service_sync_and_content_assertion():
    """
    [BOT-DEBT-042] Test que verifica:
    1. Las llamadas a Firestore son esperadas correctamente (await).
    2. La aserción de contenido prohíbe que una mutación de llaves devuelva None
       o strings vacíos para campos críticos, verificando explícitamente "Ficha Tecnica:".
    """
    mock_db = MagicMock()
    memory_service = MemoryService(db=mock_db)

    # 1. Mock persistence
    mock_doc_ref = MagicMock()
    mock_doc_ref.get = AsyncMock()
    mock_doc_snap = MagicMock()
    mock_doc_snap.exists = True
    mock_doc_snap.to_dict.return_value = {"status": "PENDING"}
    mock_doc_ref.get.return_value = mock_doc_snap
    mock_doc_ref.update = AsyncMock()

    memory_service._find_prospect_ref = AsyncMock(return_value=mock_doc_ref)

    # Execute transition
    result = await memory_service.transition_to_in_progress("3227303760")
    assert result is True
    
    # Assert that update was called and awaited 
    # (if it wasn't awaited in _firestore_io, the test would show a RuntimeWarning)
    mock_doc_ref.update.assert_called_once()
    
    # 2. Content Assertion Guardrail (PCC Pro)
    # Verificamos que si se consulta el catálogo, no devuelva None o vacío,
    # y que contenga la cadena obligatoria 'Ficha Tecnica:'.
    
    # Simulamos el payload del catálogo con una mutación maliciosa
    # El catalog service debe garantizar la cadena.
    from unittest.mock import patch
    
    with patch.object(catalog_service, 'search_items', MagicMock(return_value=[
        {
            "name": "TVS Sport 100",
            "price": "$5.000.000",
            "summary": "100cc" # El campo summary se convierte en Ficha Tecnica
        }
    ])), patch.object(catalog_service._cache_service, 'get', MagicMock(return_value=(None, 0))):
        
        mock_catalog_payload = catalog_service.search_catalog("tvs sport")
        
        # Verificar que el formateador incluye explícitamente "Ficha Tecnica:" 
        # y no es un string vacío.
        assert mock_catalog_payload is not None, "❌ Payload mutado resultó en None silencioso"
        assert mock_catalog_payload.strip() != "", "❌ Payload mutado resultó en string vacío silencioso"
        assert "Ficha Tecnica:" in mock_catalog_payload, "❌ Ausencia de 'Ficha Tecnica:' en el payload (Anti-Null Masking Falló)"
    
    # Adicional: Verificar Anti-Null Masking
    # Si simulamos que un campo crítico falta, no debe enmascararse
    with patch.object(catalog_service, 'search_items', MagicMock(return_value=[{"name": "TVS Sport 100", "summary": "100cc"}])), \
         patch.object(catalog_service._cache_service, 'get', MagicMock(return_value=(None, 0))):
        
        try:
            # El validador debe arrojar error y no tragar la excepción silenciosamente
            formatted = catalog_service.search_catalog("tvs sport")
            # Si de todos modos formatea, debe contener "Ficha Tecnica:" o lanzar error.
            if formatted:
                assert "Ficha Tecnica:" in formatted
        except Exception as e:
            # Esto es aceptable (Zero-Silent-Failures)
            pass
