import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.judge_service import JudgeService
from app.services.scoring_service import ScoringService

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
async def test_judge_habeas_data_accepted_violation(judge_service):
    # Profiling without habeas data
    response = "¿En qué trabajas actualmente?"
    prospect_data = {"habeas_data_accepted": False}
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


# --- BOT-BUG-2.1 CERTIFICATION TESTS ---

@pytest.mark.asyncio
async def test_judge_financial_parity_fake_quota_rejected(judge_service):
    """
    CERTIFICACIÓN REQUERIDA (BOT-BUG-2.1):
    Inyectar cuota falsa ($9.999.999) con contexto financiero real.
    El Juez DEBE emitir REJECTED C2_FINANCIAL_PARITY.
    """
    # Mock calculate_payment to return the canonical cuota (e.g. $589.787 for Apache 160)
    canonical_cuota = 589787.0
    fake_cuota = 9999999.0  # Wildly wrong — simulates hallucinated amount

    with patch("app.services.judge_service.financial_service.calculate_payment") as mock_calc:
        mock_calc.return_value = {"cuota_mensual": canonical_cuota}

        # Response contains a fake cuota in Colombian format
        response = (
            f"Tu cuota mensual quedaría en ${fake_cuota:,.0f} con Crediorbe a 24 meses. "
            "![moto](https://img.com/apache.jpg)"
        )
        prospect_data = {
            "ciudad": "Medellín",
            "habeas_data_accepted": True,
            "financial_context": {
                "precio": 11100000,
                "inicial": 1500000,
                "plazo_meses": 24
            }
        }

        approved, reason = await judge_service.analyze_response(
            "cuanto queda la cuota", response, prospect_data=prospect_data
        )

    assert not approved, f"El Juez debería rechazar la cuota falsa, pero aprobó: {reason}"
    assert "C2_FINANCIAL_PARITY" in reason, f"Código de rechazo incorrecto: {reason}"
    assert "difiere" in reason.lower(), f"El motivo no explica la desviación: {reason}"


@pytest.mark.asyncio
async def test_judge_financial_parity_correct_quota_approved(judge_service):
    """
    No-regresión: La cuota correcta (dentro del margen 1%) debe ser APPROVED.
    """
    canonical_cuota = 589787.0

    with patch("app.services.judge_service.financial_service.calculate_payment") as mock_calc:
        mock_calc.return_value = {"cuota_mensual": canonical_cuota}

        # Response contains the exact correct cuota
        response = (
            "Tu cuota mensual quedaría en $589.787 con Crediorbe a 24 meses. "
            "![moto](https://img.com/apache.jpg)"
        )
        prospect_data = {
            "ciudad": "Medellín",
            "habeas_data_accepted": True,
            "financial_context": {
                "precio": 11100000,
                "inicial": 1500000,
                "plazo_meses": 24
            }
        }

        approved, reason = await judge_service.analyze_response(
            "cuanto queda la cuota", response, prospect_data=prospect_data
        )

    assert approved, f"La cuota correcta fue rechazada inesperadamente: {reason}"


@pytest.mark.asyncio
async def test_judge_financial_parity_no_context_passes(judge_service):
    """
    Sin financial_context, el juez no puede validar y debe dejar pasar (no false-positive).
    """
    response = "Tu cuota mensual quedaría en $9.999.999 con Crediorbe."
    prospect_data = {"ciudad": "Bogotá", "habeas_data_accepted": True}

    approved, reason = await judge_service.analyze_response(
        "cuota", response, prospect_data=prospect_data
    )
    # Without context, C2 cannot fire — other criteria may still reject
    assert "C2_FINANCIAL_PARITY" not in reason


# --- BOT-BUG-2.1 ScoringService._get_points word-boundary fix ---

def test_scoring_no_reportado_not_zero():
    """
    'no reportado' NUNCA debe coincidir con la clave 'reportado' (0 pts).
    Debe devolver el default o una clave más específica.
    WHY: El bug de subcadena `if k in key` causaba score=0 en perfiles válidos.
    """
    svc = ScoringService()
    # 'no reportado' is not a key in POINTS_HABIT; should return default (500)
    pts = svc._get_points(svc.POINTS_HABIT, "no reportado", default=500)
    assert pts == 500, (
        f"'no reportado' no debe activar la clave 'reportado' (0 pts). Obtuvo: {pts}"
    )


def test_scoring_reportado_is_zero():
    """No-regresión: 'reportado' exacto sigue dando 0 pts."""
    svc = ScoringService()
    pts = svc._get_points(svc.POINTS_HABIT, "reportado", default=500)
    assert pts == 0, f"'reportado' debe dar 0 pts. Obtuvo: {pts}"


def test_scoring_al_dia_exact_match():
    """No-regresión: 'al dia' sigue dando 1000 pts."""
    svc = ScoringService()
    pts = svc._get_points(svc.POINTS_HABIT, "al dia", default=0)
    assert pts == 1000, f"'al dia' debe dar 1000 pts. Obtuvo: {pts}"
