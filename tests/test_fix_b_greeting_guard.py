"""
Tests FIX-B Ampliado — [BOT-PLAN-HARDENING-EGRESS-FUNNEL-001] (Fase 4).

Guard estático anti-saludo: si `prospect_data["ocupacion"]` es truthy, TODO
saludo de apertura ("¡Hola, [Nombre]!") se suprime INDEPENDIENTEMENTE de la
fase-string en la que se encuentre el bot.

Doble capa certificada:
1. Capa de prompt (ai_brain.py L1882-1895): con ocupacion truthy se inyecta el
   mandato anti-saludos y NUNCA la CRITICAL IDENTITY RULE (que ordenaba saludar).
2. Capa coercitiva post-generación (_strip_leading_greeting, en la cadena de
   post-proceso de pensar_respuesta): supresión determinista del prefijo de
   saludo residual, como defensa en profundidad.
"""

import inspect
import pathlib
import re

import pytest

from app.services.ai_brain import CerebroIA
from tests.test_faq_and_location_tools import (
    _build_cerebro_with_scripted_chat,
    _make_text_response,
)

PRIVACY_LINK = "https://tiendalasmotos.com/politica-de-privacidad"
ANTI_GREETING = "PROHIBIDO repetir saludos ni el nombre del cliente"
IDENTITY_RULE = "CRITICAL IDENTITY RULE"

# Las 3 fases reales de la máquina de estados + una fase arbitraria/legada
# (defensa contra valores de fase desconocidos o futuros).
ALL_PHASES = [
    "PHASE_1_PROFILING",
    "PHASE_2_HABEAS_DATA",
    "PHASE_3_CREDIT_PROFILING",
    "PHASE_UNKNOWN_LEGACY",
]


def _prospect_for_phase(phase: str) -> dict:
    base = {"exists": True, "nombre": "Carlos", "ocupacion": "Empleado"}
    if phase == "PHASE_1_PROFILING":
        return base  # sin moto_interest ni forma_pago → fase por defecto
    if phase == "PHASE_2_HABEAS_DATA":
        return {**base, "moto_interest": "Raider 125", "forma_pago": "crédito",
                "habeas_data_accepted": False}
    if phase == "PHASE_3_CREDIT_PROFILING":
        return {**base, "ciudad": "Bogotá", "moto_interest": "Raider 125",
                "habeas_data_accepted": True, "habeas_data_accepted_sent": True}
    return base  # fase desconocida: mismo prospecto base


def _history_for_phase(phase: str) -> list:
    if phase == "PHASE_3_CREDIT_PROFILING":
        return [
            {"role": "model", "content": f"¿me autorizas el tratamiento de tus datos? (Política: {PRIVACY_LINK})"},
            {"role": "user", "content": "Sí, autorizo"},
        ]
    return []


# ---------------------------------------------------------------------------
# Capa 1 — Guard de prompt (ocupacion truthy en las fases reales)
# ---------------------------------------------------------------------------

class TestPromptLayerGuard:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("phase", ALL_PHASES[:3])
    async def test_anti_greeting_injected_with_occupation_in_any_phase(self, phase):
        cerebro, sent_payloads = _build_cerebro_with_scripted_chat([
            _make_text_response("Tus datos están registrados. ¿Cuáles son tus gastos mensuales?"),
        ])
        await cerebro.pensar_respuesta(
            texto="continuemos",
            prospect_data=_prospect_for_phase(phase),
            history=_history_for_phase(phase),
        )
        prompt = str(sent_payloads[0])
        assert ANTI_GREETING in prompt, f"Falta mandato anti-saludos con ocupacion truthy en {phase}"
        assert IDENTITY_RULE not in prompt, f"CRITICAL IDENTITY RULE presente con ocupacion truthy en {phase}"

    @pytest.mark.asyncio
    async def test_identity_rule_preserved_without_occupation(self):
        """Control: sin ocupacion (embudo temprano) la CRITICAL IDENTITY RULE se
        conserva VERBATIM — el saludo de primer contacto es legítimo."""
        cerebro, sent_payloads = _build_cerebro_with_scripted_chat([
            _make_text_response("¡Hola! ¿Con quién tengo el gusto?"),
        ])
        await cerebro.pensar_respuesta(
            texto="hola",
            prospect_data={"exists": True, "nombre": "Carlos"},
            history=[],
        )
        prompt = str(sent_payloads[0])
        assert IDENTITY_RULE in prompt
        assert ANTI_GREETING not in prompt


