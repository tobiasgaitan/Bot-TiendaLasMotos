"""
GenAI Client Service (BOT-BUILD-GENAI-SINGLETON-050)
====================================================
Singleton perezoso y thread-safe del cliente google.genai.

Objetivo: erradicar la amplificación de 429 RESOURCE_EXHAUSTED en Turn 1 post-idle
al reutilizar UNA instancia de cliente genai por proceso, en lugar de crear un
cliente nuevo en cada request (whatsapp.py -> CerebroIA/VisionService/AudioService).

Contratos:
- get_shared_genai_client(): síncrona, thread-safe. Reservada para warm-up en
  main.py:_run_deferred_initialization (ejecutada vía asyncio.to_thread) y tests.
- get_shared_genai_client_async(): asíncrona, safe desde el event loop. Crea el
  cliente en un thread pool para no bloquear asyncio durante ADC/TLS handshake.
- reset_shared_clients(): hook de aislamiento para tests; NUNCA usar en producción.
- format_gemini_error_structured(e): forense 429 PII-safe por construcción.

Zero-Silent-Failures: todo path de error loggea logger.exception y retorna None,
respetando las guardas `if not self.client:` de los consumidores.
"""

import asyncio
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from google import genai
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    genai = None  # type: ignore
    logger.warning("⚠️ google-genai SDK not available; genai_client_service disabled")


# ---------------------------------------------------------------------------
# Estado global del singleton (por proceso)
# ---------------------------------------------------------------------------
_SHARED_CLIENTS: Dict[str, Any] = {}
_CLIENT_LOCKS: Dict[str, threading.Lock] = {}
_CLIENT_ASYNC_LOCKS: Dict[str, asyncio.Lock] = {}
_CLIENT_CREATION_TIMES: Dict[str, float] = {}
_CLIENT_REUSE_COUNTS: Dict[str, int] = {}


def _client_key(
    vertexai: bool = True,
    api_key: Optional[str] = None,
    project: Optional[str] = None,
    location: Optional[str] = None,
    credentials: Any = None,
) -> str:
    """Clave determinística para cachear variantes del cliente."""
    if api_key:
        return f"api_key:{api_key[:4]}***"
    creds_id = id(credentials) if credentials is not None else "adc"
    return f"vertex:{project}:{location}:{creds_id}"


def _create_client_sync(
    vertexai: bool = True,
    api_key: Optional[str] = None,
    project: Optional[str] = None,
    location: Optional[str] = None,
    credentials: Any = None,
) -> Any:
    """Crea un cliente genai de forma síncrona. Paridad exacta con call-sites previos."""
    if api_key and not vertexai:
        return genai.Client(api_key=api_key)

    kwargs: Dict[str, Any] = {
        "vertexai": True,
        "project": project,
        "location": location,
    }
    if credentials is not None:
        kwargs["credentials"] = credentials
    return genai.Client(**kwargs)


def _log_reuse(client: Any, key: str) -> None:
    """Log de reuso visible en Cloud Logging (criterio de éxito del ticket)."""
    age_s = time.monotonic() - _CLIENT_CREATION_TIMES.get(key, time.monotonic())
    count = _CLIENT_REUSE_COUNTS.get(key, 0)
    logger.info(
        f"♻️ [GENAI CLIENT] Reusing shared client "
        f"(id={id(client) & 0xFFFFFFFF:x}, key={key}, age_s={age_s:.1f}, "
        f"reuse_count={count}, pid={os.getpid()})"
    )


def _log_created(client: Any, key: str) -> None:
    """Log de creación visible en Cloud Logging."""
    logger.info(
        f"🆕 [GENAI CLIENT] Shared client created "
        f"(id={id(client) & 0xFFFFFFFF:x}, key={key}, pid={os.getpid()})"
    )


