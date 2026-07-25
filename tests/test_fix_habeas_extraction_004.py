"""
[BOT-BUILD-FIX-HABEAS-DATA-EXTRACTION-004] Pins de certificación.

Causa raíz: el extractor PII de generate_summary() operaba con STRICT NEGATIVE
BIAS: exigía una afirmación DIRECTA y EXPLÍCITA y ordenaba `false` ante cualquier
ambigüedad. En producción el usuario respondía "Sí"/"👍" al script legal y el
extractor seguía devolviendo habeas_data_accepted=False → el embudo re-preguntaba
el consentimiento en bucle y re-saludaba al cliente.

Fix (C1a/C1b/C2/C3/C4):
  - C1a: EXTRACTION_SCHEMA.habeas_data_accepted → STRICT POSITIVE BIAS.
  - C1b: Regla #1 del prompt extractor → STRICT POSITIVE BIAS.
  - C2: Guard determinista backend `_is_habeas_consent_turn()` — backstop de
        código que FUERZA habeas_data_accepted=True cuando el script legal fue
        presentado y el ÚLTIMO mensaje del usuario es una afirmación corta.
  - C3: REGLA DE CONSENTIMIENTO CONFIRMADO en prompts.py (tras PASO 4).
  - C4: interruption_directive prohíbe re-saludar tras consentimiento firmado.

NOTA DE DISEÑO (precedente FIX-SUMMARY-MOTO-INTEREST-001): el compliance del
extractor LLM es probabilístico → los pins estáticos blindan las reglas en el
prompt/schema y los pins de integración certifican el guard determinista de
código (la pieza NO probabilística del fix).
"""

import inspect
import json
import os
import sys

import pytest
from unittest.mock import MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import app.services.ai_brain as ai_brain_module
from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION
from app.services.ai_brain import CerebroIA, EXTRACTION_SCHEMA


# ---------------------------------------------------------------------------
# Mock helpers (patrón de tests/test_firestore_nomenclature_extraction.py)
# ---------------------------------------------------------------------------
def _make_json_response(payload: dict):
    mock_response = MagicMock()
    mock_response.text = json.dumps(payload, ensure_ascii=False)
    mock_response.usage_metadata = MagicMock(
        total_token_count=10, prompt_token_count=8, candidates_token_count=2
    )
    return mock_response


def _build_cerebro_for_extraction(script_response, captured: dict):
    cerebro = CerebroIA()
    cerebro.client = MagicMock()  # truthy → pasa el guard de generate_summary

    async def _fake_call(func, **kwargs):
        captured.update(kwargs)
        return script_response

    cerebro._call_gemini_with_retry_async = _fake_call
    return cerebro


_SCRIPT_LINE = (
    "Bot: Para hacer el estudio formal y validar tu cupo exacto con nuestro "
    "sistema, ¿me autorizas el tratamiento de tus datos? (Política: "
    "https://tiendalasmotos.com/politica-de-privacidad). Solo confírmame con "
    "un 'Sí' o con un emoji de pulgar arriba (👍)."
)
_BOT_QUESTION = (
    "¿me autorizas el tratamiento de tus datos? (Política: "
    "https://tiendalasmotos.com/politica-de-privacidad)."
)


# ===========================================================================
# T1 (estático, C1a) — El schema de extracción porta STRICT POSITIVE BIAS
# ===========================================================================
def test_t1_schema_habeas_data_accepted_strict_positive_bias():
    """EXTRACTION_SCHEMA.habeas_data_accepted debe instruir STRICT POSITIVE BIAS
    (mapear a true ante afirmación tras script legal; false solo ante negación
    explícita o ausencia del script) y ya NO el sesgo negativo."""
    props = EXTRACTION_SCHEMA["properties"]["extracted"]["properties"]
    field = props["habeas_data_accepted"]

    assert field["type"] == "BOOLEAN"
    assert "STRICT POSITIVE BIAS" in field["description"]
    assert "NEGATIVE BIAS" not in field["description"]
    assert "negación explícita" in field["description"]


