"""Cliente OpenRouter para DeepSeek V4 Flash 0731 y GLM-5.2 (BOT-BUILD-CHINA-EVAL-090-D2)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEEPSEEK_DEFAULT_SLUG = "deepseek/deepseek-v4-flash-0731"
DEEPSEEK_PROHIBITED_SLUG = "deepseek/deepseek-v4-flash"
GLM52_DEFAULT_SLUG = "z-ai/glm-5.2"

# Caracteres no-ASCII comunes al copiar/pegar desde dashboards web.
_NON_ASCII_WHITESPACE = {
    "\xa0",       # NBSP
    "\u200b",     # zero-width space
    "\u2002",     # en space
    "\u2003",     # em space
    "\u2009",     # thin space
    "\u202f",     # narrow no-break space
}

_PREFLIGHT_OK: set[str] = set()


def _sanitize_header_value(name: str, value: str) -> str:
    """Elimina whitespace no-ASCII y valida ASCII puro para headers HTTP."""
    if not isinstance(value, str):
        value = str(value)
    cleaned = value
    for ch in _NON_ASCII_WHITESPACE:
        cleaned = cleaned.replace(ch, " ")
    cleaned = cleaned.strip()
    try:
        cleaned.encode("ascii")
    except UnicodeEncodeError as exc:
        bad = exc.object[exc.start : exc.end]
        raise ValueError(
            f"[HEADER-SANITIZE] Header '{name}' contiene carácter no-ASCII "
            f"U+{ord(bad):04X} ({bad!r}) en posición {exc.start}. "
            f"Re-exporta la variable de entorno correspondiente sin copiar/pegar desde web UIs."
        ) from exc
    return cleaned


@dataclass(frozen=True)
class LLMResponse:
    provider: str
    model: str
    content: str | None
    tool_calls: list[dict[str, Any]]
    raw: dict[str, Any]


class OpenRouterClient:
    """Cliente OpenAI-compatible contra OpenRouter (o gateway compatible)."""

    def __init__(self, provider: str, api_key: str | None, model: str) -> None:
        if provider == "deepseek" and model == DEEPSEEK_PROHIBITED_SLUG:
            raise ValueError(
                f"[GUARD SLUG PROHIBIDO] DEEPSEEK_MODEL='{DEEPSEEK_PROHIBITED_SLUG}' "
                f"apunta al build 0423 pre-reentrenamiento. "
                f"Use obligatoriamente DEEPSEEK_MODEL='{DEEPSEEK_DEFAULT_SLUG}'."
            )
        self.provider = provider
        self.base_url = os.getenv("CHINA_EVAL_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        raw_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not raw_key:
            raise ValueError("OPENROUTER_API_KEY no configurada")
        self.api_key = _sanitize_header_value("Authorization", raw_key)
        if raw_key != self.api_key:
            # Log forense ZSF sin PII: no imprimimos el valor, solo la acción.
            from scripts.china_eval.common.logging import log_event, new_trace_id
            log_event(
                trace_id=new_trace_id(),
                protocol="PREFLIGHT",
                variant=0,
                provider=provider,
                verdict="SANITIZED",
                reason="OPENROUTER_API_KEY contenía whitespace no-ASCII (ej. NBSP/zero-width) que fue corregido antes de enviar el header HTTP.",
            )
        self.model = model
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_sanitize_header_value('Authorization', self.api_key)}",
            "HTTP-Referer": _sanitize_header_value("HTTP-Referer", "https://tiendalasmotos.co"),
            "X-Title": _sanitize_header_value("X-Title", "Bot-TiendaLasMotos-ChinaEval"),
        }

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] = "auto",
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        message = choice.get("message", {})
        content = message.get("content")
        raw_tool_calls = message.get("tool_calls", [])
        tool_calls: list[dict[str, Any]] = []
        for tc in raw_tool_calls:
            tool_calls.append(
                {
                    "id": tc.get("id"),
                    "type": tc.get("type"),
                    "function": {
                        "name": tc.get("function", {}).get("name"),
                        "arguments": tc.get("function", {}).get("arguments"),
                    },
                }
            )
        return LLMResponse(
            provider=self.provider,
            model=data.get("model", self.model),
            content=content,
            tool_calls=tool_calls,
            raw=data,
        )

    def fetch_available_models(self) -> list[dict[str, Any]]:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(f"{self.base_url}/models", headers=self._headers())
            resp.raise_for_status()
            return resp.json().get("data", [])


def _suggest_candidates(models: list[dict[str, Any]], token: str) -> list[str]:
    return sorted({m.get("id", "") for m in models if token.lower() in m.get("id", "").lower()})


def preflight_models(provider: str, client: OpenRouterClient | None = None) -> dict[str, Any]:
    """Valida que el slug del proveedor exista en /models. Cachea por slug."""
    if client is None:
        client = get_client(provider)
    if client.model in _PREFLIGHT_OK:
        return {"status": "OK_CACHED", "provider": provider, "slug": client.model}

    models = client.fetch_available_models()
    slugs = {m.get("id", "") for m in models}
    if client.model in slugs:
        _PREFLIGHT_OK.add(client.model)
        return {"status": "OK", "provider": provider, "slug": client.model}

    suggestions: dict[str, list[str]] = {}
    if provider == "deepseek":
        suggestions["deepseek-v4"] = _suggest_candidates(models, "deepseek-v4")
    elif provider == "glm52":
        suggestions["glm"] = _suggest_candidates(models, "glm")

    raise ValueError(
        f"[PREFLIGHT FAIL] provider={provider} slug='{client.model}' no encontrado en {client.base_url}/models. "
        f"Candidatos sugeridos: {suggestions}. "
        f"Acción: revisar CHINA_EVAL_BASE_URL, DEEPSEEK_MODEL / GLM52_MODEL."
    )


def get_deepseek_client() -> OpenRouterClient:
    return OpenRouterClient(
        provider="deepseek",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        model=os.getenv("DEEPSEEK_MODEL", DEEPSEEK_DEFAULT_SLUG),
    )


def get_glm52_client() -> OpenRouterClient:
    return OpenRouterClient(
        provider="glm52",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        model=os.getenv("GLM52_MODEL", GLM52_DEFAULT_SLUG),
    )


def get_client(provider: str) -> OpenRouterClient:
    if provider == "deepseek":
        return get_deepseek_client()
    if provider == "glm52":
        return get_glm52_client()
    raise ValueError(f"Proveedor no soportado: {provider}")
