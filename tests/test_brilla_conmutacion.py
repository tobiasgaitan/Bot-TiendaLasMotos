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
    [BOT-BUILD-FIX-E-CREDIORBE-ERADICATION-001] Certificación de erradicación:
    determine_strategy NUNCA enruta a 'Crediorbe' para ningún score, y el rango
    400-699 (ex-FINTECH) converge al fallback Brilla de Gases.
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
    # Rango ex-FINTECH → Brilla de Gases (unificación doctrinal FIX-E)
    for score in (400, 500, 699):
        res = svc.determine_strategy(
            score=score, tiene_gas_natural=False, historial_datacredito="Al dia"
        )
        assert res["entity"] == "Brilla de Gases", \
            f"score={score} debía caer al fallback Brilla, obtuvo {res['entity']}"
        assert res["strategy"] == "BRILLA"
        assert res["requires_aval"] is False


def test_crediorbe_eradicated_from_source():
    """
    [FIX-E] Guard estático anti-regresión: la nomenclatura 'Crediorbe' no debe
    reaparecer en la fuente de scoring_service.py ni ai_brain.py.
    """
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    for rel in ("app/services/scoring_service.py", "app/services/ai_brain.py"):
        src = (root / rel).read_text(encoding="utf-8")
        assert "Crediorbe" not in src, f"'Crediorbe' reapareció en {rel}"
        assert "crediorbe" not in src, f"'crediorbe' reapareció en {rel}"


def test_personality_json_synced_to_brilla():
    """
    [FIX-E] personality.json (fallback #2) debe estar sincronizado a Brilla de
    Gases en el PASO 2 del protocolo comercial, sin residuos de Crediorbe.
    """
    import json
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    data = json.loads((root / "app/core/personality.json").read_text(encoding="utf-8"))
    si = data["system_instruction"]
    assert "Crediorbe" not in si and "crediorbe" not in si
    assert "mediante nuestro sistema de Brilla de Gases" in si


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


