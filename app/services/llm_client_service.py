"""
LLM Client Service (BOT-BUILD-MIGRATE-QWEN-079)
================================================
Fachada DualProviderClient que expone la superficie google-genai usada por los
servicios del bot (CerebroIA, VisionService, AudioService, JudgeService) y
delega transparentemente a Gemini o a Qwen/DashScope según el flag runtime
`qwen_enabled` en Firestore doc `llm_runtime/global`.

Diseño:
- Superficie gemini-compatible:
  * client.models.generate_content(...)            (sync)
  * client.aio.models.generate_content(...)        (async)
  * client.aio.chats.create(model=...).send_message(...) (async)
  * __getattr__ delega atributos no implementados al backend Gemini.
- Flag QWEN_ENABLED con cache TTL 30s y lock thread-safe.
- Traducción google-genai ↔ OpenAI chat.completions.
- Rama A (tools nativas) vs Rama B (emulada por directiva JSON).
- Failover DUAL a Gemini ante Timeout/429/5xx de Qwen.
- Presupuesto de contexto 33K para historial de chat.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.services.genai_client_service import (
    get_shared_genai_client,
    get_shared_genai_client_async,
)

logger = logging.getLogger(__name__)

try:
    from google import genai
    from google.genai import types
    from google.genai._transformers import t_schema

    SDK_AVAILABLE = True
except ImportError:  # pragma: no cover
    genai = None  # type: ignore
    types = None  # type: ignore
    t_schema = None  # type: ignore
    SDK_AVAILABLE = False
    logger.warning("⚠️ google-genai SDK not available; llm_client_service Gemini path disabled")

# ---------------------------------------------------------------------------
# Constantes y configuración runtime
# ---------------------------------------------------------------------------
_QWEN_FLAG_TTL_S = 30.0
_QWEN_CONTEXT_TOKEN_BUDGET = 33_000
_QWEN_MAX_TOKENS = 2048

# Cache del flag runtime
_flag_cache_value: Optional[bool] = None
_flag_cache_time: float = 0.0
_flag_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Helpers de entorno
# ---------------------------------------------------------------------------
def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name, "")
    if val.lower() in ("true", "1", "yes"):
        return True
    if val.lower() in ("false", "0", "no"):
        return False
    return default


def _gemini_timeout_default() -> float:
    """Timeout por defecto para llamadas Gemini (usado como fallback de Qwen)."""
    try:
        from app.services.ai_brain import GEMINI_CALL_TIMEOUT_S
    except Exception:
        GEMINI_CALL_TIMEOUT_S = 18.0
    return float(os.getenv("GEMINI_CALL_TIMEOUT_S", GEMINI_CALL_TIMEOUT_S))


def _qwen_timeout_default() -> float:
    """Timeout por defecto para llamadas Qwen."""
    return float(os.getenv("QWEN_CALL_TIMEOUT_S", _gemini_timeout_default()))


def get_active_model_id(role: str = "multimodal") -> str:
    """Retorna el modelo activo según el flag runtime y el rol."""
    if is_qwen_enabled():
        return _qwen_model(role=role)
    return os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash")


# ---------------------------------------------------------------------------
# Lectura del flag runtime (Firestore + env fallback)
# ---------------------------------------------------------------------------
_FLAG_DB_CLIENT: Any = None
_FLAG_DB_LOCK = threading.Lock()


def _get_flag_db_client() -> Any:
    """Cliente Firestore cacheado a nivel módulo para el poll del flag."""
    global _FLAG_DB_CLIENT
    if _FLAG_DB_CLIENT is not None:
        return _FLAG_DB_CLIENT
    with _FLAG_DB_LOCK:
        if _FLAG_DB_CLIENT is None:
            from google.cloud import firestore

            _FLAG_DB_CLIENT = firestore.Client()
        return _FLAG_DB_CLIENT


def _read_qwen_flag_from_firestore() -> Optional[bool]:
    """Lee qwen_enabled de Firestore. Retorna None si no puede leer."""
    try:
        db = _get_flag_db_client()
        doc = db.collection("llm_runtime").document("global").get()
        if doc.exists:
            return bool(doc.to_dict().get("qwen_enabled", False))
        return False
    except Exception:
        logger.exception("❌ [LLM CLIENT] Error reading qwen_enabled from Firestore")
        return None


def is_qwen_enabled() -> bool:
    """
    Cache-aware, thread-safe flag reader.
    Error/doc ausente -> fallback a env QWEN_ENABLED (default false).
    """
    global _flag_cache_value, _flag_cache_time
    with _flag_lock:
        now = time.monotonic()
        if _flag_cache_value is not None and (now - _flag_cache_time) < _QWEN_FLAG_TTL_S:
            return _flag_cache_value

    val = _read_qwen_flag_from_firestore()
    if val is None:
        val = _env_bool("QWEN_ENABLED", False)

    with _flag_lock:
        _flag_cache_value = val
        _flag_cache_time = time.monotonic()
    return val


async def is_qwen_enabled_async() -> bool:
    """Versión async-safe del flag reader."""
    return await asyncio.to_thread(is_qwen_enabled)


def _invalidate_qwen_flag_cache() -> None:
    """Hook interno para tests/forzar relectura inmediata."""
    global _flag_cache_value, _flag_cache_time
    with _flag_lock:
        _flag_cache_value = None
        _flag_cache_time = 0.0


# ---------------------------------------------------------------------------
# Normalización de contents / parts
# ---------------------------------------------------------------------------
def _normalize_parts(contents: Any) -> List[Any]:
    """Convierte str o lista de parts a lista de parts google-genai."""
    if contents is None:
        return []
    if isinstance(contents, str):
        if SDK_AVAILABLE and types is not None:
            return [types.Part.from_text(text=contents)]
        return [{"text": contents}]
    if isinstance(contents, (list, tuple)):
        result = []
        for item in contents:
            if isinstance(item, str):
                if SDK_AVAILABLE and types is not None:
                    result.append(types.Part.from_text(text=item))
                else:
                    result.append({"text": item})
            else:
                result.append(item)
        return result
    return [contents]


def _is_image_mime(mime_type: str) -> bool:
    return mime_type.startswith("image/")


def _is_audio_mime(mime_type: str) -> bool:
    return mime_type.startswith("audio/")


def _parts_have_audio(parts: List[Any]) -> bool:
    """Detecta si una lista de parts contiene audio inline."""
    for part in parts:
        if SDK_AVAILABLE and types is not None and isinstance(part, types.Part):
            blob = getattr(part, "inline_data", None)
            if blob is not None and _is_audio_mime(blob.mime_type):
                return True
            continue
        inline_data = getattr(part, "inline_data", None) or getattr(part, "inlineData", None)
        if inline_data:
            mime_type = getattr(inline_data, "mime_type", "") or getattr(inline_data, "mimeType", "")
            if _is_audio_mime(mime_type):
                return True
            continue
        if isinstance(part, dict):
            inline_data = part.get("inline_data") or part.get("inlineData")
            if inline_data:
                mime_type = inline_data.get("mime_type") or inline_data.get("mimeType", "")
                if _is_audio_mime(mime_type):
                    return True
    return False


def _contents_have_audio(contents: Any) -> bool:
    """Detecta si contents (str, Part o lista) contiene audio inline."""
    return _parts_have_audio(_normalize_parts(contents))


def _qwen_audio_enabled() -> bool:
    """Guard opt-in para audio por Qwen. Default false: audio va a Gemini."""
    return os.getenv("QWEN_AUDIO_ENABLED", "false").lower() == "true"


def _part_to_openai_content(part: Any, index: int = 0) -> Optional[Dict[str, Any]]:
    """Convierte un google-genai Part a un fragmento de content OpenAI."""
    if not SDK_AVAILABLE or types is None:
        # Fallback duck-typing para tests sin SDK
        text = getattr(part, "text", None)
        if text:
            return {"type": "text", "text": text}
        inline_data = getattr(part, "inline_data", None) or getattr(part, "inlineData", None)
        if inline_data:
            data = getattr(inline_data, "data", b"")
            mime_type = getattr(inline_data, "mime_type", "") or getattr(inline_data, "mimeType", "")
            b64 = base64.b64encode(data).decode("ascii") if isinstance(data, bytes) else data
            if _is_image_mime(mime_type):
                return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}
            if _is_audio_mime(mime_type):
                return {"type": "input_audio", "input_audio": {"data": b64, "format": "wav"}}
        return None

    # SDK disponible: usar tipos reales
    if isinstance(part, types.Part):
        if part.text:
            return {"type": "text", "text": part.text}
        if part.inline_data is not None:
            blob = part.inline_data
            b64 = base64.b64encode(blob.data).decode("ascii") if isinstance(blob.data, bytes) else blob.data
            if _is_image_mime(blob.mime_type):
                return {"type": "image_url", "image_url": {"url": f"data:{blob.mime_type};base64,{b64}"}}
            if _is_audio_mime(blob.mime_type):
                return {"type": "input_audio", "input_audio": {"data": b64, "format": "wav"}}
        if part.function_call is not None:
            fc = part.function_call
            args = fc.args if fc.args is not None else {}
            return {
                "type": "function_call",
                "_function_call": {"name": fc.name or "", "arguments": json.dumps(args)},
            }
        if part.function_response is not None:
            fr = part.function_response
            response = fr.response if fr.response is not None else {}
            return {
                "type": "function_response",
                "_function_response": {
                    "name": fr.name or "",
                    "content": json.dumps(response) if isinstance(response, dict) else str(response),
                },
            }
    return None


def _contents_to_openai_messages(contents: Any) -> List[Dict[str, Any]]:
    """Convierte contents google-genai a mensajes OpenAI (rol user)."""
    parts = _normalize_parts(contents)
    openai_parts = [_part_to_openai_content(p, i) for i, p in enumerate(parts)]
    openai_parts = [p for p in openai_parts if p is not None]
    if not openai_parts:
        return []
    return [{"role": "user", "content": openai_parts}]


# ---------------------------------------------------------------------------
# Conversión de config google-genai → OpenAI
# ---------------------------------------------------------------------------
def _config_to_openai_params(config: Any) -> Dict[str, Any]:
    """Extrae parámetros OpenAI desde types.GenerateContentConfig."""
    params: Dict[str, Any] = {}
    if config is None:
        return params

    temperature = getattr(config, "temperature", None)
    if temperature is not None:
        params["temperature"] = temperature

    max_output_tokens = getattr(config, "max_output_tokens", None)
    if max_output_tokens is not None:
        params["max_tokens"] = min(int(max_output_tokens), _QWEN_MAX_TOKENS)

    response_mime_type = getattr(config, "response_mime_type", None)
    if response_mime_type == "application/json":
        params["response_format"] = {"type": "json_object"}

    tools = getattr(config, "tools", None)
    if tools:
        params["tools"] = _convert_tools_to_openai(tools)

    return params


def _convert_tools_to_openai(tools: List[Any]) -> List[Dict[str, Any]]:
    """Convierte google-genai Tool/Callable a OpenAI tools."""
    openai_tools: List[Dict[str, Any]] = []
    for tool in tools or []:
        if SDK_AVAILABLE and types is not None and isinstance(tool, types.Tool):
            for decl in tool.function_declarations or []:
                openai_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": decl.name or "",
                            "description": decl.description or "",
                            "parameters": _serialize_response_schema(decl.parameters) or {},
                        },
                    }
                )
        elif callable(tool):
            # Callable no soportado en migración F1; omitir silenciosamente
            continue
        elif isinstance(tool, dict) and "function_declarations" in tool:
            for decl in tool.get("function_declarations") or []:
                openai_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": decl.get("name", ""),
                            "description": decl.get("description", ""),
                            "parameters": decl.get("parameters", {}),
                        },
                    }
                )
    return openai_tools


def _relax_credit_tool_for_qwen(
    tools: Optional[List[Dict[str, Any]]],
) -> Optional[List[Dict[str, Any]]]:
    """
    [BOT-BUILD-QWEN-LIVE-FIX-089 / Pin 2]
    Relaja el schema expuesto a la ruta Qwen para calculate_credit_score.
    El backend inyecta defaults del CRM para campos faltantes, por lo que el modelo
    no debe esperar a que todos los argumentos esten explicitos en el ultimo turno.
    Solo modifica la copia enviada al provider; no altera la declaracion original.
    """
    if not tools:
        return tools
    modified = False
    out: List[Dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict) or tool.get("type") != "function":
            out.append(tool)
            continue
        func = tool.get("function", {})
        if func.get("name") != "calculate_credit_score":
            out.append(tool)
            continue
        new_tool = dict(tool)
        new_func = dict(func)
        params = dict(new_func.get("parameters") or {})
        params["required"] = []
        desc = new_func.get("description", "")
        suffix = (
            " El backend inyecta defaults del CRM para campos faltantes; invoca "
            "cuando exista señal financiera o mandato de cierre, aunque no todos los "
            "campos esten explicitos en el ultimo turno."
        )
        if suffix not in desc:
            new_func["description"] = desc + suffix
        new_func["parameters"] = params
        new_tool["function"] = new_func
        out.append(new_tool)
        modified = True
    return out if modified else tools


def _serialize_response_schema(schema: Any) -> Optional[Dict[str, Any]]:
    """Convierte response_schema a dict JSON Schema."""
    if schema is None:
        return None
    if isinstance(schema, dict):
        return schema
    if SDK_AVAILABLE and types is not None and isinstance(schema, types.Schema):
        try:
            return schema.model_dump(mode="json")
        except Exception:
            return None
    if t_schema is not None:
        try:
            converted = t_schema(None, schema)
            return converted.model_dump(mode="json")
        except Exception:
            logger.exception("❌ [LLM CLIENT] Failed to convert response_schema")
            return None
    return None


# ---------------------------------------------------------------------------
# Construcción de mensajes OpenAI (chat + system annexes)
# ---------------------------------------------------------------------------
def _build_openai_messages(
    contents: Any,
    config: Any,
    history: Optional[List[Dict[str, Any]]] = None,
    chat_history: Optional["DualProviderChat"] = None,
    emulated_toolcall: bool = False,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Construye mensajes OpenAI a partir de contents/config/history.
    Retorna (messages, schema_dict).
    """
    messages: List[Dict[str, Any]] = []
    schema_dict: Optional[Dict[str, Any]] = None

    # System annexes de transporte (no tocan prompts.py/personality.json)
    system_extras: List[str] = []

    if config is not None:
        response_schema = getattr(config, "response_schema", None)
        schema_dict = _serialize_response_schema(response_schema)
        if schema_dict:
            system_extras.append(
                "[TRANSPORT SCHEMA ANNEX] You MUST obey this JSON schema: "
                + json.dumps(schema_dict, ensure_ascii=False)
            )
            # FIELD RULES: anti-booleanización de campos STRING abiertos (derivado del schema)
            properties = schema_dict.get("properties") if isinstance(schema_dict, dict) else None
            if properties:
                field_rules = ["[TRANSPORT FIELD RULES]"]
                for field_name, prop in properties.items():
                    field_type = (prop.get("type") if isinstance(prop, dict) else "").lower()
                    if field_type == "string":
                        field_rules.append(
                            f"- {field_name}: extrae el valor literal o entidad mencionada; "
                            "PROHIBIDO colapsar a 'Sí'/'No' salvo que la descripción lo exija."
                        )
                    elif field_type == "boolean":
                        field_rules.append(f"- {field_name}: responde true o false (JSON boolean).")
                if len(field_rules) > 1:
                    system_extras.append("\n".join(field_rules))

        # TOOLCALL RULES: calibración anti-inferencia para Rama A nativa
        # y anexo extendido de disciplina MATRIZ/CIERRE cuando se expone
        # calculate_credit_score (BOT-BUILD-QWEN-LIVE-FIX-089).
        tools = getattr(config, "tools", None)
        has_credit = False
        if tools:
            for tool in tools:
                if SDK_AVAILABLE and types is not None and isinstance(tool, types.Tool):
                    names = {d.name for d in (tool.function_declarations or []) if d.name}
                elif isinstance(tool, dict) and "function_declarations" in tool:
                    names = {d.get("name") for d in tool.get("function_declarations", []) if d.get("name")}
                else:
                    names = set()
                if "calculate_credit_score" in names:
                    has_credit = True
                    break

        if tools:
            if has_credit:
                system_extras.append(
                    "[TRANSPORT TOOLCALL RULES]\n"
                    "1. Extrae como argumentos ÚNICAMENTE lo que el usuario expresó literalmente; "
                    "prohibido inferir argumentos opcionales no mencionados.\n"
                    "2. Si el usuario expresa montos en forma relativa (ej. 'mínimos', 'palos') y la "
                    "herramienta exige montos absolutos para un cálculo útil, NO invoques la herramienta; "
                    "pide la cifra absoluta.\n"
                    "3. Invoca la herramienta cuando sus argumentos obligatorios estén explícitos en "
                    "CUALQUIER turno del historial o en el checklist/CRM inyectado, o cuando el prompt "
                    "incluya [MANDATO DE CIERRE DE FASE]. En ese caso, tu ÚNICA acción permitida es invocar "
                    "calculate_credit_score; NO generes preguntas de perfilamiento.\n"
                    "4. En fase de perfilamiento (cuando el prompt incluya <estado_perfilamiento>), formula "
                    "exactamente la pregunta indicada en <siguiente_pendiente>, una sola pregunta por turno, "
                    "sin repetir datos marcados como CAPTURADO y sin agrupar preguntas.\n"
                    "5. Tras invocar calculate_credit_score, tu siguiente mensaje debe ser el cierre de fase "
                    "según el puntaje (cuota/entidad/link). No reanudes el perfilamiento."
                )
            else:
                system_extras.append(
                    "[TRANSPORT TOOLCALL RULES]\n"
                    "1. Extrae como argumentos ÚNICAMENTE lo que el usuario expresó literalmente; "
                    "prohibido inferir argumentos opcionales no mencionados.\n"
                    "2. Si el usuario expresa montos en forma relativa (ej. 'mínimos', 'palos') y la "
                    "herramienta exige montos absolutos para un cálculo útil, NO invoques la herramienta; "
                    "pide la cifra absoluta.\n"
                    "3. Invoca la herramienta SOLO cuando sus argumentos obligatorios estén explícitos."
                )

    if emulated_toolcall:
        system_extras.append(
            "[TRANSPORT TOOLCALL DIRECTIVE] When you need to call a function, "
            "output JSON exactly like {\"tool_call\":{\"name\":\"function_name\",\"args\":{...}}}. "
            "When responding to the user, output JSON exactly like {\"final\":\"your response text\"}."
        )

    if system_extras:
        messages.append({"role": "system", "content": "\n".join(system_extras)})

    # Historial (solo modo chat). NOTA F1.5: el historial YA incluye el turno
    # actual — send_message lo appenda a _history antes de invocar este builder.
    # Anexar `contents` aquí duplicaría el turno y lo haría por el camino naíf
    # de _contents_to_openai_messages (function_response → tipo OpenAI inválido).
    if chat_history is not None:
        messages.extend(chat_history.to_openai_messages())
    else:
        if history:
            messages.extend(history)
        # Turno actual (single-shot sin chat: generate_content directo)
        current_messages = _contents_to_openai_messages(contents)
        messages.extend(current_messages)

    return messages, schema_dict


