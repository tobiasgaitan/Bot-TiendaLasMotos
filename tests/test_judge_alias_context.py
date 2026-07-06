import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.routers.whatsapp import resolve_query_aliases
from app.services.judge_service import JudgeService

def test_resolve_query_aliases():
    # Mock catalog service
    mock_catalog = MagicMock()
    mock_catalog.get_catalog_aliases.return_value = {
        "semiautomatica": ["señoritera", "moped"],
        "scooter": ["automatica"]
    }
    
    # Exact synonym match
    assert resolve_query_aliases("señoritera", mock_catalog) == "semiautomatica"
    
    # Word boundary match within sentence
    assert resolve_query_aliases("quiero ver la señoritera por favor", mock_catalog) == "semiautomatica"
    
    # Case insensitivity
    assert resolve_query_aliases("SEÑORITERA", mock_catalog) == "semiautomatica"
    
    # No match returns original query
    assert resolve_query_aliases("quiero una sport", mock_catalog) == "quiero una sport"


@pytest.mark.asyncio
async def test_judge_catalog_context_construction_and_evaluation():
    """
    Test that the catalog_context constructed for the Judge Service
    contains both Neto and Con SOAT prices for Victory Advance X1,
    and that the Judge is called with this aligned context.
    """
    mock_catalog = MagicMock()
    
    # Raw items loaded from database
    mock_raw_item = {
        "name": "Victory Advance X1",
        "price": 7100000.0,
        "formatted_price": "$7.100.000",
        "category": "semiautomatica",
        "searchBy": ["semiautomatica", "señoritera", "advance"],
        "summary": "Excelente moto semiautomatica de 115cc."
    }
    mock_catalog._items = [mock_raw_item]
    
    # Truncated item returned by search()
    mock_search_result = {
        "name": "Victory Advance X1",
        "price": "$7.969.000 (incluye SOAT, Matrícula, y tramites)",
        "formatted_price": "$7.969.000 (incluye SOAT, Matrícula, y tramites)",
        "category": "semiautomatica",
        "searchBy": ["semiautomatica", "señoritera", "advance"],
        "summary": "Excelente moto semiautomatica de 115cc."
    }
    mock_catalog.search.return_value = [mock_search_result]
    mock_catalog.get_catalog_aliases.return_value = {
        "semiautomatica": ["señoritera", "moped"]
    }

    # Simulate catalog_context building logic from whatsapp.py
    translated_query = resolve_query_aliases("quiero la señoritera", mock_catalog)
    assert translated_query == "semiautomatica"
    
    catalog_results = mock_catalog.search(translated_query)
    
    catalog_context = ""
    for item in catalog_results[:3]:
        tags_str = ", ".join(item.get('searchBy', []))
        net_price_str = ""
        if mock_catalog and hasattr(mock_catalog, '_items'):
            for raw_item in mock_catalog._items:
                if raw_item.get("name") == item["name"]:
                    net_price_str = raw_item.get("formatted_price")
                    break
        if not net_price_str:
            net_price_str = item.get("formatted_price", "")
        
        catalog_context += f"- {item['name']}: Neto: {net_price_str} / Con SOAT: {item['formatted_price']}. Tags: [{tags_str}]. Specs: {item.get('summary')}\n"

    # Verify that the generated context has both Neto and Con SOAT prices
    assert "Neto: $7.100.000" in catalog_context
    assert "Con SOAT: $7.969.000 (incluye SOAT, Matrícula, y tramites)" in catalog_context

    # Now let's test that the JudgeService uses this context
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "APPROVED"
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    
    judge_service = JudgeService()
    judge_service._client = mock_client
    
    ai_response = "Te recomiendo la Victory Advance X1 por $7.969.000 con SOAT incluido. ![Victory](https://img.url)"
    
    approved, reason = await judge_service.analyze_response(
        user_input="quiero la señoritera",
        ai_response=ai_response,
        catalog_context=catalog_context
    )
    
    assert approved is True
    
    # Check that the prompt sent to the LLM judge contains both prices
    called_args = mock_client.aio.models.generate_content.call_args
    prompt_sent = called_args[1]["contents"]
    assert "Neto: $7.100.000" in prompt_sent
    assert "Con SOAT: $7.969.000" in prompt_sent
