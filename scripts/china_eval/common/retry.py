"""Retry policy para BOT-BUILD-CHINA-EVAL-090."""
from __future__ import annotations

import time
from typing import Callable, TypeVar

import httpx

T = TypeVar("T")

RETRIABLE_NETWORK_ERRORS = (httpx.ConnectError, httpx.ReadTimeout, httpx.NetworkError)
MAX_RETRIES = 3
BASE_DELAY = 1.0


def retry_network(
    fn: Callable[[], T],
    *,
    max_retries: int = MAX_RETRIES,
    base_delay: float = BASE_DELAY,
) -> T:
    """Ejecuta fn con retry ante errores de red.

    No retry ante 4xx/5xx HTTP lógicos (los clientes deben levantarlos como excepción
    no perteneciente a RETRIABLE_NETWORK_ERRORS).
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except RETRIABLE_NETWORK_ERRORS as exc:
            last_exc = exc
            if attempt == max_retries:
                break
            delay = base_delay * (2 ** attempt)
            time.sleep(delay)
    raise last_exc from None
