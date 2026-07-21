import logging
import os
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)

# Try to import OpenTelemetry components
try:
    from opentelemetry import trace
    from langfuse._client.attributes import LangfuseOtelSpanAttributes
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    logger.warning("⚠️ [LANGFUSE] OpenTelemetry or Langfuse SDK components not found. Telemetry updates will be disabled.")

# --- LANGFUSE CREDENTIALS GATE [BOT-BUILD-DEUDA-OTEL-03-06] ---
# WHY: El SDK de Langfuse v4 auto-inicializa un exportador OTLP en background al
# importarse. Sin credenciales físicas (LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY),
# ese exportador reintenta en bucle y genera ruido de exportación en los logs.
# Este gate evalúa las credenciales ANTES del import del SDK y, si faltan, desactiva
# la exportación vía el flag oficial LANGFUSE_TRACING_ENABLED=false.
# CONTRATO BOT-QA-GATE-110: el decorador `observe` real NUNCA se degrada a shim;
# solo se silencia la exportación. Fail-safe: ante cualquier error de evaluación,
# la telemetría queda desactivada (no bloqueante).
def _resolve_langfuse_credentials():
    """Resolve Langfuse credentials: settings first, os.getenv as fallback."""
    try:
        from app.core.config import settings
        return settings.langfuse_public_key, settings.langfuse_secret_key
    except Exception:
        logger.exception("🔍 [LANGFUSE_GATE] Failed to resolve credentials from settings; falling back to os.getenv.")
        return os.getenv("LANGFUSE_PUBLIC_KEY"), os.getenv("LANGFUSE_SECRET_KEY")

_lf_public_key, _lf_secret_key = _resolve_langfuse_credentials()
LANGFUSE_ENABLED = bool(_lf_public_key and _lf_secret_key)

if not LANGFUSE_ENABLED:
    os.environ["LANGFUSE_TRACING_ENABLED"] = "false"
    logger.warning("⚠️ [LANGFUSE_GATE] LANGFUSE_PUBLIC_KEY/SECRET_KEY missing. Telemetry export silenced (real @observe decorator preserved).")

# Try to import the real observe decorator
try:
    from langfuse import observe
    LANGFUSE_AVAILABLE = True
    logger.info("🔭 [LANGFUSE] Observability SDK successfully initialized.")
except Exception as e:
    LANGFUSE_AVAILABLE = False
    logger.warning(f"⚠️ [LANGFUSE] Observability SDK unavailable: {e}. Loading fallback no-op decorators.")
    
    def observe(*args, **kwargs):
        def decorator(fn):
            return fn
        if args and callable(args[0]):
            return args[0]
        return decorator

def _flatten_and_serialize(metadata: Any, prefix: str, span: Any):
    """
    Safely flattens nested dictionaries/lists and serializes values to primitive types
    supported by OpenTelemetry. Omits empty structures or Nones.
    """
    if metadata is None:
        return

    if isinstance(metadata, dict):
        for k, v in metadata.items():
            key = f"{prefix}.{k}"
            if v is None:
                continue
            if isinstance(v, (dict, list)):
                if not v: # Skip empty structures
                    continue
                _flatten_and_serialize(v, key, span)
            elif isinstance(v, (str, int, float, bool)):
                span.set_attribute(key, v)
            else:
                span.set_attribute(key, str(v)[:200])
    elif isinstance(metadata, list):
        if not metadata:
            return
        # OpenTelemetry only supports homogeneous primitive lists
        first_type = type(metadata[0])
        if first_type in (str, int, float, bool) and all(isinstance(x, first_type) for x in metadata):
            span.set_attribute(prefix, metadata)
        else:
            span.set_attribute(prefix, str([str(x)[:200] for x in metadata]))
    else:
        if isinstance(metadata, (str, int, float, bool)):
            span.set_attribute(prefix, metadata)
        else:
            span.set_attribute(prefix, str(metadata)[:200])

class _LangfuseContextAdapter:
    """
    Adapter class for langfuse_context in v4 SDK.
    Translates legacy updates into direct OpenTelemetry span attribute modifications.
    """
    def update_current_trace(self, user_id: Optional[str] = None, session_id: Optional[str] = None, tags: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None):
        if not OTEL_AVAILABLE:
            return
        try:
            span = trace.get_current_span()
            if span is not None and span.is_recording():
                if user_id is not None:
                    span.set_attribute(LangfuseOtelSpanAttributes.TRACE_USER_ID, str(user_id)[:200])
                if session_id is not None:
                    span.set_attribute(LangfuseOtelSpanAttributes.TRACE_SESSION_ID, str(session_id)[:200])
                if tags is not None and isinstance(tags, list) and tags:
                    span.set_attribute(LangfuseOtelSpanAttributes.TRACE_TAGS, [str(t)[:100] for t in tags])
                if metadata is not None:
                    _flatten_and_serialize(metadata, LangfuseOtelSpanAttributes.TRACE_METADATA, span)
        except Exception as e:
            logger.warning(f"⚠️ [LANGFUSE_ADAPTER] Failed to update current trace: {e}")

    def update_current_observation(self, metadata: Optional[Dict[str, Any]] = None, **kwargs):
        if not OTEL_AVAILABLE:
            return
        try:
            span = trace.get_current_span()
            if span is not None and span.is_recording():
                if metadata is not None:
                    _flatten_and_serialize(metadata, LangfuseOtelSpanAttributes.OBSERVATION_METADATA, span)
                if kwargs:
                    _flatten_and_serialize(kwargs, "langfuse.observation", span)
        except Exception as e:
            logger.warning(f"⚠️ [LANGFUSE_ADAPTER] Failed to update current observation: {e}")

    def update_current_generation(self, metadata: Optional[Dict[str, Any]] = None, **kwargs):
        if not OTEL_AVAILABLE:
            return
        try:
            span = trace.get_current_span()
            if span is not None and span.is_recording():
                if metadata is not None:
                    _flatten_and_serialize(metadata, LangfuseOtelSpanAttributes.OBSERVATION_METADATA, span)
                if kwargs:
                    _flatten_and_serialize(kwargs, "langfuse.observation.generation", span)
        except Exception as e:
            logger.warning(f"⚠️ [LANGFUSE_ADAPTER] Failed to update current generation: {e}")

langfuse_context = _LangfuseContextAdapter()

# Dynamically inject langfuse.decorators mock module to satisfy backward compatibility
# and prevent test suite mock patching failures.
import sys
import types as py_types
decorators_mock = py_types.ModuleType("langfuse.decorators")
decorators_mock.observe = observe
decorators_mock.langfuse_context = langfuse_context
sys.modules["langfuse.decorators"] = decorators_mock

