import pytest
from unittest.mock import MagicMock, patch
from app.services.ai_brain import CerebroIA, EXTRACTION_SCHEMA
from app.services.financial_service import FinancialService

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

def test_extraction_schema_contains_cedula_usuario():
    """
    Verifica que la propiedad 'cedula_usuario' exista dentro de extracted en EXTRACTION_SCHEMA
    con los tipos y descripciones correctos.
    """
    properties = EXTRACTION_SCHEMA["properties"]["extracted"]["properties"]
    assert "cedula_usuario" in properties
    assert properties["cedula_usuario"]["type"] == "STRING"
    assert "bias negativo" in properties["cedula_usuario"]["description"].lower()


def test_scoring_never_routes_to_crediorbe():
    """
    [BOT-BUILD-FIX-E-CREDIORBE-ERADICATION-001 + AUD-CIERRE-RUTAS-010]
    Certificación de erradicación: determine_strategy NUNCA enruta a 'Crediorbe'.
    La decisión de cierre de fase ahora la resuelve resolve_cierre_route con
    prioridad absoluta de bandas de score y gate de coherencia gas/Brilla.
    """
    from app.services.scoring_service import ScoringService
    svc = ScoringService()
    for score in [0, 200, 399, 400, 500, 699, 700, 850, 1000]:
        for gas in (False, True):
            for hist in ("", "Al dia", "Reportado"):
                res = svc.determine_strategy(
                    score=score, tiene_gas_natural=gas, historial_datacredito=hist
                )
                assert res["entity"] != "Crediorbe", \
                    f"Crediorbe resurgió con score={score}, gas={gas}, hist={hist!r}"

    # [AUD-CIERRE-RUTAS-010] Doctrina canónica de cierre de fase (bandas > strategy):
    #   R1 >= 750, R2 500-749, R3 <= 499 + gas afirmativo, R4 <= 499 + gas negativo.
    assert svc.resolve_cierre_route(750, False) == 1
    assert svc.resolve_cierre_route(850, False) == 1
    assert svc.resolve_cierre_route(1000, False) == 1
    for score in (500, 699, 700, 749):
        assert svc.resolve_cierre_route(score, False) == 2, f"score={score} sin gas debe ser ruta 2"
        assert svc.resolve_cierre_route(score, True) == 2, f"score={score} con gas debe ser ruta 2 (bandas mandan)"
    for score in (0, 200, 399, 400, 499):
        assert svc.resolve_cierre_route(score, False) == 4, f"score={score} sin gas debe ser ruta 4"
        assert svc.resolve_cierre_route(score, True) == 3, f"score={score} con gas debe ser ruta 3"


def test_crediorbe_eradicated_from_source():
    """
    [FIX-E + BOT-BUILD-LEGACY-JUDGE-012] Guard estático anti-regresión: la
    nomenclatura 'Crediorbe' no debe reaparecer en la fuente de
    scoring_service.py, ai_brain.py ni judge_service.py.
    """
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    for rel in (
        "app/services/scoring_service.py",
        "app/services/ai_brain.py",
        "app/services/judge_service.py",
    ):
        src = (root / rel).read_text(encoding="utf-8")
        assert "Crediorbe" not in src, f"'Crediorbe' reapareció en {rel}"
        assert "crediorbe" not in src, f"'crediorbe' reapareció en {rel}"


def test_m4_003_survey_service_purgado():
    """
    [BOT-BUILD-LEGACY-JUDGE-012] Tumba M4-003: el módulo muerto
    survey_service.py (residuo CrediOrbe) fue purgado y no debe renacer.
    """
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    assert not (root / "app/services/survey_service.py").exists(), (
        "El módulo legacy survey_service.py sigue existiendo (M4-003)."
    )


