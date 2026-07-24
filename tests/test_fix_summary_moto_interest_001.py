"""
[BOT-BUILD-FIX-SUMMARY-MOTO-INTEREST-001] Pins de certificación (FIX-SUMMARY-1).

Milestone 3 - Etapa 4: Corrección de pérdida de contexto en generate_summary.

Causa raíz: la regla de extracción de 'moto_interest' ordenaba "Si el usuario
menciona una marca de la competencia, déjalo vacío o no la extraigas". Tras un
turno de competencia (ej. '¿Tienen la Boxer?') donde el bot YA pivotó a un
equivalente del catálogo (FIX-1: Boxer → TVS Sport 100), el extractor borraba
el interés → Firestore con moto_interest ausente → pérdida total de contexto
en el Turno 2.

FIX-SUMMARY-1: la línea obsoleta se reemplaza por la REGLA DE PIVOTE — extraer
el modelo del catálogo ofrecido por el bot; vacío SOLO si no hay ninguna moto
del catálogo mencionada o recomendada en la conversación. La REGLA DE
PERSISTENCIA (moto ya en DB) queda intacta como mecanismo complementario.

NOTA DE DISEÑO (precedente FIX-MATRIX-RESTART-001): el compliance del
extractor LLM es probabilístico → el pin estático blinda la regla en el
prompt; el pin de integración certifica la cadena prompt→parseo→persistencia.
La verificación empírica real queda en el gate post-deploy del Auditor.
"""

import json
from unittest.mock import MagicMock

import pytest

from app.services.ai_brain import CerebroIA


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


_PIVOT_HISTORY = (
    "Usuario: ¿Tienen la Boxer CT 100?\n"
    "Juan Pablo: No manejo la Boxer directamente, pero tengo la TVS Sport 100 ELS "
    "que es su equivalente ideal. ![TVS Sport 100 ELS](https://img/tvs.png) Precio: $5.299.000.\n"
    "Usuario: ¿De cuánto sería la cuota?"
)


# ===========================================================================
# Pin 1 (estático) — La REGLA DE PIVOTE viaja en el prompt; la orden obsoleta
# de borrar el interés ante competencia fue erradicada
# ===========================================================================
@pytest.mark.asyncio
async def test_fix_summary1_prompt_carries_pivot_rule_and_not_obsolete_wipe():
    """El prompt que generate_summary envía a Gemini debe contener la REGLA DE
    PIVOTE (extraer el equivalente de catálogo ofrecido por el bot) y YA NO
    contener la instrucción 'déjalo vacío o no la extraigas' ante competencia
    (causante de la pérdida de contexto)."""
    llm_payload = {"summary": "s", "extracted": {"moto_interest": "TVS Sport 100 ELS"}}
    captured: dict = {}
    cerebro = _build_cerebro_for_extraction(_make_json_response(llm_payload), captured)

    await cerebro.generate_summary(_PIVOT_HISTORY, session_id="test-pivot-static")

    prompt = str(captured.get("contents", ""))
    assert prompt, "No se capturó el prompt del extractor"

    # REGLA DE PIVOTE presente con su semántica completa
    assert "REGLA DE PIVOTE" in prompt
    assert "DEBES extraer el modelo del catálogo ofrecido" in prompt
    assert "NO la marca de competencia" in prompt

    # Instrucción obsoleta erradicada (borrado ante competencia)
    assert "déjalo vacío o no la extraigas" not in prompt
    assert "PROHIBIDO guardar marcas de la competencia" not in prompt

    # La guarda anti-competencia se conserva: solo modelos de Tienda Las Motos
    assert "INMUTABLE contra la competencia" in prompt

    # Mecanismo complementario intacto (NO tocado por el fix)
    assert "REGLA DE PERSISTENCIA - MOTO DE INTERÉS" in prompt


# ===========================================================================
# Pin 2 (integración) — Escenario del ticket: pivote Boxer → TVS Sport 100
# persiste moto_interest (no se pierde el contexto del Turno 2)
# ===========================================================================
@pytest.mark.asyncio
async def test_fix_summary1_competitor_pivot_persists_catalog_moto_interest():
    """Historial con mención de competencia ('¿Tienen la Boxer?') + pivote del
    bot a equivalente de catálogo ('TVS Sport 100') → generate_summary devuelve
    moto_interest con el modelo DEL CATÁLOGO (no vacío, no la competencia), y
    el prompt enviado porta la REGLA DE PIVOTE junto al historial del pivote."""
    llm_payload = {
        "summary": "Usuario preguntó por Boxer; se le ofreció TVS Sport 100 ELS y pidió cuota.",
        "extracted": {
            "moto_interest": "TVS Sport 100",
            "forma_pago": "crédito",
        },
    }
    captured: dict = {}
    cerebro = _build_cerebro_for_extraction(_make_json_response(llm_payload), captured)

    result = await cerebro.generate_summary(
        _PIVOT_HISTORY,
        last_bot_question="¿Desde qué ciudad nos escribes?",
        session_id="test-pivot-integration",
    )

    # El interés persistido es el equivalente de catálogo — no vacío ni 'Boxer'
    assert result["extracted"]["moto_interest"] == "TVS Sport 100"
    assert "boxer" not in result["extracted"]["moto_interest"].lower()

    # El extractor recibió el escenario completo y la regla de pivote
    prompt = str(captured.get("contents", ""))
    assert "REGLA DE PIVOTE" in prompt
    assert "¿Tienen la Boxer CT 100?" in prompt
    assert "TVS Sport 100 ELS" in prompt
