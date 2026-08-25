"""
Pines para BOT-BUILD-HYBRID-BACKSTOP-PASO2-100.

Acota CERO_TOOL_PREMATURO al contexto MATRIZ; PASO 1/PASO 2 deben poder
ejecutar calculate_credit_score (simulación ciega / excepción de crédito)
sin que el backstop lo stripé.
"""
from __future__ import annotations

import pytest

from app.services.hybrid_llm_router import (
    RoutingDecision,
    _ResponseShim,
    _is_matrix_context,
    _should_backstop,
)


class _FakeToolShim(_ResponseShim):
    """Shim que expone tool_calls sin requerir la estructura genai completa."""

    def __init__(self, text: str | None, tool_calls: list[dict] | None = None):
        super().__init__(
            text=text,
            parts=[{"type": "text", "text": text or ""}],
            tool_calls=tool_calls,
        )


def _credit_tool() -> list[dict]:
    return [{"name": "calculate_credit_score", "args": {"entidad": "Brilla de Gases"}}]


# ---------------------------------------------------------------------------
# Contexto MATRIZ
# ---------------------------------------------------------------------------
class TestMatrixContext:
    def test_turno_1_profiling_with_credit_tool_is_backstopped(self) -> None:
        decision = RoutingDecision(
            provider="deepseek",
            reason="turno_1_profiling",
            captured_count=0,
            siguiente_pendiente="Ocupación",
            fase="PHASE_3_CREDIT_PROFILING",
        )
        shim = _FakeToolShim(text="¿A qué te dedicas?", tool_calls=_credit_tool())
        backstop, reason = _should_backstop(decision, shim)
        assert backstop is True
        assert reason == "backstop_tool_prematuro"

    def test_turno_medio_profiling_with_credit_tool_is_backstopped(self) -> None:
        decision = RoutingDecision(
            provider="deepseek",
            reason="turno_6_profiling",
            captured_count=5,
            siguiente_pendiente="Gas natural (Brilla)",
            fase="PHASE_3_CREDIT_PROFILING",
        )
        shim = _FakeToolShim(text="¿Tienes gas?", tool_calls=_credit_tool())
        backstop, reason = _should_backstop(decision, shim)
        assert backstop is True
        assert reason == "backstop_tool_prematuro"

    def test_frontera_with_credit_tool_is_backstopped(self) -> None:
        decision = RoutingDecision(
            provider="gemini",
            reason="frontera_turno_7_matriz",
            captured_count=7,
            siguiente_pendiente="Plan celular",
            fase="PHASE_3_CREDIT_PROFILING",
        )
        shim = _FakeToolShim(text="¿Tienes plan celular?", tool_calls=_credit_tool())
        backstop, reason = _should_backstop(decision, shim)
        assert backstop is True
        assert reason == "backstop_tool_prematuro"

    def test_cierre_with_credit_tool_is_not_backstopped(self) -> None:
        decision = RoutingDecision(
            provider="gemini",
            reason="cierre_fase_completo",
            captured_count=8,
            siguiente_pendiente="COMPLETO",
            fase="PHASE_3_CREDIT_PROFILING",
        )
        shim = _FakeToolShim(text="¡Listo!", tool_calls=_credit_tool())
        backstop, reason = _should_backstop(decision, shim)
        assert backstop is False
        assert reason == ""

    def test_desviacion_orden_unchanged(self) -> None:
        decision = RoutingDecision(
            provider="deepseek",
            reason="turno_6_profiling",
            captured_count=5,
            siguiente_pendiente="Gas natural (Brilla)",
            fase="PHASE_3_CREDIT_PROFILING",
        )
        # Una pregunta, pero no del campo esperado (evita substrings "gas").
        shim = _FakeToolShim(text="¿Cómo te llamas?", tool_calls=[])
        backstop, reason = _should_backstop(decision, shim)
        assert backstop is True
        assert reason == "backstop_desviacion_orden"


