"""
tests/factories.py — Fábrica de Mocking Dinámico en Memoria [Incidente H-A · HA-3]

WHY: El arnés histórico dependía de (a) literales hardcodeados de precio/SMLV/URLs
dispersos en ~20 archivos y (b) el bypass `is_test_mode` del STARTUP-GUARD para no
satisfacer el mínimo de catálogo. Esta fábrica genera catálogos/prospectos DINÁMICOS
en memoria con seed fija (reproducibilidad bit-exacta en CI), eliminando los
literales del arnés y habilitando la erradicación total del bypass (wave 04-03a).

Contratos:
- DETERMINISTA: misma seed → mismo catálogo, siempre (CI estable, diffs limpios).
- CERO literales de precio/SMLV/URLs fijas en los tests consumidores: todo valor
  económico se REFERENCIA desde el ítem generado (`items[0]["price"]`).
- FALLO EXPLÍCITO (zero-silent-failures): parámetros inválidos o servicio sin la
  superficie esperada → excepción inmediata, jamás fallback silencioso.
"""
import random
from typing import Any, Dict, List, Tuple

# SMLV vigente referenciado por la matriz de prompts (app/core/prompts.py).
# Fuente ÚNICA de verdad del arnés: los tests lo REFERENCIAN, nunca lo reescriben.
TEST_SMLV: int = 1_705_905

FACTORY_SEED: int = 2026

_CC_WHITELIST: List[int] = [100, 125, 150, 160, 200, 500]
_CATEGORIES: List[str] = ["urban", "sport", "scooter"]
_BRANDS: List[str] = ["AKT", "TVS", "BAJAJ", "YAMAHA", "HONDA", "SUZUKI"]


def make_catalog_item(idx: int, rng: random.Random) -> Dict[str, Any]:
    """Genera un ítem de catálogo sintético, único y completo (sin nulos).

    Precio dinámico: rango realista COP [3.000.000, 12.000.000], múltiplo de 10.000,
    derivado de `rng` (determinista bajo seed fija).
    """
    if not isinstance(idx, int) or idx < 0:
        raise ValueError(f"idx debe ser int >= 0, recibido: {idx!r}")
    if not isinstance(rng, random.Random):
        raise TypeError(f"rng debe ser random.Random, recibido: {type(rng).__name__}")

    brand = _BRANDS[idx % len(_BRANDS)]
    cc = _CC_WHITELIST[idx % len(_CC_WHITELIST)]
    category = _CATEGORIES[idx % len(_CATEGORIES)]
    price = rng.randrange(300, 1200) * 10_000
    return {
        "id": f"factory_moto_{idx}",
        "name": f"{brand} FACTORY {cc} MODEL {idx}",
        "price": price,
        "cc": cc,
        "category": category,
        # [BOT-PLAN-HARDENING-EGRESS-FUNNEL-001] Host canónico (URL-Lock whitelist):
        # el SSOT de imágenes vive en Firebase Storage; un host fixture no canónico
        # sería extirpado por el guard de egreso (default-deny).
        "image_url": f"https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/motos%2Ffactory_moto_{idx}.webp?alt=media",
        "link": f"https://factory.test/motos/factory_moto_{idx}",
        "description": f"Moto sintética {idx} generada por tests/factories.py (seed fija).",
        "summary": f"Ficha sintética {idx}: {cc}cc, categoría {category}.",
    }


def make_catalog(n: int = 60, seed: int = FACTORY_SEED) -> List[Dict[str, Any]]:
    """Genera un catálogo de `n` ítems únicos. Default 60 = mínimo del STARTUP-GUARD."""
    if not isinstance(n, int) or n <= 0:
        raise ValueError(f"n debe ser int > 0, recibido: {n!r}")
    rng = random.Random(seed)
    return [make_catalog_item(i, rng) for i in range(n)]


def make_domain_item(idx: int = 0, seed: int = FACTORY_SEED, **overrides: Any) -> Dict[str, Any]:
    """Ítem de fábrica con overrides de dominio (p. ej. search_tokens para fuzzy).

    WHY: tests como test_audio_regression necesitan contenido semántico específico
    (marca/modelo/tokens) sin reintroducir literales de precio — el precio queda
    generado por la fábrica salvo override explícito.
    """
    item = make_catalog_item(idx, random.Random(seed))
    item.update(overrides)
    return item


def make_prospect(**overrides: Any) -> Dict[str, Any]:
    """Prospecto CRM dinámico (alineado con el fixture mock_prospect_data de conftest)."""
    base: Dict[str, Any] = {
        "exists": True,
        "nombre": "Prospecto Factory",
        "moto_interest": make_domain_item()["name"],
        "ciudad": "Bogotá",
        "forma_pago": "Crédito",
    }
    base.update(overrides)
    return base


def format_cop(price: int) -> str:
    """Formatea un precio COP canónico con separador de miles '.' (p. ej. $6.000.000).

    WHY: las respuestas mockeadas del cerebro deben citar el precio GENERADO del
    ítem, preservando la consistencia PCC sin literales.
    """
    if not isinstance(price, int) or price <= 0:
        raise ValueError(f"price debe ser int > 0, recibido: {price!r}")
    return f"${price:,}".replace(",", ".")


def install_dynamic_catalog(n: int = 60, seed: int = FACTORY_SEED) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Inyecta make_catalog(n) en el singleton real catalog_service (`_items`) y
    limpia su caché. Retorna (items, token) para restauración explícita en teardown
    vía restore_catalog(token).

    Falla explícitamente si catalog_service no expone la superficie esperada
    (zero-silent-failures: jamás degradar a un mock parcial silencioso).
    """
    from app.services.catalog_service import catalog_service

    if not hasattr(catalog_service, "_items"):
        raise AttributeError(
            "catalog_service no expone '_items' — la inyección dinámica no es posible. "
            "Verificar versión del servicio antes de migrar el test."
        )
    items = make_catalog(n, seed)
    token: Dict[str, Any] = {"previous_items": catalog_service._items}
    catalog_service._items = items
    cache = getattr(catalog_service, "_cache_service", None)
    if cache is not None and hasattr(cache, "clear"):
        cache.clear()
    return items, token


def restore_catalog(token: Dict[str, Any]) -> None:
    """Restaura catalog_service._items al valor previo capturado por install_dynamic_catalog."""
    if not isinstance(token, dict) or "previous_items" not in token:
        raise ValueError(f"token inválido para restore_catalog: {token!r}")
    from app.services.catalog_service import catalog_service

    catalog_service._items = token["previous_items"]
    cache = getattr(catalog_service, "_cache_service", None)
    if cache is not None and hasattr(cache, "clear"):
        cache.clear()