# ---------------------------------------------------------------------------
# Fábrica síncrona (warm-up + tests)
# ---------------------------------------------------------------------------
def get_shared_genai_client(
    vertexai: bool = True,
    api_key: Optional[str] = None,
    project: Optional[str] = "tiendalasmotos",
    location: Optional[str] = "us-central1",
    credentials: Any = None,
) -> Any:
    """
    Retorna el cliente genai compartido para la clave determinada (síncrono).

    Thread-safe mediante doble-chequeo con threading.Lock. La primera creación
    puede hacer I/O (ADC + TLS); por eso en producción esta función solo debe
    invocarse desde warm-up dentro de asyncio.to_thread, o desde el fast path
    cuando el cliente ya fue precalentado.
    """
    if not SDK_AVAILABLE or genai is None:
        logger.warning("⚠️ [GENAI CLIENT] SDK not available; returning None")
        return None

    key = _client_key(vertexai, api_key, project, location, credentials)
    lock = _CLIENT_LOCKS.setdefault(key, threading.Lock())

    # Fast path: lectura atómica (GIL) sin lock.
    client = _SHARED_CLIENTS.get(key)
    if client is not None:
        _CLIENT_REUSE_COUNTS[key] = _CLIENT_REUSE_COUNTS.get(key, 0) + 1
        _log_reuse(client, key)
        return client

    with lock:
        # Double-check: otro thread pudo crearlo mientras esperábamos.
        client = _SHARED_CLIENTS.get(key)
        if client is not None:
            _CLIENT_REUSE_COUNTS[key] = _CLIENT_REUSE_COUNTS.get(key, 0) + 1
            _log_reuse(client, key)
            return client

        try:
            client = _create_client_sync(vertexai, api_key, project, location, credentials)
            _SHARED_CLIENTS[key] = client
            _CLIENT_CREATION_TIMES[key] = time.monotonic()
            _CLIENT_REUSE_COUNTS[key] = 0
            _log_created(client, key)
            return client
        except Exception:
            logger.exception(f"❌ [GENAI CLIENT] Failed to create shared client (key={key})")
            return None


# ---------------------------------------------------------------------------
# Fábrica asíncrona (única consumida desde el event loop)
# ---------------------------------------------------------------------------
async def get_shared_genai_client_async(
    vertexai: bool = True,
    api_key: Optional[str] = None,
    project: Optional[str] = "tiendalasmotos",
    location: Optional[str] = "us-central1",
    credentials: Any = None,
) -> Any:
    """
    Retorna el cliente genai compartido (asíncrono, safe para event loop).

    La creación del cliente subyacente se delega a asyncio.to_thread para evitar
    bloquear el event loop durante el handshake ADC/TLS. El resto del camino
    comparte el mismo cache síncrono, por lo que warm-up previo produce reuso
    inmediato.
    """
    if not SDK_AVAILABLE or genai is None:
        logger.warning("⚠️ [GENAI CLIENT] SDK not available async; returning None")
        return None

    key = _client_key(vertexai, api_key, project, location, credentials)

    # Asegurar lock por clave. En un event loop single-thread la asignación es
    # atómica respecto a otras coroutines (no hay await entre check y set).
    if key not in _CLIENT_ASYNC_LOCKS:
        _CLIENT_ASYNC_LOCKS[key] = asyncio.Lock()
    lock = _CLIENT_ASYNC_LOCKS[key]

    # Fast path.
    client = _SHARED_CLIENTS.get(key)
    if client is not None:
        _CLIENT_REUSE_COUNTS[key] = _CLIENT_REUSE_COUNTS.get(key, 0) + 1
        _log_reuse(client, key)
        return client

    async with lock:
        client = _SHARED_CLIENTS.get(key)
        if client is not None:
            _CLIENT_REUSE_COUNTS[key] = _CLIENT_REUSE_COUNTS.get(key, 0) + 1
            _log_reuse(client, key)
            return client

        try:
            client = await asyncio.to_thread(
                _create_client_sync, vertexai, api_key, project, location, credentials
            )
            _SHARED_CLIENTS[key] = client
            _CLIENT_CREATION_TIMES[key] = time.monotonic()
            _CLIENT_REUSE_COUNTS[key] = 0
            _log_created(client, key)
            return client
        except Exception:
            logger.exception(f"❌ [GENAI CLIENT] Failed to create shared async client (key={key})")
            return None


# ---------------------------------------------------------------------------
# Hook de aislamiento para tests
# ---------------------------------------------------------------------------
def reset_shared_clients() -> None:
    """
    Limpia todos los clientes compartidos. EXCLUSIVO para el arnés de tests.
    No invocar en producción.
    """
    _SHARED_CLIENTS.clear()
    _CLIENT_CREATION_TIMES.clear()
    _CLIENT_REUSE_COUNTS.clear()
    _CLIENT_ASYNC_LOCKS.clear()
    _CLIENT_LOCKS.clear()
    logger.debug("[GENAI CLIENT] Shared clients reset (test-only)")


