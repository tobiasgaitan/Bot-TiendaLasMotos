import pytest
import re
from unittest.mock import patch, MagicMock

from app.services.catalog_service import catalog_service
from app.services.config_service import config_service
from app.services.agentic_loop_service import AgenticOrchestrator
from app.services.credit_faq_taxonomy import is_abstract_credit_faq


# ── Mock classes for Gemini SDK responses (mirrors test_pcc_ficha_tecnica.py) ──
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


# ── FAQ SSOT / desanidamiento ──

def test_credit_faq_desanidado_datacredito_bypass():
    """
    [BOT-BUILD-REGRESSION-TRIAGE-COMPETENCIA-CUOTA-203]
    Antes del fix, 'datacredito'/'reportado' no estaban en la lista genérica
    de FAQ, por lo que el bypass nunca se activaba al estar anidado dentro de
    `if is_faq_intent:`. Ahora el clasificador SSOT evalúa la señal de crédito
    de forma independiente.
    """
    orchestrator = AgenticOrchestrator()
    prompt = "estoy reportado en datacredito"
    assert is_abstract_credit_faq(prompt) is True, "datacredito/reportado debe ser FAQ crediticia abstracta"

    result = orchestrator.run_checker(
        "Reportado requiere 10% de inicial.",
        is_catalog_query=True,
        prospect_data={"moto_interest": "TVS Raider 125", "nombre": "Carlos"},
        user_prompt=prompt,
    )
    assert result.get("bypass_strict") is True, (
        f"Prompt '{prompt}' con moto_interest DEBE activar bypass estricto tras desanidar."
    )


def test_is_abstract_credit_faq_ssot_still_rejects_simulations():
    """Una pregunta con 'cuota' debe seguir siendo intención comercial, no FAQ."""
    assert is_abstract_credit_faq("cuanto queda la cuota de la raider") is False


# ── Competencia Boxer / NKD (catálogo real + tool loop) ──

@pytest.mark.asyncio
async def test_boxer_competitor_tool_loop_returns_alternative():
    """
    [BOT-BUILD-REGRESSION-TRIAGE-COMPETENCIA-CUOTA-203]
    End-to-end del path agentic con catálogo de producción: la query 'Boxer'
    debe resolverse a TVS Sport 100, el LLM debe recibir imagen Markdown y
    la respuesta final debe pasar Visual-Lock (precio + imagen + ficha).
    """
    from app.services.ai_brain import CerebroIA
    from app.services.financial_service import financial_service
    from app.core.config_loader import ConfigLoader
    from app.core.security import get_firebase_credentials_object
    from app.core.config import settings
    from google.cloud import firestore
    import os

    old_cred = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if old_cred == "/tmp/fake-key.json":
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    try:
        credentials = get_firebase_credentials_object()
    finally:
        if old_cred is not None:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = old_cred

    db = firestore.Client(project=settings.gcp_project_id, credentials=credentials)
    config_loader = ConfigLoader(db)
    config_loader.load_all()
    config_service.initialize(db)
    financial_service._config_service.initialize(db)
    catalog_service.initialize(db, config_loader)

    cerebro = CerebroIA()
    cerebro._catalog_service = catalog_service
    cerebro.motor_financiero = financial_service
    cerebro.client = MagicMock()
    cerebro._model_id = "gemini-2.0-flash"

    # Precondición: el catálogo real sí resuelve Boxer a TVS Sport 100
    matches = catalog_service.search_items("Boxer")
    assert any("SPORT 100" in m.get("name", "") for m in matches), (
        "Catálogo prod debe devolver TVS Sport 100 para 'Boxer'"
    )
    sport = next(m for m in matches if "SPORT 100" in m.get("name", ""))
    sport_price = sport.get("formatted_price", "$5.949.999")
    sport_image = sport.get("image_url", "https://example.com/sport.jpg")

    # Simulación: LLM llama search_catalog('Boxer') y luego responde con la ficha
    fc = MockFunctionCall(name="search_catalog", args={"query": "Boxer"})
    candidate_tool = MockCandidate(content=MockContent(parts=[MockPart(function_call=fc)]))
    final_text = (
        f"¡Claro! Te recomiendo la {sport.get('name')} a {sport_price}. "
        f"![{sport.get('name')}]({sport_image}) "
        f"Ficha Tecnica: Moto de trabajo económica y duradera."
    )
    candidate_final = MockCandidate(content=MockContent(parts=[MockPart(text=final_text)]))

    responses = [MockResponse([candidate_tool]), MockResponse([candidate_final])]
    response_iter = iter(responses)

    async def mock_call(*args, **kwargs):
        return next(response_iter)

    prospect = {"nombre": "Ana", "ciudad": "Bogotá", "forma_pago": "Crédito"}
    with patch.object(cerebro, "_call_gemini_with_retry_async", new=mock_call), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):
        final = await cerebro.pensar_respuesta("Tienen la Boxer?", prospect_data=prospect)

    assert "SPORT 100" in final or sport.get("name") in final, (
        f"La respuesta no pivoteó a Sport 100: {final[:500]}"
    )
    assert re.search(r"\$[\d.]+", final) is not None, "La respuesta debe incluir precio ($)"
    assert re.search(r"!\[.*?\]\(.*?\)", final) is not None, (
        "La respuesta debe incluir imagen Markdown"
    )
    assert "No encontré" not in final, f"No debe decir 'No encontré': {final[:500]}"
    assert "no conocemos" not in final.lower(), f"No debe decir 'no conocemos': {final[:500]}"

    # Visual-Lock desde el punto de vista del orquestador
    orchestrator = AgenticOrchestrator()
    validation = orchestrator.run_checker(
        final,
        is_catalog_query=True,
        prospect_data=prospect,
        user_prompt="Tienen la Boxer?",
    )
    assert validation["success"] is True, (
        f"Visual-Lock falló para Boxer: {validation.get('report')}"
    )