# ---------------------------------------------------------------------------
# PASO 1 / PASO 2
# ---------------------------------------------------------------------------
class TestPaso2NotBackstopped:
    def test_r4_simulacion_ciega_paso2_with_credit_tool_is_allowed(self) -> None:
        decision = RoutingDecision(
            provider="gemini",
            reason="simulacion_ciega_paso2",
            captured_count=0,
            siguiente_pendiente=None,
            fase="PHASE_2_HABEAS_DATA",
        )
        shim = _FakeToolShim(text=None, tool_calls=_credit_tool())
        backstop, reason = _should_backstop(decision, shim)
        assert backstop is False
        assert reason == ""

    def test_paso2_exception_phase1_with_credit_tool_is_allowed(self) -> None:
        decision = RoutingDecision(
            provider="gemini",
            reason="default_conservador",
            captured_count=0,
            siguiente_pendiente=None,
            fase="PHASE_1_PROFILING",
        )
        shim = _FakeToolShim(text=None, tool_calls=_credit_tool())
        backstop, reason = _should_backstop(decision, shim)
        assert backstop is False
        assert reason == ""

    def test_paso1_default_none_with_credit_tool_is_allowed(self) -> None:
        decision = RoutingDecision(
            provider="gemini",
            reason="default_conservador",
            captured_count=0,
            siguiente_pendiente=None,
            fase=None,
        )
        shim = _FakeToolShim(text=None, tool_calls=_credit_tool())
        backstop, reason = _should_backstop(decision, shim)
        assert backstop is False
        assert reason == ""


# ---------------------------------------------------------------------------
# Mordidas de arquitectura
# ---------------------------------------------------------------------------
class TestBackstopMordidas:
    def test_sin_is_matrix_context_paso2_vuelve_a_strip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Si _is_matrix_context siempre devuelve True, PASO 2 se vuelve a strip."""
        monkeypatch.setattr("app.services.hybrid_llm_router._is_matrix_context", lambda decision: True)

        decision = RoutingDecision(
            provider="gemini",
            reason="simulacion_ciega_paso2",
            captured_count=0,
            siguiente_pendiente=None,
            fase="PHASE_2_HABEAS_DATA",
        )
        shim = _FakeToolShim(text=None, tool_calls=_credit_tool())
        backstop, reason = _should_backstop(decision, shim)
        assert backstop is True
        assert reason == "backstop_tool_prematuro"

    def test_condicion_por_reason_no_cubre_phase1_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Si se eximiera solo R4 (reason==simulacion_ciega_paso2), el PASO 2 en PHASE_1 falla."""
        # Emula una implementación defectuosa que trata como MATRIZ todo lo que NO es R4.
        monkeypatch.setattr(
            "app.services.hybrid_llm_router._is_matrix_context",
            lambda decision: decision.reason != "simulacion_ciega_paso2",
        )

        decision = RoutingDecision(
            provider="gemini",
            reason="default_conservador",
            captured_count=0,
            siguiente_pendiente=None,
            fase="PHASE_1_PROFILING",
        )
        shim = _FakeToolShim(text=None, tool_calls=_credit_tool())
        backstop, reason = _should_backstop(decision, shim)
        assert backstop is True
        assert reason == "backstop_tool_prematuro"


# ---------------------------------------------------------------------------
# Helper _is_matrix_context
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "fase,captured,siguiente,expected",
    [
        ("PHASE_3_CREDIT_PROFILING", 0, "Ocupación", True),
        ("PHASE_3_CREDIT_PROFILING", 5, "Gas natural (Brilla)", True),
        (None, 7, "Plan celular", True),
        ("PHASE_3_CREDIT_PROFILING", 8, "COMPLETO", True),
        ("PHASE_2_HABEAS_DATA", 0, None, False),
        ("PHASE_1_PROFILING", 0, None, False),
        (None, 0, None, False),
        (None, 0, "COMPLETO", False),
    ],
)
def test_is_matrix_context(fase: str | None, captured: int, siguiente: str | None, expected: bool) -> None:
    decision = RoutingDecision(
        provider="gemini",
        reason="test",
        captured_count=captured,
        siguiente_pendiente=siguiente,
        fase=fase,
    )
    assert _is_matrix_context(decision) is expected
