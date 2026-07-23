"""
[BOT-BUILD-COHERENCE-WAVE07-03-FIRESTORE-NOMENCLATURE-001]
Tests for the <NOMENCLATURA_TECNICA_FIRESTORE> migration decision (ESCENARIO B).

WHY: generate_summary() extracts prospect data via LLM **structured output**
(response_mime_type="application/json" + response_schema=EXTRACTION_SCHEMA).
The Firestore field mapping is enforced BY CODE (EXTRACTION_SCHEMA +
memory_service._merge_extracted_data), so the nomenclature block was removed
from the conversational prompt and documented in ai_brain.py.

These tests pin:
1. Decision — the prompt no longer carries the nomenclature block /
   sys_admin_users, but retains functional field references (C3, PASO 2).
2. Schema contract — EXTRACTION_SCHEMA keeps the mandatory Firestore fields
   (nombre, ciudad, moto_interest, habeas_data_accepted) and profiling fields.
3. Extraction behavior — generate_summary returns the extracted fields
   (nombre, ciudad, ocupacion, datacredito, ...) and sends the CODE schema
   to Gemini (backend is the mapping authority post-migration).
4. Resilience — extraction failure degrades to a safe fallback (no raise).
"""
import json
import os
import sys

import pytest
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION
from app.services.ai_brain import CerebroIA, EXTRACTION_SCHEMA


MANDATORY_FIELDS = ["nombre", "ciudad", "moto_interest", "habeas_data_accepted"]
PROFILING_FIELDS = [
    "ocupacion", "datacredito", "forma_pago", "vivienda", "servicios_publicos",
]


# ============================================================================
# 1. DECISION PINS — prompt post-migration
# ============================================================================

class TestNomenclatureMigrationDecision:
    def test_prompt_has_no_nomenclature_block(self):
        assert "<NOMENCLATURA_TECNICA_FIRESTORE>" not in JUAN_PABLO_SYSTEM_INSTRUCTION

    def test_prompt_has_no_sys_admin_users(self):
        """sys_admin_users (colección interna de admins) sale del prompt;
        queda documentada en ai_brain.py como referencia de backend."""
        assert "sys_admin_users" not in JUAN_PABLO_SYSTEM_INSTRUCTION

    def test_prompt_retains_functional_field_references(self):
        """La funcionalidad se conserva: C3 y el script legal del PASO 2 siguen
        mencionando habeas_data_accepted (no era parte del bloque eliminado)."""
        assert "habeas_data_accepted" in JUAN_PABLO_SYSTEM_INSTRUCTION

    def test_schema_does_not_include_sys_admin_users(self):
        """La colección de admins NO es un campo del prospecto."""
        props = EXTRACTION_SCHEMA["properties"]["extracted"]["properties"]
        assert "sys_admin_users" not in props


# ============================================================================
# 2. SCHEMA CONTRACT — campos obligatorios (constraint del ticket)
# ============================================================================

class TestExtractionSchemaContract:
    @pytest.mark.parametrize("field", MANDATORY_FIELDS)
    def test_mandatory_field_present(self, field):
        props = EXTRACTION_SCHEMA["properties"]["extracted"]["properties"]
        assert field in props, f"Campo obligatorio '{field}' ausente del EXTRACTION_SCHEMA."

    @pytest.mark.parametrize("field", PROFILING_FIELDS)
    def test_profiling_field_present(self, field):
        props = EXTRACTION_SCHEMA["properties"]["extracted"]["properties"]
        assert field in props, f"Campo de perfilamiento '{field}' ausente del EXTRACTION_SCHEMA."

    def test_schema_is_fixed_json_object(self):
        assert EXTRACTION_SCHEMA["type"] == "OBJECT"
        assert EXTRACTION_SCHEMA["required"] == ["summary", "extracted"]


# ============================================================================
# 3. EXTRACTION BEHAVIOR — generate_summary con structured output
# ============================================================================

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


@pytest.mark.asyncio
async def test_generate_summary_extracts_prospect_fields_via_code_schema():
    """GIVEN el LLM devuelve JSON conforme al schema,
    WHEN generate_summary procesa la conversación,
    THEN los campos del prospecto llegan a result['extracted'] y el schema
    enviado a Gemini es EXTRACTION_SCHEMA (autoridad de mapeo en backend)."""
    llm_payload = {
        "summary": "Carlos de Bogotá, empleado al día, interesado en la Raider.",
        "extracted": {
            "nombre": "Carlos",
            "ciudad": "Bogotá",
            "moto_interest": "TVS Raider 125",
            "habeas_data_accepted": True,
            "ocupacion": "Empleado",
            "datacredito": "Al día",
            "forma_pago": "crédito",
        },
    }
    captured: dict = {}
    cerebro = _build_cerebro_for_extraction(_make_json_response(llm_payload), captured)

    result = await cerebro.generate_summary(
        "usuario: me llamo Carlos, soy de Bogotá, empleado al día, quiero la Raider a crédito",
        last_bot_question="¿Me autorizas el tratamiento de tus datos?",
        session_id="test-nomenclature-01",
    )

    extracted = result["extracted"]
    assert extracted["nombre"] == "Carlos"
    assert extracted["ciudad"] == "Bogotá"
    assert extracted["moto_interest"] == "TVS Raider 125"
    assert extracted["habeas_data_accepted"] is True
    assert extracted["ocupacion"] == "Empleado"
    assert extracted["datacredito"] == "Al día"

    # Backend authority pin: el schema fijo de CÓDIGO es el que viaja a Gemini.
    # (GenerateContentConfig normaliza/copia el dict vía pydantic → igualdad profunda.)
    config = captured.get("config")
    assert config is not None, "generate_summary no envió config a Gemini."
    assert config.response_schema == EXTRACTION_SCHEMA
    assert config.response_mime_type == "application/json"


@pytest.mark.asyncio
async def test_generate_summary_sets_habeas_sent_flag_from_physical_link():
    """La presencia física del link de privacidad en el historial marca
    habeas_data_accepted_sent (regla de persistencia síncrona)."""
    llm_payload = {"summary": "s", "extracted": {"nombre": "Ana"}}
    cerebro = _build_cerebro_for_extraction(_make_json_response(llm_payload), {})

    with_link = await cerebro.generate_summary(
        "bot: Política: https://tiendalasmotos.com/politica-de-privacidad usuario: Sí",
        session_id="test-nomenclature-02",
    )
    assert with_link["extracted"]["habeas_data_accepted_sent"] is True

    without_link = await cerebro.generate_summary(
        "usuario: hola, solo estoy mirando motos",
        session_id="test-nomenclature-03",
    )
    assert without_link["extracted"]["habeas_data_accepted_sent"] is False


@pytest.mark.asyncio
async def test_generate_summary_failure_returns_safe_fallback():
    """Zero-Silent-Failures: si Gemini explota, la extracción degrada a un
    fallback seguro con llaves 'summary' y 'extracted' (sin re-raise)."""
    cerebro = CerebroIA()
    cerebro.client = MagicMock()

    async def _explode(func, **kwargs):
        raise RuntimeError("gemini-down")

    cerebro._call_gemini_with_retry_async = _explode

    result = await cerebro.generate_summary(
        "usuario: me llamo Pedro y quiero una moto",
        session_id="test-nomenclature-04",
    )
    assert "summary" in result
    assert result["extracted"] == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