# ---------------------------------------------------------------------------
# Forense 429 PII-safe por construcción
# ---------------------------------------------------------------------------
# Whitelist explícita de campos extraíbles. Cualquier otro campo se descarta
# y solo se cuenta para evitar fugas de PII (prompts, nombres, teléfonos).
_ALLOWED_FORENSIC_FIELDS = frozenset(
    ["code", "status", "reason", "domain", "quota_metric", "quota_limit", "quota_id", "retry_delay"]
)


def _format_retry_delay(retry_delay: Any) -> Optional[float]:
    """Convierte google.protobuf.Duration a segundos."""
    if isinstance(retry_delay, dict):
        seconds = retry_delay.get("seconds") or 0
        nanos = retry_delay.get("nanos") or 0
        try:
            return float(seconds) + float(nanos) / 1e9
        except (TypeError, ValueError):
            return None
    return None


def _extract_details(details: Any, fields: Dict[str, Any]) -> None:
    """Extrae metadatos de la lista de google.rpc.Status.details."""
    if isinstance(details, dict):
        details = [details]
    if not isinstance(details, list):
        fields["unknown_keys"] = 1
        return

    for item in details:
        if not isinstance(item, dict):
            fields["unknown_keys"] += 1
            continue

        type_url = str(item.get("@type", ""))
        if "QuotaFailure" in type_url:
            violations = item.get("violations", [])
            if isinstance(violations, list) and violations:
                first = violations[0]
                if isinstance(first, dict):
                    fields["quota_metric"] = first.get("quotaMetric") or first.get("quota_metric")
                    fields["quota_limit"] = (
                        first.get("quotaLimit")
                        or first.get("quota_limit")
                        or first.get("limit")
                    )
                    fields["quota_id"] = first.get("quotaId") or first.get("quota_id")
        elif "RetryInfo" in type_url:
            fields["retry_delay"] = _format_retry_delay(item.get("retryDelay"))
        elif "ErrorInfo" in type_url:
            fields["reason"] = item.get("reason")
            fields["domain"] = item.get("domain")
        else:
            # Campo desconocido: contar, nunca emitir nombre ni valor.
            fields["unknown_keys"] += 1


def format_gemini_error_structured(e: Exception) -> str:
    """
    Serializa el cuerpo de un error HTTP de Gemini en UNA línea, sin PII.

    Whitelist de campos extraíbles: code, status, reason, domain, quota_metric,
    quota_limit, quota_id, retry_delay. NUNCA se emiten e.message, details[*].message,
    request_payload ni valores de campos desconocidos. Si todo falla, retorna un
    fallback no-vacío con body_redacted=True.
    """
    def _fallback() -> str:
        code = getattr(e, "code", None)
        status = getattr(e, "status", None)
        return (
            f"code={code!r} status={status!r} type={type(e).__name__} "
            "body_redacted=True"
        )

    try:
        fields: Dict[str, Any] = {
            "code": getattr(e, "code", None),
            "status": getattr(e, "status", None),
            "reason": None,
            "domain": None,
            "quota_metric": None,
            "quota_limit": None,
            "quota_id": None,
            "retry_delay": None,
            "unknown_keys": 0,
        }

        details = getattr(e, "details", None)
        if details is not None:
            _extract_details(details, fields)

        # Emitir solo campos permitidos con valor no nulo. Si no hay ningún campo
        # permitido, fallback completo para evitar filtrar metadatos desconocidos.
        allowed_parts = [
            f"{k}={v!r}"
            for k, v in fields.items()
            if v is not None and k in _ALLOWED_FORENSIC_FIELDS
        ]
        unknown_count = fields.get("unknown_keys", 0)

        if allowed_parts:
            if unknown_count > 0:
                allowed_parts.append(f"unknown_keys={unknown_count}")
            return " ".join(allowed_parts)
        return _fallback()
    except Exception:
        # ZSF: nunca propagar; siempre retornar fallback no-vacío.
        return _fallback()
