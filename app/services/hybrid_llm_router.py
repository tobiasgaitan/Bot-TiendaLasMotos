"""HybridLLMRouter: ruteo contextual Gemini/DeepSeek con backstop determinista.

Diseñado para BOT-BUILD-LLMROUTER-HYBRID-091 / Fixes BOT-BUILD-LLMROUTER-FIX-092:
- DeepSeek V4 Flash 0731 (OpenRouter) para turnos 1-6 de MATRIZ, P1 y FAQ.
- Gemini para turno 7+, CIERRE DE FASE y cualquier invocación de calculate_credit_score.
- Backstop doble: tool-call prematuro y desviación de orden vs <siguiente_pendiente>.
- Guard post-respuesta en AMBAS rutas: ningún calculate_credit_score prematuro
  llega al caller; red determinista final con pregunta canónica.
- Activación por flag Firestore llm_runtime/global.hybrid_routing_enabled.

Expone la misma superficie google-genai que DualProviderClient, por lo que
ai_brain.py no requiere cambios.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.services.deepseek_client_service import DeepSeekOpenRouterClient

# Reutilizamos helpers probados de llm_client_service.py (misma capa de servicio).
from app.services.llm_client_service import (
    DualProviderChat,
    DualProviderClient,
    _ResponseShim,
    _build_openai_messages,
    _config_to_openai_params,
    _normalize_parts,
    _parse_openai_response,
    _response_shim_to_parts,
)

logger = logging.getLogger(__name__)

# Mapa de keywords para validar la pregunta final contra <siguiente_pendiente>.
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
# red determinista final.
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
    provider: str  # "gemini" | "deepseek"
    reason: str
    captured_count: int
    siguiente_pendiente: Optional[str]
    fase: Optional[str]


@dataclass(frozen=True)
class ProfilingState:
    captured_count: int
    siguiente_pendiente: Optional[str]
    fase: Optional[str]


def _extract_text_from_contents(contents: Any) -> str:
    """Extrae texto plano de contents (soporta str, types.Part, types.Content/dict/list)."""
    parts: list[str] = []
    if not isinstance(contents, list):
        contents = [contents]
    for c in contents:
        if c is None:
            continue
        if isinstance(c, str):
            parts.append(c)
        elif hasattr(c, "parts"):
            for part in c.parts:
                if hasattr(part, "text") and part.text:
                    parts.append(str(part.text))
                elif isinstance(part, dict) and part.get("text"):
                    parts.append(str(part["text"]))
        elif isinstance(c, dict):
            for part in c.get("parts", []):
                if isinstance(part, dict) and part.get("text"):
                    parts.append(str(part["text"]))
        elif hasattr(c, "text"):
            text = getattr(c, "text")
            if text:
                parts.append(str(text))
    return "\n".join(parts)


def _extract_last_checklist(text: str) -> str:
    """Devuelve el último bloque <estado_perfilamiento> presente en el prompt.

    En producción solo hay uno por turno; en eval/tests pueden acumularse varios
    en el historial. Siempre usamos el más reciente.
    """
    blocks = _CHECKLIST_BLOCK_RE.findall(text)
    return blocks[-1] if blocks else ""


def _parse_profiling_state(contents: Any) -> ProfilingState:
    """Parsea checklist XML y fase actual inyectados por ai_brain.py."""
    text = _extract_text_from_contents(contents)
    latest = _extract_last_checklist(text)
    captured_count = len(re.findall(r'<item[^>]+estado="CAPTURADO"', latest))

    siguiente = None
    m = re.search(r"<siguiente_pendiente>([^<]+)</siguiente_pendiente>", latest)
    if m:
        siguiente = m.group(1).strip()

    fase = None
    m = re.search(r"<fase_actual>([^<]+)</fase_actual>", text)
    if m:
        fase = m.group(1).strip()

    return ProfilingState(
        captured_count=captured_count,
        siguiente_pendiente=siguiente,
        fase=fase,
    )


def _has_tool(config: Any, name: str) -> bool:
    """Verifica si config.tools declara una herramienta por nombre."""
    if config is None:
        return False
    tools = getattr(config, "tools", None)
    if not tools:
        return False
    try:
        from google.genai import types as _types
    except Exception:
        _types = None  # type: ignore
    for tool in tools:
        if _types is not None and isinstance(tool, _types.Tool):
            names = {d.name for d in (tool.function_declarations or []) if d.name}
        elif isinstance(tool, dict) and "function_declarations" in tool:
            names = {d.get("name") for d in tool.get("function_declarations", []) if d.get("name")}
        else:
            names = set()
        if name in names:
            return True
    return False


def _declared_tools(config: Any) -> set[str]:
    """Devuelve el conjunto de nombres de herramientas declaradas."""
    names: set[str] = set()
    if config is None:
        return names
    tools = getattr(config, "tools", None)
    if not tools:
        return names
    try:
        from google.genai import types as _types
    except Exception:
        _types = None  # type: ignore
    for tool in tools:
        if _types is not None and isinstance(tool, _types.Tool):
            names.update({d.name for d in (tool.function_declarations or []) if d.name})
        elif isinstance(tool, dict) and "function_declarations" in tool:
            names.update({d.get("name") for d in tool.get("function_declarations", []) if d.get("name")})
    return names


def route_by_context(contents: Any, config: Any) -> RoutingDecision:
    """Decide proveedor según contenido/config. Nunca falla abierto: excepciones → Gemini."""
    try:
        state = _parse_profiling_state(contents)

        # R1: CIERRE DE FASE (matriz completa).
        if state.siguiente_pendiente == "COMPLETO":
            return RoutingDecision(
                provider="gemini",
                reason="cierre_fase_completo",
                captured_count=state.captured_count,
                siguiente_pendiente=state.siguiente_pendiente,
                fase=state.fase,
            )

        # R2/R3: MATRIZ de perfilamiento.
        if state.fase == "PHASE_3_CREDIT_PROFILING" or state.captured_count > 0:
            if state.captured_count >= 7:
                return RoutingDecision(
                    provider="gemini",
                    reason="frontera_turno_7_matriz",
                    captured_count=state.captured_count,
                    siguiente_pendiente=state.siguiente_pendiente,
                    fase=state.fase,
                )
            return RoutingDecision(
                provider="deepseek",
                reason=f"turno_{state.captured_count + 1}_profiling",
                captured_count=state.captured_count,
                siguiente_pendiente=state.siguiente_pendiente,
                fase=state.fase,
            )

        # R4: PHASE_2 / simulación ciega (calculate_credit_score).
        if state.fase == "PHASE_2_HABEAS_DATA" and _has_tool(config, "calculate_credit_score"):
            return RoutingDecision(
                provider="gemini",
                reason="simulacion_ciega_paso2",
                captured_count=state.captured_count,
                siguiente_pendiente=state.siguiente_pendiente,
                fase=state.fase,
            )

        # R5: P1 catálogo.
        declared = _declared_tools(config)
        if state.fase == "PHASE_1_ENGAGEMENT" and declared <= {"search_catalog"}:
            return RoutingDecision(
                provider="deepseek",
                reason="tarea_p1_catalogo",
                captured_count=state.captured_count,
                siguiente_pendiente=state.siguiente_pendiente,
                fase=state.fase,
            )

        # R6: FAQ / locations.
        if declared <= {"query_faq", "query_locations"}:
            return RoutingDecision(
                provider="deepseek",
                reason="tarea_faq_contexto",
                captured_count=state.captured_count,
                siguiente_pendiente=state.siguiente_pendiente,
                fase=state.fase,
            )

        # R7: default conservador.
        return RoutingDecision(
            provider="gemini",
            reason="default_conservador",
            captured_count=state.captured_count,
            siguiente_pendiente=state.siguiente_pendiente,
            fase=state.fase,
        )
    except Exception:
        logger.exception("🚨 [HYBRID ROUTER] Error en route_by_context; fallback a Gemini")
        return RoutingDecision(
            provider="gemini",
            reason="route_fallback_gemini",
            captured_count=-1,
            siguiente_pendiente=None,
            fase=None,
        )


def _count_questions(text: Optional[str]) -> int:
    if not text:
        return 0
    return text.count("?")


def _matches_expected_field(text: Optional[str], expected_field: Optional[str]) -> bool:
    if not text or not expected_field:
        return False
    lowered = text.lower()
    return any(kw.lower() in lowered for kw in FIELD_KEYWORDS.get(expected_field, []))


def _synthesize_canonical_question(siguiente: Optional[str]) -> str:
    return CANONICAL_QUESTION.get(siguiente or "", "¿Me confirmas el dato que falta?")


def _has_premature_credit_tool(tool_calls: List[Dict[str, Any]], siguiente: Optional[str]) -> bool:
    if siguiente == "COMPLETO":
        return False
    return any(tc.get("name") == "calculate_credit_score" for tc in tool_calls)


def _is_matrix_context(decision: RoutingDecision) -> bool:
    """True solo si la llamada pertenece al núcleo MATRIZ (profiling/frontera/cierre)."""
    if decision.fase == "PHASE_3_CREDIT_PROFILING":
        return True
    if decision.captured_count > 0:
        return True
    return bool(decision.siguiente_pendiente and decision.siguiente_pendiente != "COMPLETO")


def _should_backstop(
    decision: RoutingDecision,
    shim: _ResponseShim,
) -> Tuple[bool, str]:
    """Evalúa si la respuesta requiere re-enrute o red determinista."""
    text = shim.text
    tool_calls = shim._tool_calls if hasattr(shim, "_tool_calls") else []

    # CERO_TOOL_PREMATURO solo dentro del contexto MATRIZ; PASO 1/PASO 2 quedan fuera de alcance.
    if _is_matrix_context(decision) and _has_premature_credit_tool(tool_calls, decision.siguiente_pendiente):
        return True, "backstop_tool_prematuro"

    if decision.siguiente_pendiente and decision.siguiente_pendiente != "COMPLETO":
        q_count = _count_questions(text)
        if q_count == 1 and not _matches_expected_field(text, decision.siguiente_pendiente):
            return True, "backstop_desviacion_orden"

    return False, ""


def _build_corrective_contents(contents: Any, reason: str) -> list[Any]:
    """Inyecta mensaje correctivo antes de re-enrutar a Gemini."""
    directive = "[CORRECCIÓN DE SISTEMA] "
    if reason == "backstop_tool_prematuro":
        directive += (
            "ERROR: TOOL-CALL PREMATURO. No invoques calculate_credit_score hasta "
            "que el checklist indique COMPLETO (8/8 campos). Continúa el "
            "perfilamiento con la única pregunta pendiente."
        )
    else:
        directive += (
            "ERROR: DESVIACIÓN DE ORDEN. Tu pregunta final no coincide con el dato "
            "indicado en <siguiente_pendiente>. Ajusta la pregunta al orden de la MATRIZ."
        )

    try:
        from google.genai import types as _types
        corrective = _types.Content(role="user", parts=[_types.Part(text=directive)])
    except Exception:
        corrective = {"role": "user", "parts": [{"text": directive}]}

    if isinstance(contents, list):
        return list(contents) + [corrective]
    return [contents, corrective]


def _response_to_shim(response: Any) -> _ResponseShim:
    """Normaliza cualquier respuesta (shim o google-genai) a _ResponseShim."""
    if isinstance(response, _ResponseShim):
        return response

    text = getattr(response, "text", None)
    usage = getattr(response, "usage_metadata", None)
    prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
    candidates_tokens = getattr(usage, "candidates_token_count", 0) or 0
    total_tokens = getattr(usage, "total_token_count", 0) or 0

    parts: List[Dict[str, Any]] = []
    tool_calls: List[Dict[str, Any]] = []
    candidates = getattr(response, "candidates", [])
    if candidates and candidates[0].content and candidates[0].content.parts:
        for part in candidates[0].content.parts:
            fc = getattr(part, "function_call", None)
            if fc:
                name = getattr(fc, "name", "")
                args: Dict[str, Any] = {}
                raw_args = getattr(fc, "args", None)
                if raw_args is not None:
                    try:
                        args = dict(raw_args)
                    except Exception:
                        args = {}
                parts.append({"type": "function_call", "_function_call": {"name": name, "args": args}})
                tool_calls.append({"name": name, "args": args})
            elif getattr(part, "text", None):
                parts.append({"type": "text", "text": part.text})

    return _ResponseShim(
        text=text,
        parts=parts,
        prompt_tokens=prompt_tokens,
        candidates_tokens=candidates_tokens,
        total_tokens=total_tokens,
        tool_calls=tool_calls,
    )


def _build_deterministic_shim(shim: _ResponseShim, siguiente: Optional[str]) -> _ResponseShim:
    """Red determinista final: strip tool_calls + pregunta canónica si hace falta."""
    canonical = _synthesize_canonical_question(siguiente)
    safe_text = (shim.text or "").strip()
    if not safe_text:
        safe_text = canonical
    else:
        safe_text = f"{safe_text}\n\n{canonical}"
    return _ResponseShim(
        text=safe_text,
        parts=[{"type": "text", "text": safe_text}],
        prompt_tokens=getattr(shim.usage_metadata, "prompt_token_count", 0) or 0,
        candidates_tokens=getattr(shim.usage_metadata, "candidates_token_count", 0) or 0,
        total_tokens=getattr(shim.usage_metadata, "total_token_count", 0) or 0,
        tool_calls=[],
    )


def _apply_backstop_sync(
    router: "HybridLLMRouter",
    shim: _ResponseShim,
    decision: RoutingDecision,
    model: str,
    contents: Any,
    config: Any,
    depth: int,
) -> _ResponseShim:
    """Guard post-respuesta síncrono; máximo 1 re-enrute a Gemini."""
    backstop, reason = _should_backstop(decision, shim)
    if not backstop:
        return shim

    logger.warning(
        "🛡️ [HYBRID BACKSTOP] reason=%s captured_count=%s siguiente=%s depth=%s",
        reason,
        decision.captured_count,
        decision.siguiente_pendiente,
        depth,
    )

    if reason == "backstop_tool_prematuro":
        logger.warning("🛡️ [HYBRID BACKSTOP] tool_prematuro interceptado args_redacted=true")
        if depth == 0 and decision.provider == "deepseek":
            corrective_contents = _build_corrective_contents(contents, reason)
            gemini_response = router._dual.models.generate_content(
                model=model, contents=corrective_contents, config=config
            )
            logger.info("✅ [HYBRID BACKSTOP RESUELTO] reason=%s fallback=gemini", reason)
            return _apply_backstop_sync(
                router,
                _response_to_shim(gemini_response),
                decision,
                model,
                corrective_contents,
                config,
                depth=1,
            )
        # Red determinista final (Gemini también falló o ruta original era Gemini).
        return _build_deterministic_shim(shim, decision.siguiente_pendiente)

    # backstop_desviacion_orden
    if depth == 0 and decision.provider == "deepseek":
        corrective_contents = _build_corrective_contents(contents, reason)
        gemini_response = router._dual.models.generate_content(
            model=model, contents=corrective_contents, config=config
        )
        logger.info("✅ [HYBRID BACKSTOP RESUELTO] reason=%s fallback=gemini", reason)
        return _apply_backstop_sync(
            router,
            _response_to_shim(gemini_response),
            decision,
            model,
            corrective_contents,
            config,
            depth=1,
        )

    # Gemini también desvía: red determinista con pregunta canónica.
    return _build_deterministic_shim(shim, decision.siguiente_pendiente)


async def _apply_backstop_async(
    router: "HybridLLMRouter",
    shim: _ResponseShim,
    decision: RoutingDecision,
    model: str,
    contents: Any,
    config: Any,
    depth: int,
) -> _ResponseShim:
    """Guard post-respuesta asíncrono; máximo 1 re-enrute a Gemini."""
    backstop, reason = _should_backstop(decision, shim)
    if not backstop:
        return shim

    logger.warning(
        "🛡️ [HYBRID BACKSTOP ASYNC] reason=%s captured_count=%s siguiente=%s depth=%s",
        reason,
        decision.captured_count,
        decision.siguiente_pendiente,
        depth,
    )

    if reason == "backstop_tool_prematuro":
        logger.warning("🛡️ [HYBRID BACKSTOP ASYNC] tool_prematuro interceptado args_redacted=true")
        if depth == 0 and decision.provider == "deepseek":
            corrective_contents = _build_corrective_contents(contents, reason)
            gemini_response = await router._dual.aio.models.generate_content(
                model=model, contents=corrective_contents, config=config
            )
            logger.info("✅ [HYBRID BACKSTOP RESUELTO ASYNC] reason=%s fallback=gemini", reason)
            return await _apply_backstop_async(
                router,
                _response_to_shim(gemini_response),
                decision,
                model,
                corrective_contents,
                config,
                depth=1,
            )
        return _build_deterministic_shim(shim, decision.siguiente_pendiente)

    if depth == 0 and decision.provider == "deepseek":
        corrective_contents = _build_corrective_contents(contents, reason)
        gemini_response = await router._dual.aio.models.generate_content(
            model=model, contents=corrective_contents, config=config
        )
        logger.info("✅ [HYBRID BACKSTOP RESUELTO ASYNC] reason=%s fallback=gemini", reason)
        return await _apply_backstop_async(
            router,
            _response_to_shim(gemini_response),
            decision,
            model,
            corrective_contents,
            config,
            depth=1,
        )

    return _build_deterministic_shim(shim, decision.siguiente_pendiente)


class _HybridModelsSync:
    def __init__(self, router: "HybridLLMRouter") -> None:
        self._router = router

    def generate_content(
        self,
        model: str,
        contents: Any,
        config: Any = None,
    ) -> _ResponseShim:
        decision = route_by_context(contents, config)
        logger.info(
            "🔀 [HYBRID ROUTE] provider=%s reason=%s captured_count=%s siguiente=%s fase=%s",
            decision.provider,
            decision.reason,
            decision.captured_count,
            decision.siguiente_pendiente,
            decision.fase,
        )

        try:
            if decision.provider == "gemini":
                raw_response = self._router._dual.models.generate_content(
                    model=model, contents=contents, config=config
                )
            else:
                messages, _ = _build_openai_messages(contents=contents, config=config)
                params = _config_to_openai_params(config)
                tools = params.pop("tools", None)
                tool_choice = params.pop("tool_choice", "auto")
                temperature = params.pop("temperature", 0.0)

                raw = self._router._deepseek.chat_completion(
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    temperature=temperature,
                )
                tools_cfg = getattr(config, "tools", None) if config else None
                raw_response = _parse_openai_response(raw, emulated_toolcall=False, tools=tools_cfg)

            shim = _response_to_shim(raw_response)
            return _apply_backstop_sync(
                self._router, shim, decision, model, contents, config, depth=0
            )
        except Exception:
            logger.exception("❌ [HYBRID ROUTER] Call failed; failover a Gemini")
            return _response_to_shim(
                self._router._dual.models.generate_content(model=model, contents=contents, config=config)
            )


class _HybridAioModels:
    def __init__(self, router: "HybridLLMRouter") -> None:
        self._router = router

    async def generate_content(
        self,
        model: str,
        contents: Any,
        config: Any = None,
    ) -> _ResponseShim:
        decision = route_by_context(contents, config)
        logger.info(
            "🔀 [HYBRID ROUTE ASYNC] provider=%s reason=%s captured_count=%s siguiente=%s fase=%s",
            decision.provider,
            decision.reason,
            decision.captured_count,
            decision.siguiente_pendiente,
            decision.fase,
        )

        try:
            if decision.provider == "gemini":
                raw_response = await self._router._dual.aio.models.generate_content(
                    model=model, contents=contents, config=config
                )
            else:
                messages, _ = _build_openai_messages(contents=contents, config=config)
                params = _config_to_openai_params(config)
                tools = params.pop("tools", None)
                tool_choice = params.pop("tool_choice", "auto")
                temperature = params.pop("temperature", 0.0)

                raw = await self._router._deepseek.achat_completion(
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    temperature=temperature,
                )
                tools_cfg = getattr(config, "tools", None) if config else None
                raw_response = _parse_openai_response(raw, emulated_toolcall=False, tools=tools_cfg)

            shim = _response_to_shim(raw_response)
            return await _apply_backstop_async(
                self._router, shim, decision, model, contents, config, depth=0
            )
        except Exception:
            logger.exception("❌ [HYBRID ROUTER ASYNC] Call failed; failover a Gemini")
            return _response_to_shim(
                await self._router._dual.aio.models.generate_content(model=model, contents=contents, config=config)
            )


class HybridAioChat(DualProviderChat):
    """Chat async híbrido: rutea cada send_message a DeepSeek/Gemini."""

    def __init__(self, router: "HybridLLMRouter", model: Optional[str] = None) -> None:
        super().__init__(facade=router._dual, model=model)
        self._router = router

    async def send_message(self, contents: Any, config: Any = None) -> Any:
        current_parts = _normalize_parts(contents)
        self._history.append({"role": "user", "parts": current_parts})

        decision = route_by_context(contents, config)
        logger.info(
            "🔀 [HYBRID ROUTE ASYNC] provider=%s reason=%s captured_count=%s siguiente=%s fase=%s",
            decision.provider,
            decision.reason,
            decision.captured_count,
            decision.siguiente_pendiente,
            decision.fase,
        )

        try:
            if decision.provider == "gemini":
                conversation = self._to_gemini_contents(contents)
                raw_response = await self._router._dual.aio.models.generate_content(
                    model=self._model, contents=conversation, config=config
                )
            else:
                messages, _ = _build_openai_messages(
                    contents=contents, config=config, chat_history=self
                )
                params = _config_to_openai_params(config)
                tools = params.pop("tools", None)
                tool_choice = params.pop("tool_choice", "auto")
                temperature = params.pop("temperature", 0.0)

                raw = await self._router._deepseek.achat_completion(
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    temperature=temperature,
                )
                tools_cfg = getattr(config, "tools", None) if config else None
                raw_response = _parse_openai_response(raw, emulated_toolcall=False, tools=tools_cfg)

            shim = _response_to_shim(raw_response)
            shim = await _apply_backstop_async(
                self._router, shim, decision, self._model, contents, config, depth=0
            )
        except Exception:
            logger.exception("❌ [HYBRID ROUTER ASYNC] Call failed; failover a Gemini")
            conversation = self._to_gemini_contents(contents)
            raw_response = await self._router._dual.aio.models.generate_content(
                model=self._model, contents=conversation, config=config
            )
            shim = _response_to_shim(raw_response)

        self._history.append(
            {"role": "model", "parts": _response_shim_to_parts(shim), "tool_calls": shim._tool_calls}
        )
        return shim

    async def send_message_async(self, contents: Any, config: Any = None) -> Any:
        return await self.send_message(contents, config)


class _HybridAioChats:
    def __init__(self, router: "HybridLLMRouter") -> None:
        self._router = router

    def create(self, model: Optional[str] = None, **kwargs: Any) -> HybridAioChat:
        return HybridAioChat(self._router, model=model)


class _HybridAioNamespace:
    def __init__(self, router: "HybridLLMRouter") -> None:
        self.models = _HybridAioModels(router)
        self.chats = _HybridAioChats(router)


class HybridLLMRouter:
    """Fachada de ruteo híbrido con superficie google-genai.

    Envuelve un DualProviderClient (Gemini/Qwen) y un DeepSeekOpenRouterClient.
    """

    def __init__(
        self,
        dual_client: DualProviderClient,
        deepseek_client: Optional[DeepSeekOpenRouterClient] = None,
        role: str = "agentic",
    ) -> None:
        self._dual = dual_client
        self._deepseek = deepseek_client or DeepSeekOpenRouterClient()
        self._role = role
        self.models = _HybridModelsSync(self)
        self.aio = _HybridAioNamespace(self)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._dual, name)
