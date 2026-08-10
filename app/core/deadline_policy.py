"""
[BOT-BUILD-DEADLINE-BUDGET-023] Política de deadline dinámico frío/caliente.

Provee 'effective_gemini_timeout_s()' que retorna 30s durante la ventana
fría de la instancia de Cloud Run y 18s una vez la instancia está caliente.

GUARD DE HABILITACIÓN: la política frío/caliente solo se activa si la
variable de entorno GEMINI_COLD_CALL_TIMEOUT_S está explícitamente seteada.
Sin ella, effective_gemini_timeout_s() retorna GEMINI_CALL_TIMEOUT_S del
módulo ai_brain (comportamiento heredado, pins FIX-2A intactos sin edición).

El timestamp de arranque se captura aquí al import (fallback) y se afina
con set_instance_started_monotonic() desde el lifespan de main.py.

Variables de entorno:
  GEMINI_COLD_CALL_TIMEOUT_S  — timeout por llamada en ventana fría  (ausente → política desactivada)
  COLD_WINDOW_S               — duración de la ventana fría en segundos (default 120s)
"""

import logging
import os
import time

logger = logging.getLogger(__name__)

_instance_started_monotonic: float = time.monotonic()

COLD_WINDOW_S = float(os.getenv("COLD_WINDOW_S", "120.0"))
# NOTA: el valor de GEMINI_COLD_CALL_TIMEOUT_S se congela al import del módulo.
# La HABILITACIÓN de la política (_deadline_policy_enabled) se evalúa dinámicamente
# por llamada (soporta patch.dict en tests). Esta asimetría es inocua en producción
# (el env está fijado antes de iniciar el proceso) y los tests que necesitan cambiar
# el valor parchean la constante del módulo directamente.
GEMINI_COLD_CALL_TIMEOUT_S = float(os.getenv("GEMINI_COLD_CALL_TIMEOUT_S", "30.0"))


def _deadline_policy_enabled() -> bool:
    """La política frío/caliente se activa solo si GEMINI_COLD_CALL_TIMEOUT_S
    está explícitamente en el entorno.  Dinámica (no constante de módulo) para
    que patch.dict(os.environ, ...) funcione en tests sin reload."""
    return "GEMINI_COLD_CALL_TIMEOUT_S" in os.environ


def set_instance_started_monotonic(t: float) -> None:
    """
    Ajusta el timestamp de arranque de la instancia.
    Se invoca desde el lifespan de main.py durante el arranque de la
    aplicación para capturar el momento en que el tráfico puede comenzar
    a llegar (el puerto ya está vinculado por el ASGI server).
    """
    global _instance_started_monotonic
    _instance_started_monotonic = t
    logger.info(
        f"❄️→🌡️ [DEADLINE-POLICY] instance_started_monotonic ajustado a "
        f"{_instance_started_monotonic:.1f} (cold_window={COLD_WINDOW_S}s)"
    )


def is_cold() -> bool:
    """True si la instancia está dentro de su ventana fría."""
    return (time.monotonic() - _instance_started_monotonic) < COLD_WINDOW_S


def effective_gemini_timeout_s() -> float:
    """
    Timeout efectivo por llamada Gemini según estado térmico de la instancia.

    GUARD: si GEMINI_COLD_CALL_TIMEOUT_S NO está en el entorno, la política
    está desactivada y se retorna la constante GEMINI_CALL_TIMEOUT_S del
    módulo ai_brain (comportamiento heredado, compatible con todos los pins).

    Con la política activa:
      Frío → GEMINI_COLD_CALL_TIMEOUT_S (default 30s).
      Caliente → GEMINI_CALL_TIMEOUT_S del módulo ai_brain (18s, parcheable en tests).
    """
    if not _deadline_policy_enabled():
        from app.services.ai_brain import GEMINI_CALL_TIMEOUT_S
        return GEMINI_CALL_TIMEOUT_S

    if is_cold():
        timeout = GEMINI_COLD_CALL_TIMEOUT_S
        logger.debug(f"❄️ [DEADLINE-POLICY] Cold timeout: {timeout}s")
        return timeout
    # Lazy import para evitar circular dependency.
    from app.services.ai_brain import GEMINI_CALL_TIMEOUT_S
    return GEMINI_CALL_TIMEOUT_S