def test_personality_json_synced_to_brilla():
    """
    [FIX-E + PROMPT-RESTORE-EXACT-003] personality.json (fallback #2) debe
    estar sincronizado a Brilla de Gases como entidad inyectada en la
    simulación ciega del PASO 2 del protocolo comercial, sin residuos de
    Crediorbe. (El texto definitivo reemplazó la mención narrativa
    'mediante nuestro sistema de Brilla de Gases' por la inyección
    explícita de entidad en la herramienta.)
    """
    import json
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    data = json.loads((root / "app/core/personality.json").read_text(encoding="utf-8"))
    si = data["system_instruction"]
    assert "Crediorbe" not in si and "crediorbe" not in si
    assert 'entidad="Brilla de Gases"' in si


def test_financial_service_default_entity_is_brilla():
    """
    Verifica que en financial_service.py la simulación por defecto no exponga Brilla de Gases (anonimización).
    """
    fs = FinancialService()
    fs.calculate_payment = MagicMock(return_value={"cuota_mensual": 250000.0})
    moto_dict = {
        "name": "Moto Test",
        "price": 8000000.0,
        "displacement": "125 cc",
        "category": "Urban"
    }
    # Invocamos la simulación para una moto inexistente o similar, o evaluamos directamente la respuesta generada.
    res = fs._generate_full_simulation_response(moto_dict, 0.0)
    # Debe omitir mencionar "Brilla de Gases" o cualquier marca de agua
    assert "Brilla de Gases" not in res
    assert "Brilla" not in res
@pytest.mark.asyncio
async def test_unified_catalog_keys_interception():
    """
    Verifica que la herramienta search_catalog extraiga correctamente name,
    summary y price de Firestore sin levantar ValueError.
    """
    cerebro = CerebroIA()
    cerebro.client = MagicMock()
    cerebro._model_id = "gemini-2.0-flash"
    
    mock_catalog = MagicMock()
    # Retornamos llaves unificadas
    mock_catalog.search_items.return_value = [
        {
            "name": "TVS Apache 160",
            "summary": "Moto deportiva y ágil",
            "price": "$ 9.500.000",
            "category": "Urban"
        }
    ]
    cerebro._catalog_service = mock_catalog
    
    fc = MockFunctionCall(name="search_catalog", args={"query": "Apache 160"})
    candidate1 = MockCandidate(content=MockContent(parts=[MockPart(function_call=fc)]))
    response1 = MockResponse(candidates=[candidate1])
    
    candidate2 = MockCandidate(content=MockContent(parts=[MockPart(text="Ok")]))
    response2 = MockResponse(candidates=[candidate2])
    
    call_count = 0
    captured_contents = []
    
    async def mock_call(*args, **kwargs):
        nonlocal call_count, captured_contents
        call_count += 1
        if "contents" in kwargs:
            captured_contents.append(kwargs["contents"])
        elif len(args) > 1:
            captured_contents.append(args[1])
        elif len(args) > 0:
            captured_contents.append(args[0])
        if call_count == 1:
            return response1
        return response2

    with patch.object(cerebro, '_call_gemini_with_retry_async', new=mock_call), \
         patch('app.services.ai_brain.SDK_AVAILABLE', True):
          
        prospect = {
            "nombre": "Carlos",
            "ciudad": "Santa Marta",
            "forma_pago": "Contado"
        }
        await cerebro.pensar_respuesta("Qué precio tiene la Apache 160?", prospect_data=prospect)
        
        # Debe haber capturado el segundo llamado con los resultados del catálogo procesados
        assert len(captured_contents) >= 2
        second_call_contents = captured_contents[1]
        
        result_text = ""
        for part in second_call_contents:
            fun_res = getattr(part, "function_response", None)
            if fun_res is not None:
                resp = getattr(fun_res, "response", {})
                if isinstance(resp, dict):
                    result_text = resp.get("result", "")
                else:
                    result_text = getattr(resp, "result", "")
                break
        
        # Validar que Nombre, Descripción y Precio se formatearon correctamente
        assert "TVS Apache 160" in result_text
        assert "Moto deportiva y ágil" in result_text
        assert "$ 9.500.000" in result_text
        assert "Ficha Tecnica: Moto deportiva y ágil" in result_text


