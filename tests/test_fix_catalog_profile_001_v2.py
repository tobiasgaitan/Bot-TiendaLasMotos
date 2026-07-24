"""
[BOT-BUILD-FIX-CATALOG-PROFILE-001-AMPLIADO-v2] Pins de certificación (3 fixes).

Milestone 3 - Etapa 4: Erradicación de Instrucciones Obsoletas en ai_brain.py.

FIX-A  funnel_instruction de PHASE_3_CREDIT_PROFILING (L1616-1623): erradicada
       la orden obsoleta 'Ejecuta calculate_credit_score ¡DETENTE AQUÍ!' que se
       re-inyectaba en cada function_response y generaba bucle de herramientas
       → max_turns=3 → fallback (Problema 4: bloqueo ~3 min). La nueva
       instrucción es MATRIZ DE PERFILAMIENTO (8 datos) → CIERRE DE FASE.
FIX-B  CRITICAL IDENTITY RULE (v8.3) condicionada por fase: en PHASE_3 se
       suprime y se inyecta el mandato anti-saludos (Problema 3: '¡Hola Carlos!'
       repetido en cada turno de la matriz). Fuera de PHASE_3 la regla
       original se conserva VERBATIM (cero regresión en el resto del embudo).
FIX-C  Descripción de calculate_credit_score: erradicados 'Paso 9' (inexistente
       en todo flujo vigente) y '¡DETENTE AQUÍ! No generes respuesta'
       (co-causante del bucle sin texto final). Nueva descripción con las dos
       únicas ventanas de uso (simulación inicial + CIERRE DE FASE).

NOTA FORENSE DE ALCANCE: el system instruction de fallback (personality.json /
prompts.py PASO 4) aún contiene '¡DETENTE AQUÍ!' — es lado PROMPT (Firestore),
EXCLUIDO de este ticket (ticket de configuración ex-FIX-E). Por eso los pins
de 'DETENTE' se acotan QUIRÚRGICAMENTE al bloque <instruccion_de_cierre> y al
eco de herramienta, nunca al prompt completo.
"""

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai_brain import CerebroIA


# ---------------------------------------------------------------------------
# Mock helpers (patrón establecido en tests/test_fix_catalog_profile_001.py)
# ---------------------------------------------------------------------------
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


def _text_response(text: str) -> MockResponse:
    return MockResponse(candidates=[MockCandidate(content=MockContent(parts=[MockPart(text=text)]))])


def _tool_response(name: str, args: dict) -> MockResponse:
    fc = MagicMock()
    fc.name = name
    fc.args = args
    return MockResponse(candidates=[MockCandidate(content=MockContent(parts=[MockPart(function_call=fc)]))])


def _phase3_prospect() -> dict:
    """Prospecto que el estado determinista ubica en PHASE_3_CREDIT_PROFILING:
    habeas aceptado+enviado, link de política en historial, nombre+ciudad."""
    return {
        "exists": True,
        "nombre": "Carlos",
        "ciudad": "Barranquilla",
        "forma_pago": "credito",
        "moto_interest": "TVS SPORT 100 ELS",
        "habeas_data_accepted": True,
        "habeas_data_accepted_sent": True,
        "ocupacion": "Empleado",
    }


_HISTORY_WITH_POLICY_LINK = [
    {"role": "model", "content": "Política: https://tiendalasmotos.com/politica-de-privacidad"}
]


def _extract_closing_instruction(prompt: str) -> str:
    match = re.search(r"<instruccion_de_cierre>(.*?)</instruccion_de_cierre>", prompt, re.DOTALL)
    assert match, "No se encontró <instruccion_de_cierre> en el prompt"
    return match.group(1)


