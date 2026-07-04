import pytest
import re
import traceback
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ai_brain import CerebroIA
from app.services.catalog_service import catalog_service

class MockFunctionCall:
    def __init__(self, name, args):
        self.name = name
        self.args = args

class MockPart:
    def __init__(self, function_call=None, text=None):
        self.function_call = function_call
        self.text = text

class MockContent:
    def __init__(self, parts):
        self.parts = parts

class MockCandidate:
    def __init__(self, content):
        self.content = content

class MockResponse:
    def __init__(self, candidates):
        self.candidates = candidates

@pytest.mark.asyncio
async def test_fallback_price_parsing():
    """
    Test Case 1:
    - raw_price is missing/None in the catalog.
    - price contains formatted price string like '$ 6.200.000'.
    - Assert that ai_brain parses it perfectly to 6200000.0 and calls calculate_payment.
    """
    cerebro = CerebroIA()
    cerebro.client = MagicMock()
    cerebro._model_id = "gemini-2.0-flash"
    
    # Mock catalog service
    mock_catalog = MagicMock()
    mock_catalog.search_items.return_value = [
        {
            "name": "TVS Sport 100",
            "price": "$ 6.200.000 (incluye SOAT, Matrícula)",
            "raw_price": None,
            "formatted_price": "$ 6.200.000",
            "category": "Urban",
            "image_url": "https://img.url",
            "summary": "Excelente moto"
        }
    ]
    cerebro._catalog_service = mock_catalog
    
    # Mock financial motor
    mock_financial = MagicMock()
    mock_financial.evaluate_profile.return_value = {
        "score": 750,
        "strategy": "Aprobado",
        "entity": "Crediorbe",
        "link_url": "https://crediorbe.link"
    }
    mock_financial.calculate_payment.return_value = {
        "cuota_mensual": 250000
    }
    cerebro.motor_financiero = mock_financial
    
    # Mock LLM calls
    fc = MockFunctionCall(name="calculate_credit_score", args={})
    candidate1 = MockCandidate(content=MockContent(parts=[MockPart(function_call=fc)]))
    response1 = MockResponse(candidates=[candidate1])
    
    candidate2 = MockCandidate(content=MockContent(parts=[MockPart(text="Felicidades, tienes crédito pre-aprobado.")]))
    response2 = MockResponse(candidates=[candidate2])
    
    call_count = 0
    async def mock_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return response1
        return response2
        
    with patch.object(cerebro, '_call_gemini_with_retry_async', new=mock_call), \
         patch('app.services.ai_brain.SDK_AVAILABLE', True):
         
        prospect = {
            "nombre": "Pedro",
            "moto_interest": "TVS Sport 100",
            "ciudad": "Cali",
            "forma_pago": "Crédito",
            "habeas_data_accepted": True
        }
        res = await cerebro.pensar_respuesta("Quiero saber mi crédito", prospect_data=prospect)
        
        # Verify that search_items was called
        mock_catalog.search_items.assert_called_with("TVS Sport 100")
        
        # Verify that calculate_payment was called with correct parsed price (6200000.0)
        mock_financial.calculate_payment.assert_called_once_with(
            precio=6200000.0,
            inicial=0,
            plazo_meses=24,
            entidad="Crediorbe"
        )
        
        assert res == "Felicidades, tienes crédito pre-aprobado."