@pytest.mark.asyncio
async def test_boxer_competitor_bypasses_drift_interceptor():
    """
    Si ya existe un moto_interest previo (Raider 125), una consulta de
    competencia 'NKD' igual debe poder pivotar a TVS Sport 100.
    """
    from app.services.ai_brain import CerebroIA
    from app.services.financial_service import financial_service

    cerebro = CerebroIA()
    cerebro.motor_financiero = financial_service
    cerebro.client = MagicMock()
    cerebro._model_id = "gemini-2.0-flash"

    # Stub mínimo de catálogo para no depender de red en este test unitario
    stub_sport = {
        "id": "tvs_sport",
        "name": "TVS Sport 100 ELS",
        "price": 5949999,
        "formatted_price": "$5.949.999",
        "category": "trabajo",
        "image_url": "https://example.com/sport.jpg",
        "summary": "Moto de trabajo económica.",
        "searchBy": ["nkd", "boxer"],
    }
    mock_catalog = MagicMock()
    mock_catalog.search_items.return_value = [stub_sport]
    mock_catalog.get_all_items.return_value = [stub_sport]
    mock_catalog.get_catalog_aliases.return_value = {}
    cerebro._catalog_service = mock_catalog

    fc = MockFunctionCall(name="search_catalog", args={"query": "NKD"})
    candidate_tool = MockCandidate(content=MockContent(parts=[MockPart(function_call=fc)]))
    final_text = (
        "La opción que manejamos es la TVS Sport 100 ELS a $5.949.999. "
        "![TVS Sport 100 ELS](https://example.com/sport.jpg) "
        "Ficha Tecnica: Moto de trabajo económica."
    )
    candidate_final = MockCandidate(content=MockContent(parts=[MockPart(text=final_text)]))

    responses = [MockResponse([candidate_tool]), MockResponse([candidate_final])]
    response_iter = iter(responses)

    async def mock_call(*args, **kwargs):
        return next(response_iter)

    prospect = {
        "nombre": "Luis",
        "ciudad": "Medellín",
        "moto_interest": "TVS Raider 125",
        "forma_pago": "Crédito",
    }
    with patch.object(cerebro, "_call_gemini_with_retry_async", new=mock_call), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):
        final = await cerebro.pensar_respuesta("Tienen NKD?", prospect_data=prospect)

    assert "TVS Sport 100 ELS" in final, f"No pivotó desde Raider hacia Sport: {final[:500]}"
    assert prospect.get("moto_interest") == "TVS Sport 100 ELS", (
        "El moto_interest debe actualizarse al alternativo de la competencia"
    )


# ── TVS Raider 125: normalización de base amortizable ──

@pytest.mark.asyncio
async def test_raider_125_helper_path_414444():
    """
    [BOT-BUILD-REGRESSION-TRIAGE-COMPETENCIA-CUOTA-203]
    [BOT-BUILD-204] El helper del agente normaliza la base amortizable de la Raider 125
    (precio catálogo $7.799.999 / cc=124) a base=$6.991.896 y cc=0. Ahora el re-add lee
    la banda 0-99 (=700.000) de Firestore, produciendo cuota $414.444 hasta que la base
    legacy (strip=780.000) se realinee con SSOT.
    """
    from app.services.ai_brain import CerebroIA
    from app.services.financial_service import financial_service
    from app.core.config_loader import ConfigLoader
    from app.core.security import get_firebase_credentials_object
    from app.core.config import settings
    from google.cloud import firestore
    import os

    old_cred = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if old_cred == "/tmp/fake-key.json":
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    try:
        credentials = get_firebase_credentials_object()
    finally:
        if old_cred is not None:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = old_cred

    db = firestore.Client(project=settings.gcp_project_id, credentials=credentials)
    config_loader = ConfigLoader(db)
    config_loader.load_all()
    config_service.initialize(db)
    financial_service._config_service.initialize(db)

    cerebro = CerebroIA()
    cerebro.motor_financiero = financial_service

    res = cerebro._calculate_payment_helper(
        precio=7799999.0,
        inicial=858000.0,
        plazo_meses=24,
        entidad="Brilla de Gases",
        moto_cc=124.0,
        category="motos",
        moto_name="TVS RAIDER 125",
    )
    assert res.get("cuota_mensual") == 414444.0, (
        f"Raider 125 helper path mismatch: expected 414444, got {res.get('cuota_mensual')}"
    )
    assert round(res.get("capital_financiado", 0)) == 7175591, (
        f"Wrong capital_financiado: {res.get('capital_financiado')}"
    )