# ---------------------------------------------------------------------------
# Capa 2 — Supresor coercitivo post-generación
# ---------------------------------------------------------------------------

class TestCoercivePrefixSuppressor:
    @pytest.mark.parametrize("phase", ALL_PHASES)
    def test_strip_leading_greeting_is_phase_independent(self, phase):
        """La función pura no conoce fases: el prefijo de saludo se suprime igual
        en las 3 fases reales y en una fase arbitraria/legada."""
        _ = phase  # la fase es irrelevante por contrato; parametrize documenta el alcance
        out = CerebroIA._strip_leading_greeting(
            "¡Hola, Carlos! Tus ingresos están registrados. ¿Cuáles son tus gastos mensuales?",
            name="Carlos",
        )
        assert not out.startswith("¡Hola")
        assert out.startswith("Tus ingresos")
        assert "¿Cuáles son tus gastos mensuales?" in out

    def test_strip_variants(self):
        cases = [
            ("¡Hola! ¿Cómo estás?", "Carlos", "¿Cómo estás?"),
            ("Hola, ¿cómo estás?", None, "¿cómo estás?"),
            ("Buenos días, tu cuota quedó lista.", "Carlos", "Tu cuota quedó lista."),
            ("¡Hola Carlos! 👋 Mira esta moto.", "Carlos", "Mira esta moto."),
        ]
        for text, name, expected_start in cases:
            out = CerebroIA._strip_leading_greeting(text, name=name)
            assert out.startswith(expected_start), f"{text!r} → {out!r}"

    def test_non_greeting_text_unchanged(self):
        text = "La TVS Sport 100 cuesta $5.999.000. ¿Te animas?"
        assert CerebroIA._strip_leading_greeting(text, name="Carlos") == text

    def test_never_returns_empty(self):
        text = "¡Hola!"
        assert CerebroIA._strip_leading_greeting(text, name="Carlos") == text

    @pytest.mark.asyncio
    async def test_end_to_end_greeting_suppressed_with_occupation(self):
        """El LLM desobedece el prompt y abre con saludo: la capa coercitiva lo
        suprime antes de que el texto salga de pensar_respuesta."""
        cerebro, _ = _build_cerebro_with_scripted_chat([
            _make_text_response("¡Hola, Carlos! Entendido, tus ingresos quedan registrados. ¿Cuáles son tus gastos mensuales?"),
        ])
        result = await cerebro.pensar_respuesta(
            texto="gano 2 millones",
            prospect_data=_prospect_for_phase("PHASE_3_CREDIT_PROFILING"),
            history=_history_for_phase("PHASE_3_CREDIT_PROFILING"),
        )
        assert not result.startswith("¡Hola")
        assert "¿Cuáles son tus gastos mensuales?" in result

    @pytest.mark.asyncio
    async def test_end_to_end_greeting_kept_without_occupation(self):
        """Control: sin ocupacion el supresor NO actúa (saludo legítimo)."""
        cerebro, _ = _build_cerebro_with_scripted_chat([
            _make_text_response("¡Hola! Qué gusto saludarte. ¿Con quién tengo el gusto?"),
        ])
        result = await cerebro.pensar_respuesta(
            texto="hola",
            prospect_data={"exists": True},
            history=[],
        )
        assert result.startswith("¡Hola!")


# ---------------------------------------------------------------------------
# Pins estáticos anti-regresión
# ---------------------------------------------------------------------------

class TestStaticPins:
    def test_identity_rule_branch_guarded_by_occupation(self):
        """La rama que inyecta CRITICAL IDENTITY RULE debe estar guardada por la
        condición de datos (has_occupation), no solo por la fase-string."""
        src = (pathlib.Path(__file__).resolve().parents[1] / "app/services/ai_brain.py").read_text(encoding="utf-8")
        assert "has_occupation" in src
        assert re.search(
            r'if phase == "PHASE_3_CREDIT_PROFILING" or has_occupation:',
            src,
        ), "El guard anti-saludos volvió a condicionarse solo por fase (FIX-B regresión)"

    def test_suppressor_wired_in_postprocessing_chain(self):
        src = inspect.getsource(CerebroIA.pensar_respuesta)
        assert "_strip_leading_greeting" in src
        assert 'prospect_data.get("ocupacion")' in src