@pytest.mark.asyncio
async def test_missing_both_prices_raises_error():
    """
    Test Case 2:
    - Both raw_price and price are missing or empty.
    - Assert that a controlled ValueError is raised, a warning log is recorded with the traceback,
      and it does NOT silently fail (we see the traceback inside log/exception).
    """
    cerebro = CerebroIA()
    cerebro.client = MagicMock()
    cerebro._model_id = "gemini-2.0-flash"
    
    # Mock catalog service to return item with no price keys
    mock_catalog = MagicMock()
    mock_catalog.search_items.return_value = [
        {
            "name": "TVS Sport 100",
            "category": "Urban",
            "image_url": "https://img.url",
            "summary": "Excelente moto"
        }
    ]
    cerebro._catalog_service = mock_catalog
    
    # Mock financial motor
    mock_financial = MagicMock()
    mock_financial.evaluate_profile.return_value = {
        "score": 750,
        "strategy": "Aprobado",
        "entity": "Crediorbe",
        "link_url": "https://crediorbe.link"
    }
    cerebro.motor_financiero = mock_financial
    
    # We patch _call_gemini_with_retry_async
    fc = MockFunctionCall(name="calculate_credit_score", args={})
    candidate1 = MockCandidate(content=MockContent(parts=[MockPart(function_call=fc)]))
    response1 = MockResponse(candidates=[candidate1])
    
    candidate2 = MockCandidate(content=MockContent(parts=[MockPart(text="Final reply")]))
    response2 = MockResponse(candidates=[candidate2])
    
    call_count = 0
    async def mock_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return response1
        return response2
        
    with patch.object(cerebro, '_call_gemini_with_retry_async', new=mock_call), \
         patch('app.services.ai_brain.SDK_AVAILABLE', True), \
         patch('app.services.ai_brain.logger.warning') as mock_log_warn, \
         patch('app.services.ai_brain.logger.exception') as mock_log_exception:
         
        prospect = {
            "nombre": "Pedro",
            "moto_interest": "TVS Sport 100",
            "ciudad": "Cali",
            "forma_pago": "Crédito",
            "habeas_data_accepted": True
        }
        
        await cerebro.pensar_respuesta("Quiero saber mi crédito", prospect_data=prospect)
        
        # Verify that warning was logged indicating null masking detection with traceback
        mock_log_warn.assert_called()
        warn_args = [call[0][0] for call in mock_log_warn.call_args_list]
        assert any("[NULL MASKING DETECTED]" in arg for arg in warn_args)
        assert any("Traceback" in arg for arg in warn_args)
        
        # Verify that the controlled ValueError was raised and caught by the outer try-except block,
        # logging a logger.exception with the correct description
        mock_log_exception.assert_called()
        exc_args = [call[0][0] for call in mock_log_exception.call_args_list]
        assert any("Credit error" in arg for arg in exc_args)

def test_catalog_retains_ficha_tecnica():
    """
    Test Case 3:
    - Verify using regular expressions that catalog_service.search_catalog contains 'Ficha Tecnica:'
      and that the payload summary is not empty or missing.
    """
    # Mock firestore/items inside catalog_service to return a test item with summary
    from app.services.config_service import config_service
    with patch.object(catalog_service, '_items', [
        {
            "id": "1",
            "name": "TVS Sport 100",
            "price": 6000000,
            "cc": 100,
            "category": "Urban",
            "image_url": "https://img.url",
            "link": "https://link.url",
            "description": "Moto económica de 100cc ideal para el trabajo diario."
        }
    ]), patch.object(catalog_service, '_db', MagicMock()), \
         patch.object(config_service, '_financial_config', None), \
         patch.object(config_service, 'get_registration_cost', return_value=0):
        
        catalog_service.load_configurations = MagicMock()
        catalog_service._cache_service.clear()
        
        # Perform a search
        res = catalog_service.search_catalog("TVS Sport")
        
        # Assert that "Ficha Tecnica:" is present and matches the pattern
        assert "Ficha Tecnica:" in res
        
        # Validate using regex that "Ficha Tecnica:" has a non-empty summary content following it
        match = re.search(r"Ficha Tecnica:\s*(.+)", res)
        assert match is not None
        summary_text = match.group(1).strip()
        assert len(summary_text) > 0
        assert "Moto" in summary_text