# ===========================================================================
# T2 (estático-runtime, C1b) — La regla #1 del extractor viaja a Gemini con
# STRICT POSITIVE BIAS y la regla obsoleta NEGATIVE BIAS fue erradicada
# ===========================================================================
@pytest.mark.asyncio
async def test_t2_extractor_prompt_carries_positive_bias_rule():
    """El prompt que generate_summary envía a Gemini debe contener la regla
    habeas_data_accepted con STRICT POSITIVE BIAS y ya NO contener la instrucción
    STRICT NEGATIVE BIAS (causante del bucle de re-pregunta)."""
    llm_payload = {"summary": "s", "extracted": {}}
    captured: dict = {}
    cerebro = _build_cerebro_for_extraction(_make_json_response(llm_payload), captured)

    await cerebro.generate_summary("User: hola, solo estoy mirando", session_id="test-004-t2")

    prompt = str(captured.get("contents", ""))
    assert prompt, "No se capturó el prompt del extractor"

    assert "habeas_data_accepted (STRICT POSITIVE BIAS)" in prompt
    assert "STRICT NEGATIVE BIAS" not in prompt
    assert "NUNCA asumas aceptación por el simple hecho de continuar la charla" not in prompt
    # Nueva semántica pineada
    assert "NIEGA explícitamente" in prompt
    assert "NUNCA fue presentado" in prompt


# ===========================================================================
# T3 (integración, C2) — ESCENARIO DEL TICKET: el LLM devuelve false pero el
# turno es una aceptación determinística → el guard FUERZA true (fin del bucle)
# ===========================================================================
@pytest.mark.asyncio
async def test_t3_guard_forces_true_when_llm_misses_consent():
    """GIVEN el script legal presentado y el usuario respondiendo 'Sí',
    WHEN el extractor LLM (pese al bias positivo) devuelve false,
    THEN el guard determinista backend fuerza habeas_data_accepted=True."""
    llm_payload = {"summary": "s", "extracted": {"habeas_data_accepted": False}}
    cerebro = _build_cerebro_for_extraction(_make_json_response(llm_payload), {})

    conversation = (
        "Bot: Si te interesa a crédito, las cuotas a 24 meses serían "
        "aproximadamente de $180.000.\n"
        f"{_SCRIPT_LINE}\n"
        "User: Sí"
    )
    result = await cerebro.generate_summary(
        conversation,
        last_bot_question=_BOT_QUESTION,
        session_id="test-004-t3",
    )

    assert result["extracted"]["habeas_data_accepted"] is True
    # La persistencia síncrona del script sigue intacta (mecanismo complementario)
    assert result["extracted"]["habeas_data_accepted_sent"] is True