# ===========================================================================
# FIX-A — Instrucción de PHASE_3: MATRIZ → CIERRE (no bucle de herramienta)
# ===========================================================================
@pytest.mark.asyncio
async def test_fixa_phase3_closing_instruction_is_matrix_cierre_not_detente():
    """El bloque <instruccion_de_cierre> de PHASE_3 debe contener la instrucción
    de MATRIZ/CIERRE aprobada por el Auditor y CERO residuos de la orden
    obsoleta ('DETENTE', 'Ejecuta la herramienta calculate_credit_score')."""
    cerebro = CerebroIA()
    prompts = []

    async def mock_call(*args, **kwargs):
        prompts.append(str(args[1]) if len(args) > 1 else "")
        return _text_response("Entendido. ¿Cuáles son tus ingresos mensuales?")

    with patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):
        await cerebro.pensar_respuesta(
            "soy empleado", prospect_data=_phase3_prospect(), history=_HISTORY_WITH_POLICY_LINK
        )

    assert prompts, "No se capturó el prompt enviado a Gemini"
    closing = _extract_closing_instruction(prompts[0])

    # Texto nuevo (verbatim del ticket, puede estar partido en el prompt)
    assert "MATRIZ DE PERFILAMIENTO (8 datos)" in closing
    assert "SOLO UNA PREGUNTA A LA VEZ" in closing
    assert "NO repitas saludos" in closing
    assert "NO repreguntes datos CAPTURADOS" in closing
    assert "CIERRE DE FASE" in closing

    # Cero residuos de la instrucción obsoleta en la instrucción de cierre
    assert "DETENTE" not in closing
    assert "Ejecuta la herramienta calculate_credit_score" not in closing

    # La frase obsoleta exacta tampoco puede aparecer re-inyectada en ninguna
    # otra zona del prompt (la re-inyección de máxima recencia L1767-1768 usa
    # el mismo funnel_instruction ya corregido).
    assert "Ejecuta la herramienta calculate_credit_score" not in prompts[0]


@pytest.mark.asyncio
async def test_fixa_tool_echo_in_phase3_carries_matrix_instruction_not_detente():
    """Si el LLM invoca calculate_credit_score en PHASE_3, el function_response
    devuelto arrastra el funnel_instruction (diseño heredado, sancionado). El
    eco debe llevar la instrucción de MATRIZ — que NO induce re-ejecución —
    y cero 'DETENTE' (antes: el eco re-ordenaba ejecutar la herramienta →
    bucle hasta max_turns → fallback)."""
    cerebro = CerebroIA()
    calls = []
    responses = [
        _tool_response("calculate_credit_score", {}),
        _text_response("Entendido. ¿Cuáles son tus ingresos mensuales?"),
    ]

    async def mock_call(*args, **kwargs):
        payload = args[1] if len(args) > 1 else ""
        if isinstance(payload, list):
            payload = " ".join(str(p) for p in payload)
        calls.append(str(payload))
        return responses.pop(0)

    with patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):
        result = await cerebro.pensar_respuesta(
            "soy empleado", prospect_data=_phase3_prospect(), history=_HISTORY_WITH_POLICY_LINK
        )

    # El post-procesador de respuestas puede recortar muletillas iniciales
    # ("Entendido."); lo que se certifica aquí es el eco de herramienta.
    assert "¿Cuáles son tus ingresos mensuales?" in result
    assert len(calls) == 2, "Se esperaba 1 llamada de inferencia + 1 eco de herramienta"
    tool_echo = calls[1]
    assert "MATRIZ DE PERFILAMIENTO (8 datos)" in tool_echo
    assert "CIERRE DE FASE" in tool_echo
    assert "DETENTE" not in tool_echo
    assert "Ejecuta la herramienta calculate_credit_score" not in tool_echo


# ===========================================================================
# FIX-B — Identity rule suprimida en PHASE_3, verbatim fuera de ella
# ===========================================================================
@pytest.mark.asyncio
async def test_fixb_phase3_suppresses_identity_rule_and_injects_anti_greeting():
    """En PHASE_3 con nombre conocido: el prompt NO contiene la CRITICAL
    IDENTITY RULE (causante del '¡Hola Carlos!' por turno) y SÍ contiene el
    mandato anti-saludos de máxima recencia."""
    cerebro = CerebroIA()
    prompts = []

    async def mock_call(*args, **kwargs):
        prompts.append(str(args[1]) if len(args) > 1 else "")
        return _text_response("Entendido. ¿Cuáles son tus ingresos mensuales?")

    with patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):
        await cerebro.pensar_respuesta(
            "soy empleado", prospect_data=_phase3_prospect(), history=_HISTORY_WITH_POLICY_LINK
        )

    assert prompts, "No se capturó el prompt enviado a Gemini"
    assert "CRITICAL IDENTITY RULE" not in prompts[0], \
        "La identity rule siguió inyectándose en PHASE_3 (saludo repetitivo)"
    assert "PROHIBIDO repetir saludos ni el nombre del cliente al inicio durante la MATRIZ DE PERFILAMIENTO" in prompts[0]