@pytest.mark.asyncio
async def test_search_catalog_tool_execution_retains_ficha_tecnica():
    """
    Test Case 4:
    - Verify that executing the search_catalog tool inside CerebroIA.pensar_respuesta
      uses search_items, and the tool output (search_results) formatted into response_parts
      contains 'Ficha Tecnica:' and the payload summary.
    """
    cerebro = CerebroIA()
    cerebro.client = MagicMock()
    cerebro._model_id = "gemini-2.0-flash"
    
    # Mock catalog service
    mock_catalog = MagicMock()
    mock_catalog.search_items.return_value = [
        {
            "name": "Victory Life",
            "price": "$ 5.800.000",
            "category": "Scooter",
            "image_url": "https://img.url/life",
            "summary": "Excelente scooter para ciudad"
        }
    ]
    cerebro._catalog_service = mock_catalog
    
    # Mock LLM calls
    fc = MockFunctionCall(name="search_catalog", args={"query": "Victory Life"})
    candidate1 = MockCandidate(content=MockContent(parts=[MockPart(function_call=fc)]))
    response1 = MockResponse(candidates=[candidate1])
    
    # Second turn reply
    candidate2 = MockCandidate(content=MockContent(parts=[MockPart(text="La Victory Life es perfecta. Vale $5.800.000 y puedes verla aquí: ![Life](https://img.url/life) Ficha Tecnica: Excelente moto.")]))
    response2 = MockResponse(candidates=[candidate2])
    
    call_count = 0
    captured_response_parts = None
    
    async def mock_call(*args, **kwargs):
        nonlocal call_count, captured_response_parts
        call_count += 1
        if call_count == 1:
            return response1
        # Intercept the second call arguments to inspect the response_parts
        captured_response_parts = args[1]
        return response2
        
    with patch.object(cerebro, '_call_gemini_with_retry_async', new=mock_call), \
         patch('app.services.ai_brain.SDK_AVAILABLE', True):
         
        prospect = {
            "nombre": "Sofia",
            "ciudad": "Medellín",
            "forma_pago": "Contado"
        }
        await cerebro.pensar_respuesta("Quiero información de la Victory Life", prospect_data=prospect)
        
        # Verify search_items was called
        mock_catalog.search_items.assert_called_once_with("Victory Life")
        
        # Verify that response_parts contains the tool output with Ficha Tecnica
        assert captured_response_parts is not None
        assert len(captured_response_parts) == 1
        
        # The part response is under .function_response.response
        part = captured_response_parts[0]
        part_result = part.function_response.response.get("result", "")
        
        assert "Ficha Tecnica:" in part_result
        assert "Excelente scooter para ciudad" in part_result


@pytest.mark.asyncio
async def test_search_catalog_tool_execution_raises_error_on_missing_critical_keys():
    """
    Test Case 5 (Updated BOT-RESILIENCE-102):
    - Verify that if the catalog matches are missing critical keys like name or price,
      a logger.warning is emitted with NULL MASKING DETECTED tag, and the item is SKIPPED.
    """
    cerebro = CerebroIA()
    cerebro.client = MagicMock()
    cerebro._model_id = "gemini-2.0-flash"
    
    # Mock catalog service to return item with no name key (which is critical)
    mock_catalog = MagicMock()
    mock_catalog.search_items.return_value = [
        {
            "price": "$ 6.200.000",
            "category": "Urban",
            "summary": "Excelente moto"
            # name is missing!
        }
    ]
    cerebro._catalog_service = mock_catalog
    
    # Mock LLM calls
    fc = MockFunctionCall(name="search_catalog", args={"query": "TVS Sport"})
    candidate1 = MockCandidate(content=MockContent(parts=[MockPart(function_call=fc)]))
    response1 = MockResponse(candidates=[candidate1])
    
    call_count = 0
    async def mock_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return response1
        
    with patch.object(cerebro, '_call_gemini_with_retry_async', new=mock_call), \
         patch('app.services.ai_brain.SDK_AVAILABLE', True), \
         patch('app.services.ai_brain.logger.warning') as mock_log_warn:
         
        prospect = {
            "nombre": "Pedro",
            "ciudad": "Cali",
            "forma_pago": "Crédito"
        }
        
        # Call thinking logic — MUST NOT crash
        await cerebro.pensar_respuesta("Muéstrame la TVS Sport", prospect_data=prospect)
        
        # Verify that logger.warning (NOT exception) was called
        # with NULL MASKING DETECTED tag, indicating the corrupted item was skipped
        mock_log_warn.assert_called()
        warn_args = [call[0][0] for call in mock_log_warn.call_args_list]
        assert any("NULL MASKING DETECTED" in arg for arg in warn_args), \
            "logger.warning DEBE contener '[NULL MASKING DETECTED]' indicando ítem omitido"