# ===========================================================================
# T4 (unitario, C2) — Tabla de verdad del guard determinista
# _is_habeas_consent_turn: afirmaciones cortas tras script → True;
# negaciones/preguntas/muros de texto/sin script → False (jamás fuerza)
# ===========================================================================
@pytest.mark.parametrize(
    "conversation,last_bot_question,expected",
    [
        # Afirmaciones directas y cortas tras el script → True
        (f"{_SCRIPT_LINE}\nUser: Sí", _BOT_QUESTION, True),
        (f"{_SCRIPT_LINE}\nUser: si", _BOT_QUESTION, True),
        (f"{_SCRIPT_LINE}\nUser: Sí, acepto", _BOT_QUESTION, True),
        (f"{_SCRIPT_LINE}\nUser: Acepto", _BOT_QUESTION, True),
        (f"{_SCRIPT_LINE}\nUser: Dale", _BOT_QUESTION, True),
        (f"{_SCRIPT_LINE}\nUser: Listo", _BOT_QUESTION, True),
        (f"{_SCRIPT_LINE}\nUser: Ok", _BOT_QUESTION, True),
        (f"{_SCRIPT_LINE}\nUser: Claro", _BOT_QUESTION, True),
        (f"{_SCRIPT_LINE}\nUser: Bueno, sí", _BOT_QUESTION, True),
        (f"{_SCRIPT_LINE}\nUser: ajá", _BOT_QUESTION, True),
        (f"{_SCRIPT_LINE}\nUser: 👍", _BOT_QUESTION, True),
        (f"{_SCRIPT_LINE}\nUser: 👍👍", _BOT_QUESTION, True),
        # Script detectado SOLO vía última pregunta del bot (sin link en historial) → True
        ("Bot: ¿me autorizas el tratamiento de tus datos?\nUser: Sí", _BOT_QUESTION, True),
        # Historial con prefijos en español (formato legacy de tests) → True
        (f"{_SCRIPT_LINE}\nusuario: Sí", _BOT_QUESTION, True),
        # Negación explícita → False (jamás fuerza sobre la voluntad del usuario)
        (f"{_SCRIPT_LINE}\nUser: No, todavía no", _BOT_QUESTION, False),
        (f"{_SCRIPT_LINE}\nUser: Nel", _BOT_QUESTION, False),
        (f"{_SCRIPT_LINE}\nUser: 👎", _BOT_QUESTION, False),
        # Pregunta/ambigüedad → False (el guard no decide; decide el LLM)
        (f"{_SCRIPT_LINE}\nUser: ¿qué requisitos hay?", _BOT_QUESTION, False),
        (f"{_SCRIPT_LINE}\nUser: Sí, pero ¿y la cuota?", _BOT_QUESTION, False),
        # Muro de texto (>60 chars) → False (consentimiento debe ser corto y directo)
        (
            f"{_SCRIPT_LINE}\nUser: Sí, pero primero quiero saber todos los "
            "requisitos del crédito y los plazos",
            _BOT_QUESTION,
            False,
        ),
        # Sin script legal presentado → False (la afirmación sola NO basta)
        ("Bot: ¿Desde qué ciudad nos escribes?\nUser: Sí", "¿Desde qué ciudad nos escribes?", False),
        ("User: Sí", "", False),
        # Sin turno de usuario detectable → False
        ("", _BOT_QUESTION, False),
    ],
)
def test_t4_is_habeas_consent_turn_truth_table(conversation, last_bot_question, expected):
    cerebro = CerebroIA()
    assert cerebro._is_habeas_consent_turn(conversation, last_bot_question) is expected


# ===========================================================================
# T5 (integración, C2) — El guard NUNCA fuerza: sin script legal la afirmación
# no basta; ante negación explícita se respeta el false del extractor
# ===========================================================================
@pytest.mark.asyncio
async def test_t5_guard_never_forces_without_script_or_on_denial():
    llm_payload = {"summary": "s", "extracted": {"habeas_data_accepted": False}}
    cerebro = _build_cerebro_for_extraction(_make_json_response(llm_payload), {})

    # A) Afirmación sin script legal presentado → el guard NO interviene
    without_script = await cerebro.generate_summary(
        "Bot: ¿Desde qué ciudad nos escribes?\nUser: Sí",
        last_bot_question="¿Desde qué ciudad nos escribes?",
        session_id="test-004-t5a",
    )
    assert without_script["extracted"]["habeas_data_accepted"] is False

    # B) Negación explícita tras el script → el guard respeta la voluntad
    denial = await cerebro.generate_summary(
        f"{_SCRIPT_LINE}\nUser: No, todavía no",
        last_bot_question=_BOT_QUESTION,
        session_id="test-004-t5b",
    )
    assert denial["extracted"]["habeas_data_accepted"] is False


# ===========================================================================
# T6 (estático, C3+C4) — Guardrails de prompt pineados: REGLA DE CONSENTIMIENTO
# CONFIRMADO en prompts.py y prohibición de re-saludo en interruption_directive
# ===========================================================================
def test_t6_prompt_guardrails_pinned():
    # C3: prompts.py — tras PASO 4, anti re-pregunta del consentimiento
    assert "REGLA DE CONSENTIMIENTO CONFIRMADO" in JUAN_PABLO_SYSTEM_INSTRUCTION
    assert "asume habeas_data_accepted = true y NO vuelvas a preguntar" in JUAN_PABLO_SYSTEM_INSTRUCTION
    assert "Avanza inmediatamente a pedir Nombre y Ciudad" in JUAN_PABLO_SYSTEM_INSTRUCTION

    # C4: ai_brain.py — interruption_directive anti re-saludo post-consentimiento
    source = inspect.getsource(ai_brain_module)
    assert "PROHIBIDO saludar o presentarte de nuevo" in source
    assert "ve directo a la solicitud de identidad" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