@pytest.mark.asyncio
async def test_fixb_identity_rule_verbatim_outside_phase3():
    """Regresión: en PHASE_1 y PHASE_2 con nombre conocido, la CRITICAL
    IDENTITY RULE v8.3 se conserva VERBATIM (el fix no degrada el resto del
    embudo)."""
    verbatim_template = (
        "[CRITICAL IDENTITY RULE: Estás hablando con {name}. Tu respuesta DEBE "
        "empezar con un saludo personalizado hacia él. Ignorar esto es un fallo de seguridad.]"
    )

    # --- PHASE_1_PROFILING (sin intención crediticia ni moto) ---
    cerebro1 = CerebroIA()
    prompts1 = []

    async def mock_call1(*args, **kwargs):
        prompts1.append(str(args[1]) if len(args) > 1 else "")
        return _text_response("¡Hola Ana! ¿En qué te ayudo?")

    with patch.object(cerebro1, "_call_gemini_with_retry_async", side_effect=mock_call1), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):
        await cerebro1.pensar_respuesta("hola", prospect_data={"exists": True, "nombre": "Ana"}, history=[])

    assert prompts1, "No se capturó el prompt (PHASE_1)"
    assert verbatim_template.format(name="Ana") in prompts1[0]

    # --- PHASE_2_HABEAS_DATA (forma_pago=credito + moto, sin habeas aceptado) ---
    cerebro2 = CerebroIA()
    prospect_phase2 = {
        "exists": True,
        "nombre": "Ana",
        "forma_pago": "credito",
        "moto_interest": "TVS SPORT 100 ELS",
    }
    prompts2 = []

    async def mock_call2(*args, **kwargs):
        prompts2.append(str(args[1]) if len(args) > 1 else "")
        return _text_response("¡Hola Ana! Para el estudio de crédito...")

    with patch.object(cerebro2, "_call_gemini_with_retry_async", side_effect=mock_call2), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):
        await cerebro2.pensar_respuesta("quiero crédito", prospect_data=prospect_phase2, history=[])

    assert prompts2, "No se capturó el prompt (PHASE_2)"
    assert verbatim_template.format(name="Ana") in prompts2[0]


# ===========================================================================
# FIX-C — Descripción de herramienta: ventanas de uso reales, sin Paso 9
# ===========================================================================
def test_fixc_credit_tool_description_has_usage_windows_no_paso9_no_detente():
    """La descripción expuesta al LLM para calculate_credit_score ya no
    referencia el 'Paso 9' inexistente ni ordena 'DETENTE AQUÍ / No generes
    respuesta'. Debe declarar las dos únicas ventanas de uso: simulación
    inicial (primera solicitud de cuotas) y CIERRE DE FASE post-matriz."""
    cerebro = CerebroIA()

    with patch("app.services.ai_brain.SDK_AVAILABLE", True):
        tools = cerebro._create_tools({})

    assert tools, "No se generaron herramientas dinámicas"
    declarations = [decl for tool in tools for decl in (tool.function_declarations or [])]
    credit_decl = next((d for d in declarations if d.name == "calculate_credit_score"), None)
    assert credit_decl is not None, "calculate_credit_score ausente del payload de herramientas"

    description = credit_decl.description or ""
    assert "Paso 9" not in description
    assert "DETENTE" not in description
    assert "CIERRE DE FASE" in description
    assert "matriz de perfilamiento" in description
    assert "PROHIBIDO ejecutarla en cada turno de la matriz" in description

    # Los parámetros (incluye campos FIX-4A) quedan intactos
    props = (credit_decl.parameters.properties if credit_decl.parameters else {}) or {}
    for field in ("ocupacion_y_contrato", "ingresos_demostrables", "historial_datacredito",
                  "ingresos_mensuales", "gastos_mensuales", "tiene_gas_natural", "plan_celular"):
        assert field in props, f"Parámetro '{field}' perdido tras FIX-C"
