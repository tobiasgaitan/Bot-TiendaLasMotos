import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.catalog_service import CatalogService
from app.services.ai_brain import CerebroIA

@pytest.mark.asyncio
async def test_drift_alias_bypass_senoritera_cold_start():
    """
    Evaluates 'señoritera' under Cold Start preconditions.
    The query 'señoritera' is an alias of 'moto semiautomatica'.
    The bypass should succeed and skip_catalog must be False (calls catalog search).
    """
    # 1. Fresh instantiation (Cold Start)
    catalog_service = CatalogService()
    cerebro = CerebroIA(catalog_service=catalog_service)
    
    # 2. Configure aliases dynamically (using lowercase keys as per strict normalization)
    mock_aliases = {"moto semiautomatica": ["señoritera", "moped"]}
    catalog_service._category_aliases = mock_aliases
    
    # 3. Mock dependencies of Think Response
    prospect_data = {
        "exists": True,
        "moto_interest": "moto semiautomatica",
        "nombre": "Test User",
        "ciudad": "Cali",
        "forma_pago": "Crédito"
    }
    
    # Mock Gemini response returning tool call to search_catalog with query 'señoritera'
    with patch.object(cerebro, '_call_gemini_with_retry_async', new_callable=AsyncMock) as mocked_call:
        mock_response_1 = MagicMock()
        mock_fc = MagicMock()
        mock_fc.name = "search_catalog"
        mock_fc.args = {"query": "señoritera"}
        mock_part_1 = MagicMock(function_call=mock_fc, text=None)
        mock_response_1.candidates = [MagicMock(content=MagicMock(parts=[mock_part_1]))]
        
        mock_response_2 = MagicMock()
        mock_part_2 = MagicMock(function_call=None, text="La señoritera cuesta $7.000.000. ![Scooter](https://img.url) Ficha Tecnica: Excelente moto")
        mock_response_2.candidates = [MagicMock(content=MagicMock(parts=[mock_part_2]))]
        
        mocked_call.side_effect = [mock_response_1, mock_response_2]
        
        # Mock search_items in catalog_service to return a valid item
        mock_item = {
            "name": "Victory Flow",
            "price": "$7.000.000 (incluye SOAT, Matrícula, y tramites)",
            "category": "moto semiautomatica",
            "image_url": "https://img.url",
            "summary": "Excelente moto"
        }
        with patch.object(catalog_service, 'search_items', return_value=[mock_item]) as mock_search:
            # Execute
            await cerebro.pensar_respuesta("quiero ver la señoritera", prospect_data=prospect_data)
            
            # Assertions: the bypass happened, catalog search was called for 'señoritera'
            assert mock_search.called, "Bypass failed: catalog_service.search_items was not called for 'señoritera'."
            assert mock_search.call_args[0][0] == "señoritera"


@pytest.mark.asyncio
async def test_drift_alias_blocked_senoriter_cold_start():
    """
    Evaluates 'señoriter' under Cold Start preconditions.
    The query 'señoriter' is not in the aliases list, and its difflib similarity to
    'moto semiautomatica' is 0.2857 (< 0.30).
    It must be blocked by the Drift Interceptor (skip_catalog = True).
    """
    # 1. Fresh instantiation (Cold Start)
    catalog_service = CatalogService()
    cerebro = CerebroIA(catalog_service=catalog_service)
    
    # 2. Configure aliases dynamically (using lowercase keys as per strict normalization)
    mock_aliases = {"moto semiautomatica": ["señoritera", "moped"]}
    catalog_service._category_aliases = mock_aliases
    
    # 3. Mock dependencies of Think Response
    prospect_data = {
        "exists": True,
        "moto_interest": "moto semiautomatica",
        "nombre": "Test User",
        "ciudad": "Cali",
        "forma_pago": "Crédito"
    }
    
    # Mock Gemini response returning tool call to search_catalog with query 'señoriter'
    with patch.object(cerebro, '_call_gemini_with_retry_async', new_callable=AsyncMock) as mocked_call:
        mock_response_1 = MagicMock()
        mock_fc = MagicMock()
        mock_fc.name = "search_catalog"
        mock_fc.args = {"query": "señoriter"}
        mock_part_1 = MagicMock(function_call=mock_fc, text=None)
        mock_response_1.candidates = [MagicMock(content=MagicMock(parts=[mock_part_1]))]
        
        mock_response_2 = MagicMock()
        mock_part_2 = MagicMock(function_call=None, text="Te recomiendo la moto semiautomatica.")
        mock_response_2.candidates = [MagicMock(content=MagicMock(parts=[mock_part_2]))]
        
        mocked_call.side_effect = [mock_response_1, mock_response_2]
        
        with patch.object(catalog_service, 'search_items', return_value=[]) as mock_search:
            # Execute
            await cerebro.pensar_respuesta("quiero ver la señoriter", prospect_data=prospect_data)
            
            # Assertions: the drift interceptor blocked the search, so search_items was NOT called
            assert not mock_search.called, "Security violation: catalog_service.search_items was called for 'señoriter' which should be blocked."
