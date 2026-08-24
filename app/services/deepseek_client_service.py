"""Cliente DeepSeek V4 Flash 0731 vía OpenRouter para producción.

Espejo del patrón Qwen en llm_client_service.py: cliente OpenAI-compatible
(httpx) contra OpenRouter, con guard anti-slug, sanitización de headers y
preflight de modelo.

Inmutabilidad: no toca app/core/ai_brain.py, prompts.py, personality.json ni
juan_pablo_personality.docx.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_SLUG = "deepseek/deepseek-v4-flash-0731"
PROHIBITED_SLUG = "deepseek/deepseek-v4-flash"

_NON_ASCII_WHITESPACE = {
    "\xa0",       # NBSP
    "\u200b",     # zero-width space
    "\u2002",     # en space
    "\u2003",     # em space
    "\u2009",     # thin space
    "\u202f",     # narrow no-break space
}


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
            f"U+{ord(bad):04X} ({bad!r}). Re-exporta la variable de entorno "
            f"correspondiente sin copiar/pegar desde web UIs."
        ) from exc
    return cleaned


def _get_deepseek_model() -> str:
    model = os.getenv("DEEPSEEK_MODEL", DEFAULT_SLUG)
    if model == PROHIBITED_SLUG:
        raise ValueError(
            f"[GUARD SLUG PROHIBIDO] DEEPSEEK_MODEL='{PROHIBITED_SLUG}' apunta "
            f"al build 0423 pre-reentrenamiento. Use obligatoriamente "
            f"DEEPSEEK_MODEL='{DEFAULT_SLUG}'."
        )
    return model


class DeepSeekOpenRouterClient:
    """Cliente OpenAI-compatible contra OpenRouter para DeepSeek."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        raw_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not raw_key:
            raise ValueError(
                "OPENROUTER_API_KEY no configurada. "
                "Binda el secreto en Cloud Run (COND-1)."
            )
        self.api_key = _sanitize_header_value("Authorization", raw_key)
        self.model = model or _get_deepseek_model()
        self.base_url = (base_url or os.getenv("OPENROUTER_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_sanitize_header_value('Authorization', self.api_key)}",
            "HTTP-Referer": _sanitize_header_value("HTTP-Referer", "https://tiendalasmotos.co"),
            "X-Title": _sanitize_header_value("X-Title", "Bot-TiendaLasMotos-HybridRouter"),
        }

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: str | dict[str, Any] = "auto",
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """Llama a /chat/completions y devuelve el JSON crudo de OpenAI."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
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
            return resp.json()

    async def achat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: str | dict[str, Any] = "auto",
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """Llama asíncrono a /chat/completions."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    def fetch_available_models(self) -> list[dict[str, Any]]:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(f"{self.base_url}/models", headers=self._headers())
            resp.raise_for_status()
            return resp.json().get("data", [])

    def preflight(self) -> dict[str, Any]:
        """Valida que el slug exista en /models."""
        models = self.fetch_available_models()
        slugs = {m.get("id", "") for m in models}
        if self.model in slugs:
            return {"status": "OK", "model": self.model}
        suggestions = sorted({m.get("id", "") for m in models if "deepseek-v4" in m.get("id", "").lower()})
        raise ValueError(
            f"[PREFLIGHT FAIL] DeepSeek model='{self.model}' no encontrado en "
            f"{self.base_url}/models. Candidatos: {suggestions}. "
            f"Revisa DEEPSEEK_MODEL / OPENROUTER_BASE_URL."
        )
