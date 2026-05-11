import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from app.services.judge_service import JudgeService

@pytest.fixture
def judge_service():
    # Mock cerebro_ia to avoid actual API calls during basic tests
    mock_cerebro = MagicMock()
    service = JudgeService(cerebro_ia=mock_cerebro)
    # Disable semantic audit by default for unit tests
    service._client = None
    return service

@pytest.mark.asyncio
async def test_judge_visual_lock_fail(judge_service):
    # Mention bike but no price
    response = "Te recomiendo la TVS Apache 160, es una excelente moto."
    approved, reason = await judge_service.analyze_response("hola", response)
    assert not approved
    assert "C1_VISUAL_LOCK" in reason
    assert "precio" in reason.lower()

@pytest.mark.asyncio
async def test_judge_visual_lock_fail_image(judge_service):
    # Mention bike and price but no image
    response = "Te recomiendo la TVS Apache 160 por solo $8.990.000."
    approved, reason = await judge_service.analyze_response("hola", response)
    assert not approved
    assert "C1_VISUAL_LOCK" in reason
    assert "imagen" in reason.lower()

@pytest.mark.asyncio
async def test_judge_visual_lock_success(judge_service):
    # Mention bike, price and image
    response = "Te recomiendo la TVS Apache 160 por solo $8.990.000. ![moto](https://link.com/foto.jpg)"
    approved, reason = await judge_service.analyze_response("hola", response)
    assert approved

@pytest.mark.asyncio
async def test_judge_one_question_rule(judge_service):
    # Two questions
    response = "¿Cómo estás? ¿Te interesa alguna moto?"
    approved, reason = await judge_service.analyze_response("hola", response)
    assert not approved
    assert "C5_ONE_QUESTION_RULE" in reason

@pytest.mark.asyncio
async def test_judge_habeas_data_violation(judge_service):
    # Profiling without habeas data
    response = "¿En qué trabajas actualmente?"
    prospect_data = {"habeas_data": False}
    approved, reason = await judge_service.analyze_response("hola", response, prospect_data=prospect_data)
    assert not approved
    assert "C3_HABEAS_DATA_VIOLATION" in reason

@pytest.mark.asyncio
async def test_judge_city_discovery_fail(judge_service):
    # Move to credit without city
    response = "Para iniciar tu crédito necesito unos datos."
    prospect_data = {"ciudad": ""}
    approved, reason = await judge_service.analyze_response("financiar", response, prospect_data=prospect_data)
    assert not approved
    assert "C9_CITY_MISSING" in reason

@pytest.mark.asyncio
async def test_judge_brilla_protocol_fail(judge_service):
    # Brilla without requirements
    response = "Podemos financiarte con Crédito Brilla."
    prospect_data = {"ciudad": "Cali"}
    approved, reason = await judge_service.analyze_response("brilla", response, prospect_data=prospect_data)
    assert not approved
    assert "C7_BRILLA_PROTOCOL" in reason

@pytest.mark.asyncio
async def test_judge_scoring_inconsistency(judge_service):
    # Low score recommending bank
    response = "Te recomiendo financiar con un Banco."
    prospect_data = {
        "ciudad": "Cali",
        "extracted": {
            "ocupacion": "informal",
            "datacredito": "reportado",
            "ingresos": "minimo"
        }
    }
    approved, reason = await judge_service.analyze_response("banco", response, prospect_data=prospect_data)
    assert not approved
    assert "C6_SCORING_INCONSISTENCY" in reason

@pytest.mark.asyncio
async def test_judge_link_check_fail(judge_service):
    # Unauthorized URL
    response = "Mira más en https://autecomobility.com/motos"
    approved, reason = await judge_service.analyze_response("ver mas", response)
    assert not approved
    assert "C8_CONVERSION_PATH" in reason
    assert "URL no autorizada" in reason
