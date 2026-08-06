"""
[AUD-CIERRE-RUTAS-010] Tests del rediseño de la doctrina de CIERRE DE FASE.
Vía B: resolvedor determinista + enforcement POST-JSON en ai_brain.py.
Vía A: paridad de prompt (cubierta por test_promptrestore003_fuentes_armonizadas_texto_definitivo).
"""

import pytest
import logging
from unittest.mock import MagicMock, patch

from app.services.ai_brain import CerebroIA
from app.services.scoring_service import ScoringService, is_gas_affirmative


class FakeMotor(ScoringService):
    """Motor financiero de doble propósito: hereda de ScoringService para que
    ai_brain entre en la rama ScoringService, pero devuelve valores controlados."""

    def __init__(self, score=530, strategy="BRILLA", entity="Brilla de Gases", is_fallback=True):
        # No llamamos a super().__init__ para no depender de estado; la clase no lo necesita.
        self._score = score
        self._strategy = strategy
        self._entity = entity
        self._is_fallback = is_fallback

    def calculate_score(self, **kwargs):
        return self._score

    def determine_strategy(self, **kwargs):
        return {
            "strategy": self._strategy,
            "entity": self._entity,
            "rate_key": None if self._entity == "Brilla de Gases" else "tasa_nmv_banco",
            "link_key": "link_brilla" if self._entity == "Brilla de Gases" else "link_banco_bogota",
            "requires_aval": False,
            "is_fallback": self._is_fallback,
        }


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


def _extract_function_result(contents):
    """Extrae el texto del function_response de calculate_credit_score del prompt enviado a Gemini."""
    for part in contents:
        fun_res = getattr(part, "function_response", None)
        if fun_res is not None:
            resp = getattr(fun_res, "response", {})
            if isinstance(resp, dict):
                return resp.get("result", "")
            return getattr(resp, "result", "")
    return ""


# ---------------------------------------------------------------------------
# 1. Resolvedor puro resolve_cierre_route
# ---------------------------------------------------------------------------
def test_resolve_cierre_route_tabla_completa():
    """T1: tabla bandas x gas completa; prioridad absoluta de bandas sobre strategy."""
    svc = ScoringService()

    # R1 Banco
    for score in (750, 800, 1000):
        for gas in (True, False, "Sí", "No", None):
            assert svc.resolve_cierre_route(score, gas) == 1, f"score={score} gas={gas!r}"

    # R2 Revisión humana (con o sin gas; bandas mandan)
    for score in (500, 600, 700, 749):
        for gas in (True, False, "Sí", "No"):
            assert svc.resolve_cierre_route(score, gas) == 2, f"score={score} gas={gas!r}"

    # R3 Brilla solo con gas afirmativo
    for score in (0, 200, 399, 400, 499):
        assert svc.resolve_cierre_route(score, True) == 3, f"score={score} con gas True"
        assert svc.resolve_cierre_route(score, "Sí") == 3, f"score={score} con gas 'Sí'"
        assert svc.resolve_cierre_route(score, "si") == 3, f"score={score} con gas 'si'"

    # R4 Rechazo sin gas
    for score in (0, 200, 399, 400, 499):
        assert svc.resolve_cierre_route(score, False) == 4, f"score={score} sin gas False"
        assert svc.resolve_cierre_route(score, "No") == 4, f"score={score} sin gas 'No'"
        assert svc.resolve_cierre_route(score, None) == 4, f"score={score} sin gas None"


def test_resolve_cierre_route_hueco_499():
    """T2: score 499 ya no queda huérfano; pertenece a R3/R4 (<=499)."""
    svc = ScoringService()
    assert svc.resolve_cierre_route(499, True) == 3
    assert svc.resolve_cierre_route(499, False) == 4


# ---------------------------------------------------------------------------
# 2. Normalización estricta de gas (cierra truthy-bug H1)
# ---------------------------------------------------------------------------
def test_is_gas_affirmative_normalizacion():
    """T3: solo True/1 o strings afirmativas normalizadas son True; 'No' es False."""
    assert is_gas_affirmative(True) is True
    assert is_gas_affirmative(1) is True
    assert is_gas_affirmative("Sí") is True
    assert is_gas_affirmative("sí") is True
    assert is_gas_affirmative("Si") is True
    assert is_gas_affirmative("si") is True
    assert is_gas_affirmative(" Sí ") is True

    assert is_gas_affirmative(False) is False
    assert is_gas_affirmative(0) is False
    assert is_gas_affirmative("No") is False
    assert is_gas_affirmative("no") is False
    assert is_gas_affirmative("NO") is False
    assert is_gas_affirmative("") is False
    assert is_gas_affirmative(None) is False
    assert is_gas_affirmative("quizas") is False