def _estimate_token_budget(messages: List[Dict[str, Any]]) -> float:
    """Estimador conservador: chars/4 + 15% margen."""
    try:
        payload = json.dumps(messages, ensure_ascii=False)
    except (TypeError, ValueError):
        payload = str(messages)
    return (len(payload) / 4.0) * 1.15


def _trim_history_to_budget(
    messages: List[Dict[str, Any]], current_turn_count: int
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Recorta mensajes antiguos (nunca el turno actual) hasta estar dentro del
    presupuesto de contexto. Retorna (messages, trimmed).
    """
    budget = _QWEN_CONTEXT_TOKEN_BUDGET
    # messages termina con `current_turn_count` mensajes del turno actual
    if current_turn_count <= 0:
        return messages, False

    trimmed = False
    while _estimate_token_budget(messages) > budget:
        # Número de mensajes que podemos recortar sin tocar el turno actual
        recortables = len(messages) - current_turn_count
        if recortables <= 0:
            break
        # Eviccionar el mensaje más antiguo NO-system: los annex/directive de
        # transporte (role=system) sobreviven siempre (Bug NB-c).
        evict_idx = None
        for i in range(recortables):
            if messages[i].get("role") != "system":
                evict_idx = i
                break
        if evict_idx is None:
            break
        messages.pop(evict_idx)
        trimmed = True
    return messages, trimmed


# ---------------------------------------------------------------------------
# Response shim (OpenAI → google-genai shape)
# ---------------------------------------------------------------------------
class _ResponseShim:
    """Objeto respuesta compatible con la superficie google-genai mínima."""

    def __init__(
        self,
        text: Optional[str],
        parts: List[Any],
        prompt_tokens: int = 0,
        candidates_tokens: int = 0,
        total_tokens: int = 0,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ):
        self.text = text
        self._tool_calls = tool_calls or []

        class _Usage:
            def __init__(self, p: int, c: int, t: int):
                self.prompt_token_count = p
                self.candidates_token_count = c
                self.total_token_count = t

        self.usage_metadata = _Usage(prompt_tokens, candidates_tokens, total_tokens)

        class _PartShim:
            def __init__(self, text: Optional[str] = None, function_call: Optional[Any] = None):
                self.text = text
                self.function_call = function_call

        class _Content:
            def __init__(self, parts: List[Any]):
                self.parts = parts

        class _Candidate:
            def __init__(self, content: Any):
                self.content = content

        shim_parts = []
        for p in parts:
            if isinstance(p, dict) and p.get("type") == "function_call":
                fc = p["_function_call"]
                name = fc.get("name", "")
                args = fc.get("args", {})
                if SDK_AVAILABLE and types is not None:
                    func_call = types.FunctionCall(name=name, args=args)
                else:
                    func_call = _SimpleFunctionCall(name=name, args=args)
                shim_parts.append(_PartShim(function_call=func_call))
            elif isinstance(p, dict) and p.get("type") == "text":
                shim_parts.append(_PartShim(text=p.get("text", "")))
            else:
                shim_parts.append(_PartShim(text=str(p) if not isinstance(p, types.Part) else getattr(p, "text", "")))

        self.candidates = [_Candidate(_Content(shim_parts))]


class _SimpleFunctionCall:
    """Duck-typed function_call para entornos sin google-genai SDK."""

    def __init__(self, name: str, args: Dict[str, Any]):
        self.name = name
        self.args = args


# ---------------------------------------------------------------------------
# [BOT-BUILD-TOOLCALL-FB1-084] Post-proceso de args Rama A Qwen
# ---------------------------------------------------------------------------
_ALLOWED_OCCUPATION_VALUES: Set[str] = {
    "empleado",
    "empleado fijo",
    "independiente",
    "informal",
    "desempleado",
    "obra",
    "indefinido",
    "fijo",
}

# Validadores declarativos para propiedades NO requeridas de tools.
# Un arg opcional que no pase el validador se poda ANTES de retornar el fc,
# cerrando inferencias espurias sin tocar prompts/personality (C4 intacto).
_ARG_PRUNE_VALIDATORS: Dict[str, Dict[str, Callable[[Any], bool]]] = {
    "calculate_credit_score": {
        "ocupacion": lambda v: str(v).strip().lower() in _ALLOWED_OCCUPATION_VALUES,
        "ocupacion_y_contrato": lambda v: str(v).strip().lower() in _ALLOWED_OCCUPATION_VALUES,
    },
}


def _extract_required_fields(tools: Optional[List[Any]]) -> Dict[str, Set[str]]:
    """Extrae las propiedades requeridas por tool name desde config.tools."""
    required: Dict[str, Set[str]] = {}
    if not tools:
        return required
    for tool in tools:
        if isinstance(tool, dict):
            declarations = tool.get("function_declarations") or []
        else:
            declarations = getattr(tool, "function_declarations", None) or []
        for fd in declarations:
            if isinstance(fd, dict):
                name = fd.get("name")
                params = fd.get("parameters") or {}
            else:
                name = getattr(fd, "name", None)
                params = getattr(fd, "parameters", None) or {}
            if isinstance(params, dict):
                req = params.get("required") or []
            else:
                req = getattr(params, "required", None) or []
            if name:
                required[name] = set(req)
    return required


def _prune_ungrounded_args(
    tool_name: str,
    args: Dict[str, Any],
    required: Set[str],
) -> Dict[str, Any]:
    """
    Poda args opcionales que no pasen el validador declarativo de su campo.
    NUNCA poda propiedades requeridas. Log ZSF sin valor crudo (PII-safe).
    """
    validators = _ARG_PRUNE_VALIDATORS.get(tool_name, {})
    pruned: Dict[str, Any] = {}
    for key, value in args.items():
        if key in required:
            pruned[key] = value
            continue
        validator = validators.get(key)
        if validator is None:
            pruned[key] = value
            continue
        if validator(value):
            pruned[key] = value
        else:
            logger.info(f"🌿 [ARG-PRUNE] tool={tool_name} field={key} reason=not_in_allowed_lexicon")
    removed_fields = [k for k in args if k not in pruned]
    if removed_fields:
        logger.info("[TOOLCALL-PRUNE] tool=%s removed=%s", tool_name, removed_fields)
    return pruned


# ---------------------------------------------------------------------------
# [BOT-BUILD-TOOLCALL-HARDEN-085] Guard numérico para Rama A Qwen
# ---------------------------------------------------------------------------
_MIN_PLAUSIBLE_COP = 100_000
_COP_RELATIVE_MARKERS = {"minimo", "mínimo", "smlv", "salario"}
_COP_MULTIPLIERS = {
    "millon": 1_000_000,
    "millón": 1_000_000,
    "millones": 1_000_000,
    "palos": 1_000_000,
}

_TOOLCALL_SUPPRESSION_DIRECTIVE = (
    "[TRANSPORT TOOLCALL SUPPRESSED] "
    "La llamada a calculate_credit_score fue suprimida porque ingresos_mensuales o gastos_mensuales "
    "no son montos absolutos plausibles en COP. "
    "Pide al usuario la cifra mensual exacta en pesos colombianos (solo números) antes de calcular, "
    "o continúa sin calcular si el usuario no la puede dar."
)


def _is_plausible_cop_amount(value: Any) -> bool:
    """
    Valida si un monto es una cantidad absoluta plausible en COP.
    - Rechaza valores relativos (mínimo, SMLV, salario).
    - Acepta multiplicadores léxicos (millón/millones/palos).
    - Umbral configurable _MIN_PLAUSIBLE_COP.
    - Fail-open: ante cualquier error interno retorna True para no romper llamadas válidas.
    """
    try:
        s = str(value).lower().strip()
        if not s:
            return True  # ausencia no se valida aquí
        if any(marker in s for marker in _COP_RELATIVE_MARKERS):
            return False
        # Extraer primer token numérico, tolerando separadores de miles/decimales.
        m = re.search(r"\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?", s.replace(" ", ""))
        if not m:
            return False
        num_str = m.group(0)
        # Normalizar: si hay coma y no punto, coma es separador decimal; si hay ambos, coma es miles.
        if "," in num_str and "." not in num_str:
            num_str = num_str.replace(",", ".")
        else:
            num_str = num_str.replace(",", "")
        amount = float(num_str)
        multiplier = 1
        for word, mult in _COP_MULTIPLIERS.items():
            if word in s:
                multiplier = mult
                break
        return amount * multiplier >= _MIN_PLAUSIBLE_COP
    except Exception:
        return True


def _find_invalid_numeric_toolcall(stored_tool_calls: List[Dict[str, Any]]) -> Optional[Tuple[str, str]]:
    """Busca args numéricos inválidos en calculate_credit_score. Retorna (tool, field) o None."""
    try:
        for tc in stored_tool_calls:
            if tc.get("name") == "calculate_credit_score":
                args = tc.get("args") or {}
                for field in ("ingresos_mensuales", "gastos_mensuales"):
                    value = args.get(field)
                    if value is not None and str(value).strip() != "" and not _is_plausible_cop_amount(value):
                        return tc.get("name"), field
        return None
    except Exception as e:
        logger.warning(f"🌿 [TOOL-SUPPRESS] validator_error fail_open error={type(e).__name__}")
        return None


def _maybe_reprompt_after_suppression_sync(
    messages: List[Dict[str, Any]],
    params: Dict[str, Any],
    timeout: float,
    role: str,
    shim: _ResponseShim,
    emulated: bool,
    tools: Optional[List[Any]],
) -> _ResponseShim:
    """
    Si Rama A Qwen emitió calculate_credit_score con montos no plausibles, re-prompt
    una sola vez con directiva de transporte. Fail-open ante error o re-incidencia.
    """
    if emulated:
        return shim
    invalid = _find_invalid_numeric_toolcall(shim._tool_calls)
    if invalid is None:
        return shim
    tool_name, field = invalid
    logger.info(f"🔧 [TOOL-SUPPRESS] tool={tool_name} field={field} reason=implausible_absolute_amount")
    reprompt_messages = list(messages)
    reprompt_messages.append({"role": "system", "content": _TOOLCALL_SUPPRESSION_DIRECTIVE})
    try:
        openai_response2 = _call_qwen_sync(reprompt_messages, params, timeout, role=role)
    except Exception as e:
        logger.warning(f"🌿 [TOOL-SUPPRESS] retry_error fail_open error={type(e).__name__}")
        return shim
    shim2 = _parse_openai_response(openai_response2, emulated_toolcall=emulated, tools=tools)
    invalid2 = _find_invalid_numeric_toolcall(shim2._tool_calls)
    if invalid2 is None:
        return shim2
    logger.warning(f"🌿 [TOOL-SUPPRESS] retry_failed fail_open tool={invalid2[0]} field={invalid2[1]}")
    return shim2


async def _maybe_reprompt_after_suppression_async(
    messages: List[Dict[str, Any]],
    params: Dict[str, Any],
    timeout: float,
    role: str,
    shim: _ResponseShim,
    emulated: bool,
    tools: Optional[List[Any]],
) -> _ResponseShim:
    """Versión async de _maybe_reprompt_after_suppression_sync."""
    if emulated:
        return shim
    invalid = _find_invalid_numeric_toolcall(shim._tool_calls)
    if invalid is None:
        return shim
    tool_name, field = invalid
    logger.info(f"🔧 [TOOL-SUPPRESS] tool={tool_name} field={field} reason=implausible_absolute_amount")
    reprompt_messages = list(messages)
    reprompt_messages.append({"role": "system", "content": _TOOLCALL_SUPPRESSION_DIRECTIVE})
    try:
        openai_response2 = await _call_qwen_async(reprompt_messages, params, timeout, role=role)
    except Exception as e:
        logger.warning(f"🌿 [TOOL-SUPPRESS] retry_error fail_open error={type(e).__name__}")
        return shim
    shim2 = _parse_openai_response(openai_response2, emulated_toolcall=emulated, tools=tools)
    invalid2 = _find_invalid_numeric_toolcall(shim2._tool_calls)
    if invalid2 is None:
        return shim2
    logger.warning(f"🌿 [TOOL-SUPPRESS] retry_failed fail_open tool={invalid2[0]} field={invalid2[1]}")
    return shim2


# ---------------------------------------------------------------------------
# Parsing de respuestas Qwen
# ---------------------------------------------------------------------------
def _parse_openai_response(
    openai_response: Dict[str, Any],
    emulated_toolcall: bool = False,
    tools: Optional[List[Any]] = None,
) -> _ResponseShim:
    """Convierte respuesta OpenAI/Qwen a shim google-genai."""
    choice = openai_response.get("choices", [{}])[0]
    message = choice.get("message", {})
    content = message.get("content")
    tool_calls = message.get("tool_calls") or []

    parts: List[Dict[str, Any]] = []
    stored_tool_calls: List[Dict[str, Any]] = []

    if emulated_toolcall and content:
        # Rama B: parsear JSON de la directiva
        parsed = _try_parse_json(content)
        if isinstance(parsed, dict):
            if "tool_call" in parsed:
                tc = parsed["tool_call"]
                name = tc.get("name", "") if isinstance(tc, dict) else ""
                args = tc.get("args", {}) if isinstance(tc, dict) else {}
                parts.append({"type": "function_call", "_function_call": {"name": name, "args": args}})
                stored_tool_calls.append({"id": f"emul_{name}", "name": name, "args": args})
            elif "final" in parsed:
                parts.append({"type": "text", "text": str(parsed["final"])})
            else:
                parts.append({"type": "text", "text": content})
        else:
            parts.append({"type": "text", "text": content})
    else:
        # Rama A / texto normal
        required_by_tool = _extract_required_fields(tools)
        if content:
            parts.append({"type": "text", "text": content})
        for tc in tool_calls:
            if tc.get("type") == "function":
                func = tc.get("function", {})
                name = func.get("name", "")
                arguments = func.get("arguments", "{}")
                try:
                    args = json.loads(arguments)
                except Exception:
                    args = {}
                # [BOT-BUILD-TOOLCALL-FB1-084] Poda args opcionales inferidos.
                args = _prune_ungrounded_args(name, args, required_by_tool.get(name, set()))
                parts.append({"type": "function_call", "_function_call": {"name": name, "args": args}})
                stored_tool_calls.append(
                    {
                        "id": tc.get("id", f"call_{name}"),
                        "name": name,
                        "args": args,
                    }
                )

    usage = openai_response.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0) or 0
    candidates_tokens = usage.get("completion_tokens", 0) or 0
    total_tokens = usage.get("total_tokens", 0) or 0

    has_fc = any(p.get("type") == "function_call" for p in parts)
    if emulated_toolcall:
        # Rama B: el texto SIEMPRE deriva de las parts parseadas; jamás del
        # envelope JSON crudo (Bug F3).
        text_segments = [p.get("text", "") for p in parts if p.get("type") == "text"]
        text = "".join(text_segments) if text_segments else None
    else:
        text = content if not tool_calls and not has_fc else None
        if text is None and parts and parts[0].get("type") == "text":
            text = parts[0].get("text")

    return _ResponseShim(
        text=text,
        parts=parts,
        prompt_tokens=prompt_tokens,
        candidates_tokens=candidates_tokens,
        total_tokens=total_tokens,
        tool_calls=stored_tool_calls,
    )


def _try_parse_json(text: str) -> Any:
    """Intenta parsear JSON de manera robusta."""
    try:
        return json.loads(text)
    except Exception:
        # Intentar limpiar fences markdown
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
            try:
                return json.loads(cleaned)
            except Exception:
                pass
    return None


# ---------------------------------------------------------------------------
# Error formatting
# ---------------------------------------------------------------------------
def format_qwen_error_structured(e: Exception) -> str:
    """Whitelist PII-safe de errores Qwen/DashScope. Fallback no-vacío."""
    allowed = {"code", "status", "request_id", "error_type"}

    def _fallback() -> str:
        return f"code=None status=None error_type={type(e).__name__!r} body_redacted=True"

    try:
        fields: Dict[str, Any] = {}
        for key in allowed:
            val = getattr(e, key, None)
            if val is not None:
                fields[key] = val

        # Respuestas httpx con body JSON
        response = getattr(e, "response", None)
        if response is not None:
            try:
                body = response.json()
                if isinstance(body, dict):
                    for key in ("code", "status", "request_id", "id"):
                        if key in body and key in allowed:
                            fields[key] = body[key]
                    err = body.get("error", {})
                    if isinstance(err, dict):
                        for key in ("code", "status", "type"):
                            if key in err and key in allowed:
                                fields[key] = err[key]
                        if "request_id" in err and "request_id" in allowed:
                            fields["request_id"] = err["request_id"]
            except Exception:
                pass
            try:
                fields["status"] = response.status_code
            except Exception:
                pass

        if "error_type" not in fields:
            fields["error_type"] = type(e).__name__

        # Si no hay campos permitidos de interés forense, usar fallback explícito
        if not any(k in fields for k in ("code", "status", "request_id")):
            return _fallback()
        return " ".join(f"{k}={v!r}" for k, v in fields.items())
    except Exception:
        logger.exception("❌ [LLM CLIENT] Error formatting Qwen error")
        return _fallback()


# ---------------------------------------------------------------------------
# Detección de errores retriables
# ---------------------------------------------------------------------------
def _is_retriable_qwen_error(e: Exception) -> Tuple[bool, str]:
    """Timeout/429/5xx son retriables hacia Gemini."""
    if isinstance(e, (TimeoutError,)):
        return True, "timeout"
    try:
        import httpx

        if isinstance(e, httpx.TimeoutException):
            return True, "httpx_timeout"
        response = getattr(e, "response", None)
        if response is not None:
            status = getattr(response, "status_code", 0)
            if status == 429:
                return True, f"429"
            if 500 <= status < 600:
                return True, f"{status}"
    except Exception:
        pass
    return False, type(e).__name__


# ---------------------------------------------------------------------------
# Llamadas HTTP a Qwen
# ---------------------------------------------------------------------------
def _qwen_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {os.getenv('QWEN_OMNI_API_KEY', '')}",
        "Content-Type": "application/json",
    }


def _qwen_base_url() -> str:
    return os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")


def _qwen_model(role: str = "multimodal") -> str:
    """Modelo Qwen según rol: agentic → turbo; multimodal → omni-turbo."""
    if role == "agentic":
        return os.getenv("QWEN_AGENTIC_MODEL", os.getenv("QWEN_PRIMARY_MODEL", "qwen-turbo"))
    return os.getenv("QWEN_MULTIMODAL_MODEL", os.getenv("QWEN_PRIMARY_MODEL", "qwen-omni-turbo"))


def _gemini_model() -> str:
    """Model ID del backend Gemini (fallback). Env-parametrizado (H4)."""
    return os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash")


def _call_qwen_sync(
    messages: List[Dict[str, Any]],
    params: Dict[str, Any],
    timeout: float,
    role: str = "multimodal",
) -> Dict[str, Any]:
    model_id = _qwen_model(role=role)
    logger.info(f"🚀 [QWEN ROUTE] provider=dashscope model={model_id} role={role}")
    payload = {
        "model": model_id,
        "messages": messages,
        **params,
    }
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            f"{_qwen_base_url()}/chat/completions",
            headers=_qwen_headers(),
            json=payload,
        )
        response.raise_for_status()
        return response.json()


async def _call_qwen_async(
    messages: List[Dict[str, Any]],
    params: Dict[str, Any],
    timeout: float,
    role: str = "multimodal",
) -> Dict[str, Any]:
    model_id = _qwen_model(role=role)
    logger.info(f"🚀 [QWEN ROUTE] provider=dashscope model={model_id} role={role}")
    payload = {
        "model": model_id,
        "messages": messages,
        **params,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{_qwen_base_url()}/chat/completions",
            headers=_qwen_headers(),
            json=payload,
        )
        response.raise_for_status()
        return response.json()


# ---------------------------------------------------------------------------
# Chat helper
# ---------------------------------------------------------------------------
class DualProviderChat:
    """Chat async compatible con google-genai chats."""

    def __init__(self, facade: "DualProviderClient", model: Optional[str] = None):
        self._facade = facade
        self._model = model or get_active_model_id(role=facade._role)
        self._history: List[Dict[str, Any]] = []  # turns con role, parts, tool_calls
        self._gemini_chat: Any = None

    def to_openai_messages(self) -> List[Dict[str, Any]]:
        """Convierte historial interno a mensajes OpenAI ordenados."""
        messages: List[Dict[str, Any]] = []
        pending_assistant_calls: List[Dict[str, Any]] = []

        for turn in self._history:
            role = turn["role"]
            parts = turn.get("parts", [])
            tool_calls = turn.get("tool_calls", [])

            if role == "model":
                # Primero: texto/modelo
                text_parts = []
                func_parts = []
                for p in parts:
                    if SDK_AVAILABLE and types is not None and isinstance(p, types.Part):
                        if p.function_call is not None:
                            func_parts.append(p.function_call)
                        elif p.text:
                            text_parts.append(p.text)
                    else:
                        fc = getattr(p, "function_call", None)
                        text = getattr(p, "text", None)
                        if fc is not None:
                            func_parts.append(fc)
                        elif text:
                            text_parts.append(text)

                if text_parts or func_parts:
                    msg: Dict[str, Any] = {"role": "assistant"}
                    if text_parts:
                        msg["content"] = "\n".join(text_parts)
                    else:
                        msg["content"] = None
                    if tool_calls:
                        msg["tool_calls"] = [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": json.dumps(tc["args"]),
                                },
                            }
                            for tc in tool_calls
                        ]
                        pending_assistant_calls = list(tool_calls)
                    elif func_parts:
                        synthetic = []
                        pending_assistant_calls = []
                        for i, fc in enumerate(func_parts):
                            name = getattr(fc, "name", "") or ""
                            args = getattr(fc, "args", {}) or {}
                            call_id = f"call_{len(messages)}_{i}"
                            synthetic.append(
                                {
                                    "id": call_id,
                                    "type": "function",
                                    "function": {"name": name, "arguments": json.dumps(args)},
                                }
                            )
                            pending_assistant_calls.append({"id": call_id, "name": name, "args": args})
                        msg["tool_calls"] = synthetic
                    messages.append(msg)

            elif role == "user":
                # Puede incluir function_response parts → mensajes tool
                func_responses = []
                text_parts = []
                for p in parts:
                    fr = None
                    text = None
                    if SDK_AVAILABLE and types is not None and isinstance(p, types.Part):
                        fr = p.function_response
                        text = p.text
                    else:
                        fr = getattr(p, "function_response", None)
                        text = getattr(p, "text", None)

                    if fr is not None:
                        name = getattr(fr, "name", "") or ""
                        response = getattr(fr, "response", {}) or {}
                        # Emparejar con el primer pending_assistant_call no usado del mismo nombre
                        matched_id = None
                        for idx, tc in enumerate(pending_assistant_calls):
                            if tc.get("name") == name:
                                matched_id = tc["id"]
                                pending_assistant_calls.pop(idx)
                                break
                        if matched_id is None and pending_assistant_calls:
                            matched_id = pending_assistant_calls.pop(0)["id"]
                        if matched_id is None:
                            matched_id = f"call_{len(messages)}_{name}"
                        func_responses.append(
                            {
                                "role": "tool",
                                "tool_call_id": matched_id,
                                "content": json.dumps(response) if isinstance(response, dict) else str(response),
                            }
                        )
                    elif text:
                        text_parts.append(text)

                if text_parts:
                    # Convertir a OpenAI multimodal si hay inline data
                    openai_parts: List[Dict[str, Any]] = []
                    for p in parts:
                        converted = _part_to_openai_content(p)
                        if converted:
                            openai_parts.append(converted)
                    if openai_parts:
                        messages.append({"role": "user", "content": openai_parts})
                if func_responses:
                    messages.extend(func_responses)

        return messages

    async def send_message(self, contents: Any, config: Any = None) -> Any:
        """Envía un turno y retorna respuesta google-genai-shapped."""
        # F1.5: medir el historial ANTES de append para poder contar cuántos
        # mensajes OpenAI aporta el turno actual después de la conversión.
        prev_turn_messages = len(self.to_openai_messages())

        # Agregar turno actual al historial
        current_parts = _normalize_parts(contents)
        self._history.append({"role": "user", "parts": current_parts})

        flag = await is_qwen_enabled_async()
        logger.info(f"🚦 [QWEN ROUTE DECISION] qwen_enabled={flag} role={self._facade._role}")
        if not flag:
            return await self._send_via_gemini(contents, config)

        # Guard de audio: contenido de audio va a Gemini salvo QWEN_AUDIO_ENABLED=true
        history_parts = [p for turn in self._history for p in turn.get("parts", [])]
        if (_parts_have_audio(current_parts) or _parts_have_audio(history_parts)) and not _qwen_audio_enabled():
            return await self._send_via_gemini(contents, config)

        # Modo Qwen
        emulated = os.getenv("QWEN_TOOLCALL_MODE", "native").lower() == "emulated"
        messages, _ = _build_openai_messages(
            contents=contents,
            config=config,
            chat_history=self,
            emulated_toolcall=emulated,
        )

        # El turno actual ya está dentro de chat_history; cuenta por delta.
        current_turn_count = len(self.to_openai_messages()) - prev_turn_messages
        messages, trimmed = _trim_history_to_budget(messages, current_turn_count)
        if trimmed:
            logger.info("✂️ [QWEN CONTEXT] history_trimmed old_messages to fit 33K budget")

        # Verificar si el turno actual solo excede el presupuesto
        if _estimate_token_budget(messages) > _QWEN_CONTEXT_TOKEN_BUDGET:
            logger.error("🚨 [QWEN CONTEXT] budget_exceeded current_turn_only -> failover to Gemini")
            return await self._failover_to_gemini(contents, config, reason="current_turn_budget_exceeded")

        params = _config_to_openai_params(config)
        if not emulated and params.get("tools"):
            params["tools"] = _relax_credit_tool_for_qwen(params["tools"])
        if emulated:
            params.pop("tools", None)

        timeout = _qwen_timeout_default()
        try:
            openai_response = await _call_qwen_async(messages, params, timeout, role=self._facade._role)
        except Exception as e:
            retriable, reason = _is_retriable_qwen_error(e)
            if retriable:
                logger.warning(
                    f"🔄 [DUAL FAILOVER] provider=dashscope→gemini reason={reason} "
                    f"forensic={format_qwen_error_structured(e)}"
                )
                return await self._failover_to_gemini(contents, config, reason=reason, original_exception=e)
            logger.exception("❌ [LLM CLIENT] Qwen call failed (non-retriable)")
            logger.error(f"🚨 [QWEN FORENSIC] {format_qwen_error_structured(e)}")
            raise

        tools = getattr(config, "tools", None) if config else None
        shim = _parse_openai_response(openai_response, emulated_toolcall=emulated, tools=tools)
        shim = await _maybe_reprompt_after_suppression_async(
            messages, params, timeout, self._facade._role, shim, emulated, tools
        )
        self._history.append(
            {"role": "model", "parts": _response_shim_to_parts(shim), "tool_calls": shim._tool_calls}
        )
        return shim

    async def _send_via_gemini(self, contents: Any, config: Any) -> Any:
        """Delega el chat al backend Gemini real."""
        gemini = await self._facade._get_gemini_async()
        if gemini is None:
            raise RuntimeError("Gemini backend not available")
        if self._gemini_chat is None:
            self._gemini_chat = gemini.aio.chats.create(model=_gemini_model())
        response = await self._gemini_chat.send_message(contents, config=config)
        # Guardar parts gemini en historial (copia superficial)
        gemini_parts = []
        try:
            gemini_parts = list(response.candidates[0].content.parts)
        except Exception:
            pass
        self._history.append({"role": "model", "parts": gemini_parts, "tool_calls": []})
        return response

    async def _failover_to_gemini(
        self, contents: Any, config: Any, reason: str, original_exception: Optional[Exception] = None
    ) -> Any:
        """Reintenta contra Gemini con el payload google-types original."""
        gemini = await self._facade._get_gemini_async()
        if gemini is None:
            raise RuntimeError(f"Qwen failed ({reason}) and Gemini backend not available")
        forensic_error = original_exception if original_exception is not None else RuntimeError(reason)
        logger.warning(
            f"🔄 [DUAL FAILOVER] provider=dashscope→gemini reason={reason} "
            f"forensic={format_qwen_error_structured(forensic_error)}"
        )
        # Reconstruir contents como lista de Content para Gemini
        conversation = self._to_gemini_contents(contents)
        response = await gemini.aio.models.generate_content(
            model=_gemini_model(),
            contents=conversation,
            config=config,
        )
        gemini_parts = []
        try:
            gemini_parts = list(response.candidates[0].content.parts)
        except Exception:
            pass
        self._history.append({"role": "model", "parts": gemini_parts, "tool_calls": []})
        return response

    def _to_gemini_contents(self, current_contents: Any) -> List[Any]:
        """Reconstruye la conversación como lista de types.Content para Gemini."""
        contents: List[Any] = []
        if SDK_AVAILABLE and types is not None:
            for turn in self._history:
                role = turn["role"]
                role_name = "model" if role == "model" else "user"
                parts = list(turn.get("parts", []))
                if parts:
                    contents.append(types.Content(role=role_name, parts=parts))
            # Asegurar que el turno actual esté representado
            if current_contents is not None:
                current_parts = _normalize_parts(current_contents)
                # Si el último turno ya es user y coincide, no duplicar
                if not (self._history and self._history[-1]["role"] == "user"):
                    contents.append(types.Content(role="user", parts=current_parts))
        else:
            contents = []
        return contents


def _response_shim_to_parts(shim: _ResponseShim) -> List[Any]:
    """Convierte parts del shim a google-genai Parts."""
    parts: List[Any] = []
    for p in shim.candidates[0].content.parts:
        if SDK_AVAILABLE and types is not None:
            if p.function_call is not None:
                fc = p.function_call
                parts.append(types.Part.from_function_call(name=fc.name, args=fc.args))
            elif p.text is not None:
                parts.append(types.Part.from_text(text=p.text))
        else:
            if p.function_call is not None:
                parts.append({"function_call": {"name": p.function_call.name, "args": p.function_call.args}})
            elif p.text is not None:
                parts.append({"text": p.text})
    return parts


# ---------------------------------------------------------------------------
# Namespaces del facade
# ---------------------------------------------------------------------------
class _AioModels:
    def __init__(self, facade: "DualProviderClient"):
        self._facade = facade

    async def generate_content(self, model: str, contents: Any, config: Any = None) -> Any:
        return await self._facade._generate_content_async(model, contents, config)


class _AioChats:
    def __init__(self, facade: "DualProviderClient"):
        self._facade = facade

    def create(self, model: Optional[str] = None, **kwargs: Any) -> DualProviderChat:
        return DualProviderChat(self._facade, model=model)


class _AioNamespace:
    def __init__(self, facade: "DualProviderClient"):
        self.models = _AioModels(facade)
        self.chats = _AioChats(facade)


class _ModelsSync:
    def __init__(self, facade: "DualProviderClient"):
        self._facade = facade

    def generate_content(self, model: str, contents: Any, config: Any = None) -> Any:
        return self._facade._generate_content_sync(model, contents, config)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        gemini = self._facade._gemini_sync
        if gemini is None:
            raise AttributeError(f"Gemini sync backend not available ({name})")
        return getattr(gemini.models, name)


# ---------------------------------------------------------------------------
# Facade principal
# ---------------------------------------------------------------------------
class DualProviderClient:
    """
    Fachada dual Gemini/Qwen con superficie google-genai.
    """

    def __init__(
        self,
        gemini_sync: Optional[Any] = None,
        gemini_async: Optional[Any] = None,
        role: str = "multimodal",
    ):
        self._gemini_sync = gemini_sync
        self._gemini_async = gemini_async
        self._role = role
        self.models = _ModelsSync(self)
        self.aio = _AioNamespace(self)

    @property
    def _model_id(self) -> str:
        return get_active_model_id(role=self._role)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if self._gemini_sync is None:
            raise AttributeError(f"Gemini sync backend not available ({name})")
        return getattr(self._gemini_sync, name)

    async def _get_gemini_async(self) -> Any:
        if self._gemini_async is None:
            self._gemini_async = await get_shared_genai_client_async(
                vertexai=True,
                project="tiendalasmotos",
                location="us-central1",
            )
        return self._gemini_async

    def _get_gemini_sync(self) -> Any:
        if self._gemini_sync is None:
            self._gemini_sync = get_shared_genai_client(
                vertexai=True,
                project="tiendalasmotos",
                location="us-central1",
            )
        return self._gemini_sync

    def _generate_content_sync(self, model: str, contents: Any, config: Any = None) -> Any:
        if not is_qwen_enabled():
            gemini = self._get_gemini_sync()
            if gemini is None:
                raise RuntimeError("Gemini backend not available")
            return gemini.models.generate_content(model=model, contents=contents, config=config)

        # Qwen sync path
        if _contents_have_audio(contents) and not _qwen_audio_enabled():
            gemini = self._get_gemini_sync()
            if gemini is None:
                raise RuntimeError("Gemini backend not available")
            return gemini.models.generate_content(model=_gemini_model(), contents=contents, config=config)

        emulated = os.getenv("QWEN_TOOLCALL_MODE", "native").lower() == "emulated"
        messages, _ = _build_openai_messages(
            contents=contents,
            config=config,
            emulated_toolcall=emulated,
        )
        params = _config_to_openai_params(config)
        if not emulated and params.get("tools"):
            params["tools"] = _relax_credit_tool_for_qwen(params["tools"])
        if emulated:
            params.pop("tools", None)

        try:
            openai_response = _call_qwen_sync(messages, params, _qwen_timeout_default(), role=self._role)
        except Exception as e:
            retriable, reason = _is_retriable_qwen_error(e)
            if retriable:
                logger.warning(
                    f"🔄 [DUAL FAILOVER] provider=dashscope→gemini reason={reason} "
                    f"forensic={format_qwen_error_structured(e)}"
                )
                gemini = self._get_gemini_sync()
                if gemini is None:
                    raise RuntimeError(f"Qwen failed ({reason}) and Gemini backend not available")
                return gemini.models.generate_content(model=_gemini_model(), contents=contents, config=config)
            logger.exception("❌ [LLM CLIENT] Qwen sync call failed (non-retriable)")
            logger.error(f"🚨 [QWEN FORENSIC] {format_qwen_error_structured(e)}")
            raise

        tools = getattr(config, "tools", None) if config else None
        shim = _parse_openai_response(openai_response, emulated_toolcall=emulated, tools=tools)
        return _maybe_reprompt_after_suppression_sync(
            messages, params, _qwen_timeout_default(), self._role, shim, emulated, tools
        )

    async def _generate_content_async(self, model: str, contents: Any, config: Any = None) -> Any:
        if not await is_qwen_enabled_async():
            gemini = await self._get_gemini_async()
            if gemini is None:
                raise RuntimeError("Gemini backend not available")
            return await gemini.aio.models.generate_content(model=model, contents=contents, config=config)

        # Qwen async path
        if _contents_have_audio(contents) and not _qwen_audio_enabled():
            gemini = await self._get_gemini_async()
            if gemini is None:
                raise RuntimeError("Gemini backend not available")
            return await gemini.aio.models.generate_content(model=_gemini_model(), contents=contents, config=config)

        emulated = os.getenv("QWEN_TOOLCALL_MODE", "native").lower() == "emulated"
        messages, _ = _build_openai_messages(
            contents=contents,
            config=config,
            emulated_toolcall=emulated,
        )
        params = _config_to_openai_params(config)
        if not emulated and params.get("tools"):
            params["tools"] = _relax_credit_tool_for_qwen(params["tools"])
        if emulated:
            params.pop("tools", None)

        try:
            openai_response = await _call_qwen_async(messages, params, _qwen_timeout_default(), role=self._role)
        except Exception as e:
            retriable, reason = _is_retriable_qwen_error(e)
            if retriable:
                logger.warning(
                    f"🔄 [DUAL FAILOVER] provider=dashscope→gemini reason={reason} "
                    f"forensic={format_qwen_error_structured(e)}"
                )
                gemini = await self._get_gemini_async()
                if gemini is None:
                    raise RuntimeError(f"Qwen failed ({reason}) and Gemini backend not available")
                return await gemini.aio.models.generate_content(model=_gemini_model(), contents=contents, config=config)
            logger.exception("❌ [LLM CLIENT] Qwen async call failed (non-retriable)")
            logger.error(f"🚨 [QWEN FORENSIC] {format_qwen_error_structured(e)}")
            raise

        tools = getattr(config, "tools", None) if config else None
        shim = _parse_openai_response(openai_response, emulated_toolcall=emulated, tools=tools)
        return await _maybe_reprompt_after_suppression_async(
            messages, params, _qwen_timeout_default(), self._role, shim, emulated, tools
        )


# ---------------------------------------------------------------------------
# Fábricas públicas
# ---------------------------------------------------------------------------
_SHARED_LLM_CLIENTS: Dict[str, DualProviderClient] = {}
_SHARED_LLM_LOCK = threading.Lock()
# Reutilizar locks async del genai_client_service para LLM
_CLIENT_ASYNC_LOCKS: Dict[str, asyncio.Lock] = {}


def get_shared_llm_client(
    vertexai: bool = True,
    api_key: Optional[str] = None,
    project: Optional[str] = "tiendalasmotos",
    location: Optional[str] = "us-central1",
    credentials: Any = None,
    role: str = "multimodal",
) -> DualProviderClient:
    """Fábrica sync del facade dual."""
    from app.services.genai_client_service import _client_key

    base_key = _client_key(vertexai, api_key, project, location, credentials)
    key = f"{base_key}|role={role}"
    client = _SHARED_LLM_CLIENTS.get(key)
    if client is not None:
        return client

    with _SHARED_LLM_LOCK:
        client = _SHARED_LLM_CLIENTS.get(key)
        if client is not None:
            return client
        gemini_sync = get_shared_genai_client(
            vertexai=vertexai,
            api_key=api_key,
            project=project,
            location=location,
            credentials=credentials,
        )
        client = DualProviderClient(gemini_sync=gemini_sync, role=role)
        _SHARED_LLM_CLIENTS[key] = client
        return client


async def get_shared_llm_client_async(
    vertexai: bool = True,
    api_key: Optional[str] = None,
    project: Optional[str] = "tiendalasmotos",
    location: Optional[str] = "us-central1",
    credentials: Any = None,
    role: str = "multimodal",
) -> DualProviderClient:
    """Fábrica async del facade dual."""
    from app.services.genai_client_service import _client_key

    base_key = _client_key(vertexai, api_key, project, location, credentials)
    key = f"{base_key}|role={role}"
    client = _SHARED_LLM_CLIENTS.get(key)
    if client is not None:
        return client

    if key not in _CLIENT_ASYNC_LOCKS:
        _CLIENT_ASYNC_LOCKS[key] = asyncio.Lock()
    lock = _CLIENT_ASYNC_LOCKS[key]

    async with lock:
        client = _SHARED_LLM_CLIENTS.get(key)
        if client is not None:
            return client
        gemini_async = await get_shared_genai_client_async(
            vertexai=vertexai,
            api_key=api_key,
            project=project,
            location=location,
            credentials=credentials,
        )
        gemini_sync = await asyncio.to_thread(
            get_shared_genai_client,
            vertexai,
            api_key,
            project,
            location,
            credentials,
        )
        client = DualProviderClient(gemini_sync=gemini_sync, gemini_async=gemini_async, role=role)
        _SHARED_LLM_CLIENTS[key] = client
        return client


def reset_shared_llm_clients() -> None:
    """Hook de aislamiento para tests."""
    global _SHARED_LLM_CLIENTS, _FLAG_DB_CLIENT
    _SHARED_LLM_CLIENTS.clear()
    _CLIENT_ASYNC_LOCKS.clear()
    _FLAG_DB_CLIENT = None
    _invalidate_qwen_flag_cache()
    logger.debug("[LLM CLIENT] Shared LLM clients reset (test-only)")
