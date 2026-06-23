import pytest
import re
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.ai_brain import CerebroIA
from app.services.catalog_service import catalog_service
from app.services.config_service import config_service

@pytest.mark.asyncio
async def test_pensar_respuesta_with_none_prospect_data(cerebro_mock):
    """
    Verifica que pensar_respuesta se ejecute limpiamente sin AttributeError
    cuando prospect_data es None (Cold Start / pruebas aisladas).
    """
    with patch.object(cerebro_mock, '_call_gemini_with_retry_async', new_callable=AsyncMock) as mocked_call:
        mock_response = MagicMock()
        mock_part = MagicMock()
        mock_part.text = "Hola! Soy Juan Pablo. ¿En qué puedo ayudarte?"
        mock_part.function_call = None
        mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
        mocked_call.return_value = mock_response
        
        # Debe ejecutarse sin lanzar AttributeError
        res = await cerebro_mock.pensar_respuesta("Hola", prospect_data=None)
        assert res is not None
        assert "Juan Pablo" in res

@pytest.mark.asyncio
async def test_pcc_ficha_tecnica_content_assertion():
    """
    Verifica que la cadena 'Ficha Tecnica:' esté presente y no devuelva 
    strings vacíos o 'None' silenciosos debido a mutación de llaves,
    cumpliendo con la validación de integridad del Price Consistency Check (PCC).
    """
    mock_item = {
        "id": "1",
        "name": "Moto Ghost",
        "price": 5000000,
        "cc": 125,
        "category": "Urban",
        "image_url": "http://img.url",
        "link": "http://link.url",
        "description": "Excelente moto urbana.",
        "summary": "Excelente moto urbana."
    }
    
    with patch.object(catalog_service, '_items', [mock_item]), \
         patch.object(catalog_service, '_db', MagicMock()), \
         patch.object(config_service, '_financial_config', None), \
         patch.object(config_service, 'get_registration_cost', return_value=0):
        
        catalog_service.load_configurations = MagicMock()
        catalog_service._cache_service.clear()
        
        res = catalog_service.search_catalog("Ghost")
        assert "Ficha Tecnica:" in res, "La cadena transformada 'Ficha Tecnica:' debe estar presente."
        
        match = re.search(r"Ficha Tecnica:\s*(.*)", res)
        assert match is not None, "Debe existir la sección Ficha Tecnica."
        val = match.group(1).strip()
        assert val != "", "El contenido de Ficha Tecnica no puede estar vacío."
        assert val != "None", "El contenido de Ficha Tecnica no puede ser None silencioso."
