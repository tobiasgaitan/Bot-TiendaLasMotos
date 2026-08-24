"""Router híbrido para evaluación P3-EXT (scripts/china_eval).

Replica la lógica de producción en app/services/hybrid_llm_router.py pero usando
los clientes OpenRouter del eval (OpenRouterClient) para DeepSeek y Gemini fallback.
Esto permite validar COND-3 sin depender del SDK google-genai en el entorno de eval.

Fixes BOT-BUILD-LLMROUTER-FIX-092:
- Parser usa únicamente el último bloque <estado_perfilamiento>.
- Backstop de tool prematuro como guard post-respuesta en ambas rutas.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from typing import Any, Optional

from scripts.china_eval.common.clients import LLMResponse, OpenRouterClient, get_client

logger = logging.getLogger("china_eval.hybrid_router")

FIELD_KEYWORDS: dict[str, list[str]] = {
    "Ocupación": ["ocupación", "ocupacion", "trabajas", "dedicas", "empleo", "trabajo", "a qué te dedicas", "a que te dedicas"],
    "Contrato": ["contrato", "tipo de contrato", "vinculación", "vinculacion", "vínculo", "vinculo"],
    "Ingresos": ["ingresos", "ingreso", "gana", "ganas", "salario", "devenga", "mensuales", "cuánto ganas", "cuanto ganas"],
    "Reportes Datacrédito": ["datacrédito", "datacredito", "reportes", "reportado", "historial crediticio", "reporte"],
    "Gastos mensuales": ["gastos", "gasto", "egresos", "egreso", "cuánto gastas", "cuanto gastas"],
    "Gas natural (Brilla)": ["gas", "brilla", "natural", "servicio de gas"],
    "Vivienda": ["vivienda", "casa", "vives", "hogar", "tipo de vivienda", "en qué vives"],
    "Plan celular": ["celular", "plan", "móvil", "movil", "plan celular", "tienes celular"],
}

# Réplica READ-ONLY de app/services/ai_brain.py::_PROFILING_QUESTION_MAP para la
# red determinista final: si Gemini (fallback) también emite un tool-call
# prematuro, sintetizamos la pregunta canónica del dato pendiente.
CANONICAL_QUESTION: dict[str, str] = {
    "Ocupación": "¿A qué te dedicas actualmente?",
    "Contrato": "¿Qué tipo de contrato tienes?",
    "Ingresos": "¿Cuáles son tus ingresos mensuales?",
    "Reportes Datacrédito": "¿Has tenido reportes en Datacrédito?",
    "Gastos mensuales": "¿Cuánto son tus gastos mensuales aproximadamente?",
    "Gas natural (Brilla)": "¿Cuentas con servicio de gas natural domiciliario?",
    "Vivienda": "¿Cuál es tu tipo de vivienda?",
    "Plan celular": "¿Tienes plan celular a tu nombre?",
}

_CHECKLIST_BLOCK_RE = re.compile(r"<estado_perfilamiento>.*?</estado_perfilamiento>", re.DOTALL)


@dataclass(frozen=True)
class RoutingDecision:
    provider: str
    reason: str
    captured_count: int
    siguiente_pendiente: Optional[str]


def _extract_last_checklist(prompt_text: str) -> str:
    """Extrae el último bloque <estado_perfilamiento> del prompt.

    El eval inyecta un checklist nuevo en cada mensaje de usuario; por eso
    el prompt acumula N bloques históricos. Solo el último refleja el estado
    real del turno actual.
    """
    blocks = _CHECKLIST_BLOCK_RE.findall(prompt_text)
    return blocks[-1] if blocks else ""


def _parse_profiling_state(prompt_text: str) -> tuple[int, Optional[str]]:
    latest = _extract_last_checklist(prompt_text)
    captured_count = len(re.findall(r'<item[^>]+estado="CAPTURADO"', latest))
    m = re.search(r"<siguiente_pendiente>([^<]+)</siguiente_pendiente>", latest)
    siguiente = m.group(1).strip() if m else None
    return captured_count, siguiente


def route_by_context(prompt_text: str) -> RoutingDecision:
    """Decide proveedor según el prompt; nunca falla abierto."""
    try:
        captured_count, siguiente = _parse_profiling_state(prompt_text)
        if siguiente == "COMPLETO":
            return RoutingDecision("gemini", "cierre_fase_completo", captured_count, siguiente)
        if captured_count > 0 or "PHASE_3_CREDIT_PROFILING" in prompt_text:
            if captured_count >= 7:
                return RoutingDecision("gemini", "frontera_turno_7_matriz", captured_count, siguiente)
            return RoutingDecision("deepseek", f"turno_{captured_count + 1}_profiling", captured_count, siguiente)
        return RoutingDecision("deepseek", "default_profiling", captured_count, siguiente)
    except Exception as exc:
        logger.exception("[HYBRID EVAL] route_by_context falló: %s", exc)
        return RoutingDecision("gemini", "route_fallback_gemini", -1, None)


def _count_questions(text: str | None) -> int:
    return text.count("?") if text else 0


def _matches_expected_field(text: str | None, expected_field: str | None) -> bool:
    if not text or not expected_field:
        return False
    lowered = text.lower()
    return any(kw.lower() in lowered for kw in FIELD_KEYWORDS.get(expected_field, []))


def _has_premature_credit_tool(tool_calls: list[dict[str, Any]], siguiente: Optional[str]) -> bool:
    """True si hay calculate_credit_score y la matriz NO está completa."""
    if siguiente == "COMPLETO":
        return False
    return any(tc.get("function", {}).get("name") == "calculate_credit_score" for tc in tool_calls)


def _should_backstop(
    decision: RoutingDecision,
    content: str | None,
    tool_calls: list[dict[str, Any]],
) -> tuple[bool, str]:
    if _has_premature_credit_tool(tool_calls, decision.siguiente_pendiente):
        return True, "backstop_tool_prematuro"
    if decision.siguiente_pendiente and decision.siguiente_pendiente != "COMPLETO":
        if _count_questions(content) == 1 and not _matches_expected_field(content, decision.siguiente_pendiente):
            return True, "backstop_desviacion_orden"
    return False, ""


def _build_corrective_message(reason: str) -> dict[str, str]:
    if reason == "backstop_tool_prematuro":
        return {
            "role": "user",
            "content": (
                "[CORRECCIÓN DE SISTEMA] ERROR: TOOL-CALL PREMATURO. "
                "No invoques calculate_credit_score hasta que el checklist indique COMPLETO. "
                "Continúa el perfilamiento con la única pregunta pendiente."
            ),
        }
    return {
        "role": "user",
        "content": (
            "[CORRECCIÓN DE SISTEMA] ERROR: DESVIACIÓN DE ORDEN. "
            "Ajusta la pregunta final al dato indicado en <siguiente_pendiente>."
        ),
    }


def _strip_premature_tool_calls(resp: LLMResponse) -> LLMResponse:
    """Red determinista final: elimina tool_calls prematuros del payload."""
    safe_content = resp.content or ""
    # Si no queda contenido textual, sintetizamos la pregunta canónica más
    # adelante; aquí solo limpiamos el campo tool_calls.
    return replace(resp, tool_calls=[], content=safe_content)


def _synthesize_canonical_question(siguiente: Optional[str]) -> str:
    return CANONICAL_QUESTION.get(siguiente or "", "¿Me confirmas el dato que falta?")


class HybridEvalRouter:
    """Router híbrido de evaluación usando OpenRouterClient para ambos proveedores."""

    def __init__(
        self,
        deepseek_provider: str = "deepseek",
        gemini_provider: str = "glm52",
    ) -> None:
        self.deepseek_client = get_client(deepseek_provider)
        self.gemini_client = get_client(gemini_provider)

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Rutea, ejecuta y aplica backstop doble si cualquier LLM falla."""
        prompt_text = "\n".join(
            str(m.get("content", "")) for m in messages if isinstance(m, dict)
        )
        decision = route_by_context(prompt_text)
        logger.info(
            "[HYBRID EVAL ROUTE] provider=%s reason=%s captured=%s siguiente=%s",
            decision.provider,
            decision.reason,
            decision.captured_count,
            decision.siguiente_pendiente,
        )

        if decision.provider == "gemini":
            resp = self.gemini_client.chat_completion(messages, tools=tools)
        else:
            resp = self.deepseek_client.chat_completion(messages, tools=tools)

        # Guard post-respuesta: apply backstop según el resultado real.
        resp = self._apply_backstop(
            resp=resp,
            decision=decision,
            messages=messages,
            tools=tools,
            depth=0,
        )
        return resp

    def _apply_backstop(
        self,
        resp: LLMResponse,
        decision: RoutingDecision,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        depth: int,
    ) -> LLMResponse:
        """Aplica backstop doble; máximo 1 re-enrute a Gemini."""
        backstop, reason = _should_backstop(decision, resp.content, resp.tool_calls)
        if not backstop:
            return resp

        logger.warning(
            "[HYBRID EVAL BACKSTOP] reason=%s captured=%s siguiente=%s depth=%s",
            reason,
            decision.captured_count,
            decision.siguiente_pendiente,
            depth,
        )

        if reason == "backstop_tool_prematuro":
            logger.warning(
                "[HYBRID EVAL BACKSTOP] tool_prematuro interceptado args_redacted=true"
            )
            if depth == 0 and decision.provider == "deepseek":
                corrected_messages = list(messages) + [_build_corrective_message(reason)]
                gemini_resp = self.gemini_client.chat_completion(corrected_messages, tools=tools)
                logger.info("[HYBRID EVAL BACKSTOP RESUELTO] reason=%s fallback=gemini", reason)
                return self._apply_backstop(gemini_resp, decision, corrected_messages, tools, depth=1)
            # Red determinista final: strip + pregunta canónica.
            resp = _strip_premature_tool_calls(resp)
            canonical = _synthesize_canonical_question(decision.siguiente_pendiente)
            final_content = (resp.content or "").strip()
            if not final_content:
                final_content = canonical
            else:
                final_content = f"{final_content}\n\n{canonical}"
            logger.info(
                "[HYBRID EVAL BACKSTOP DETERMINISTA] siguiente=%s pregunta_canonica_inyectada",
                decision.siguiente_pendiente,
            )
            return replace(resp, content=final_content, tool_calls=[])

        # backstop_desviacion_orden
        if depth == 0 and decision.provider == "deepseek":
            corrected_messages = list(messages) + [_build_corrective_message(reason)]
            gemini_resp = self.gemini_client.chat_completion(corrected_messages, tools=tools)
            logger.info("[HYBRID EVAL BACKSTOP RESUELTO] reason=%s fallback=gemini", reason)
            return self._apply_backstop(gemini_resp, decision, corrected_messages, tools, depth=1)

        # Si Gemini también desvía, aplicar red determinista con pregunta canónica.
        canonical = _synthesize_canonical_question(decision.siguiente_pendiente)
        logger.info(
            "[HYBRID EVAL BACKSTOP DETERMINISTA] reason=%s siguiente=%s pregunta_canonica_inyectada",
            reason,
            decision.siguiente_pendiente,
        )
        return replace(resp, content=canonical, tool_calls=[])
