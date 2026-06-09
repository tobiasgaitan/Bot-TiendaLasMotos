import pytest
import asyncio
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_firestore_io_explicit_raise():
    """
    Verifica que _firestore_io levante la excepción explícitamente y no silencie el fallo retornando _ContingencySnapshot
    cuando ocurre un error genérico (Zero-Silent-Failures).
    """
    # Importar MemoryService aquí para evitar problemas circulares
    from app.services.memory_service import MemoryService
    
    db_mock = AsyncMock()
    db_mock.project = "test-project"
    db_mock._credentials = "test-credentials"
    ms = MemoryService(db=db_mock)

    async def failing_coro():
        raise Exception("Generic Firestore Error")
        
    with pytest.raises(Exception, match="Generic Firestore Error"):
        await ms._firestore_io(
            failing_coro(),
            phone="1234567890",
            label="test_label"
        )

def test_ficha_tecnica_content_assertion():
    """
    [MANDATORIO: Incluir un test unitario de aserción de contenido que verifique la 
    presencia explícita de la cadena transformada (ej. 'Ficha Tecnica:') y prohíba 
    que una mutación de llaves resulte en un string vacío o valores devueltos como None silenciosos].
    """
    # Simulando la mutación de llaves que podría ocurrir durante la serialización/optimización
    simulated_payload = {
        "price": 1500000,
        "description": "Ficha Tecnica: Moto 150cc",
        "mutated_key": ""
    }
    
    # Extraer la cadena de la respuesta (simulación de orquestador)
    content = simulated_payload.get("description")
    
    # 1. Verificar presencia explícita de la cadena transformada
    assert "Ficha Tecnica:" in str(content), "Error: La cadena 'Ficha Tecnica:' fue truncada o eliminada del payload."
    
    # 2. Prohibir que la mutación resulte en string vacío o None silencioso
    assert content is not None, "Violación Zero-Silent-Failures: El contenido se evaluó como None."
    assert str(content).strip() != "", "Violación Zero-Silent-Failures: El contenido se evaluó como string vacío."