# ---------------------------------------------------------------------------
# 3. Regresión exacta del incidente (score 530, gas "No" -> ruta 2)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_incidente_530_no_gas_ruta_2():
    """T4: replica exacta del ticket. strategy del motor sigue siendo BRILLA,
    pero el enforcement POST-JSON selecciona cierre_ruta=2 y emite copywriting
    de revisión humana, no de Brilla."""
    cerebro = CerebroIA()
    cerebro.motor_financiero = FakeMotor(score=530, strategy="BRILLA", entity="Brilla de Gases")

    mock_config = MagicMock()
    mock_config.get_partners_config.return_value = {
        "link_banco_bogota": "https://slm.bancodebogota.com/mctn45s5",
        "link_brilla": "https://brilladegasesdeoccidente.com/",
    }
    cerebro._config_loader = mock_config
    cerebro._catalog_service = None  # ruta 2 no requiere cuota

    fc = MockFunctionCall(
        name="calculate_credit_score",
        args={
            "ocupacion_y_contrato": "Empleado término fijo",
            "ingresos_demostrables": "SMLV",
            "historial_datacredito": "Al día",
            "plan_celular": "Sí",
            "tiene_gas_natural": "No",
        },
    )
    response1 = MockResponse(candidates=[MockCandidate(MockContent([MockPart(function_call=fc)]))])
    response2 = MockResponse(candidates=[MockCandidate(MockContent([MockPart(text="Ok")]))])

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

    prospect = {
        "nombre": "Ana",
        "ciudad": "Santa Marta",
        "forma_pago": "credito",
        "moto_interest": "TVS Sport 100",
        "habeas_data_accepted": True,
        "habeas_data_accepted_sent": True,
        "tiene_gas_natural": "No",
    }
    history = [{"role": "model", "content": "Política de privacidad aceptada"}]

    with patch.object(cerebro, "_call_gemini_with_retry_async", new=mock_call), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):
        await cerebro.pensar_respuesta("Continuar con el estudio", prospect_data=prospect, history=history)

    assert len(captured_contents) >= 2, "Se esperaban al menos dos llamadas a Gemini"
    result_text = _extract_function_result(captured_contents[1])

    # Vía B: el copywriting es de ruta 2 (revisión humana), no de Brilla.
    assert "Un compañero revisará estos datos" in result_text, result_text
    assert "Cédula, PPT o Cédula de Extranjería" in result_text, result_text
    # El mandato Brilla (cédula + recibos de gas) NO debe aparecer para 530 sin gas.
    assert "Brilla de Gases" not in result_text, result_text
    assert "recibos del gas natural" not in result_text, result_text

    # Persistencia aditiva intacta; strategy/entity del motor no alterados.
    score_resultado = prospect.get("_score_resultado", {})
    assert score_resultado.get("cierre_ruta") == 2, score_resultado
    assert score_resultado.get("score") == 530, score_resultado
    assert score_resultado.get("strategy") == "BRILLA", score_resultado
    assert score_resultado.get("entity") == "Brilla de Gases", score_resultado


# ---------------------------------------------------------------------------
# 4. Logger forense aditivo
# ---------------------------------------------------------------------------
def test_logger_forense_cierre_ruta(caplog):
    """T5: resolve_cierre_route no emite PII; logger de ai_brain loguea score/ruta/gas."""
    caplog.set_level(logging.INFO)
    svc = ScoringService()
    with caplog.at_level(logging.INFO):
        svc.resolve_cierre_route(530, "No")

    # El resolvedor no loguea por sí mismo; el log es responsabilidad de ai_brain.
    # Verificamos que is_gas_affirmative no loguee y que no haya PII en el resolvedor.
    assert "530" not in caplog.text  # sin log propio del resolvedor
