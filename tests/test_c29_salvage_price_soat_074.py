"""
BOT-BUILD-C29-075-RF2 — C5-061 (💰 formateado con $ en rutas deterministas
salvage/fallback) + C5-065 (ancla SOAT idempotente, sin duplicado visible).

Pines:
  P1: helper _canonical_top_price convierte price int en string con $ + ancla
  P2: helper recompute primero (price int > 0) gana sobre formatted stale
  P3: _ensure_soat_anchor es idempotente ante variantes de casing del modelo
  P3b: mencion SOAT no-canónico evita append de ancla canónica
  P4: append de ancla SOAT una sola vez + idempotencia en segunda pasada
  P5: _build_pcc_fallback con item int sobrevive a PRICE-LOCK T0/T1
  P6: antidrift — ninguna cadena .get('price') or ...formatted_price inline
       en los 9 call sites de fallback/salvage (C5-077 FUERA del universo)
  P7: guard price > 0 evita precio fabricado desde price: 0
"""

import ast
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.ai_brain import CerebroIA
from app.services.catalog_service import PRICE_PACKAGE_ANCHOR
from app.routers.whatsapp import _coerce_caption_price_lock


# -----------------------------------------------------------------------------
# R1 / C5-061 — SSOT de precio formateado
# -----------------------------------------------------------------------------

def test_p1_helper_int_price_returns_formatted_with_anchor():
    """
    Price int puro → build_commercial_price con $ y ancla SOAT canónica.
    """
    with patch("app.services.config_service.config_service.get_registration_cost", return_value=0):
        price = CerebroIA._canonical_top_price(
            {"price": 5_000_000, "cc": 125, "category": "moto"}
        )

    assert "$" in price, f"falta $: {price!r}"
    assert "5.000.000" in price, f"monto mal formateado: {price!r}"
    assert PRICE_PACKAGE_ANCHOR in price, f"falta ancla: {price!r}"


def test_p2_helper_recompute_wins_over_stale_formatted():
    """
    R1': el recompute desde price int (>0) gana sobre formatted_price stale
    o sin ancla; esto cierra la trampa de mapped_items con formatted legacy.
    """
    stale_formatted = "$9.999.999"  # sin ancla, distinto al recompute
    with patch("app.services.config_service.config_service.get_registration_cost", return_value=0):
        price = CerebroIA._canonical_top_price(
            {"price": 6_000_000, "formatted_price": stale_formatted}
        )

    assert stale_formatted not in price, f"formatted stale gano: {price!r}"
    assert "$" in price, f"falta $: {price!r}"
    assert "6.000.000" in price, f"monto mal formateado: {price!r}"
    assert PRICE_PACKAGE_ANCHOR in price, f"falta ancla: {price!r}"


# -----------------------------------------------------------------------------
# R2 / C5-065 — Idempotencia del ancla SOAT
# -----------------------------------------------------------------------------

def test_p3_soat_anchor_idempotent_variant_casing():
    """
    El modelo ya emitio una variante con mayuscula; no se duplica.
    """
    text = "La moto esta disponible por $6.000.000 (Incluye SOAT y Matricula). ¿Te interesa?"
    out = CerebroIA._ensure_soat_anchor(text)
    assert out == text
    assert out.count("SOAT") == text.count("SOAT")


def test_p3b_soat_mentioned_elsewhere_no_append():
    """
    SOAT mencionado fuera de una ancla canónica → no appendear ancla.
    """
    text = "El SOAT es aparte. Precio: $5.000.000"
    out = CerebroIA._ensure_soat_anchor(text)
    assert out == text
    assert PRICE_PACKAGE_ANCHOR not in out


def test_p4_soat_anchor_appends_once_and_is_idempotent():
    """
    Sin ancla ni mencion SOAT: append una sola vez; segunda pasada no-op.
    """
    text = "Precio: $5.000.000"
    out1 = CerebroIA._ensure_soat_anchor(text)
    assert PRICE_PACKAGE_ANCHOR in out1
    assert out1.count(PRICE_PACKAGE_ANCHOR) == 1

    out2 = CerebroIA._ensure_soat_anchor(out1)
    assert out2 == out1


# -----------------------------------------------------------------------------
# Impacto cruzado PRICE-LOCK (whatsapp.py)
# -----------------------------------------------------------------------------

def test_p5_fallback_int_price_survives_price_lock():
    """
    End-to-end: item con price int → helper formatea → _build_pcc_fallback
    genera caption >4L → _coerce_caption_price_lock preserva $ (T1 merge).
    """
    with patch("app.services.config_service.config_service.get_registration_cost", return_value=0):
        item = {
            "name": "VICTORY MRX 125",
            "price": 5_000_000,
            "cc": 125,
            "category": "moto",
        }
        brain = CerebroIA(catalog_service=None)
        top_price = CerebroIA._canonical_top_price(item)
        caption = brain._build_pcc_fallback(
            "Hola, quisiera una moto doble proposito",
            [],
            top_name="VICTORY MRX 125",
            top_image="https://example.com/mrx125.jpg",
            top_price=top_price,
        )
        out = _coerce_caption_price_lock(caption, turn_id="P5")

    assert re.search(r"\$5[\.,]?000[\.,]?000", out), f"precio perdido: {out!r}"
    assert "Ficha Tecnica:" in out
    assert len(out.splitlines()) <= 4, f"excede 4 lineas: {out!r}"
    assert len(out) <= 350, f"excede 350 chars: {len(out)}"


# -----------------------------------------------------------------------------
# Antidrift — R1 mecanico en los 9 call sites
# -----------------------------------------------------------------------------


def test_p7_helper_zero_price_returns_empty():
    """
    R1'': price numerico 0 (o negativo) sin formatted debe retornar '' para
    evitar fabricar un precio = solo costo de registro en el fallback.
    """
    assert CerebroIA._canonical_top_price({"price": 0}) == ""
    assert CerebroIA._canonical_top_price({"price": -1}) == ""
    # Con formatted presente se respeta el fallback aunque price sea 0
    assert CerebroIA._canonical_top_price({"price": 0, "formatted_price": "$5.000.000"}) == "$5.000.000"

def test_p6_no_inline_price_getter_chains_in_fallback_sites():
    """
    Las 9 rutas deterministas salvage/fallback deben usar _canonical_top_price;
    el unico patron .get('price') or ...formatted_price restante es C5-077
    (builder de contexto LLM), declarado fuera de scope.
    """
    src_path = Path(__file__).resolve().parents[1] / "app/services/ai_brain.py"
    src = src_path.read_text(encoding="utf-8")
    tree = ast.parse(src)

    target_names = {"_build_pcc_fallback", "_build_canonical_paso1_caption"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = None
        if isinstance(node.func, ast.Name) and node.func.id in target_names:
            name = node.func.id
        elif isinstance(node.func, ast.Attribute) and node.func.attr in target_names:
            name = node.func.attr
        if name is None:
            continue

        kw = next((k for k in node.keywords if k.arg == "top_price"), None)
        assert kw is not None, f"{name} no recibe top_price"
        segment = ast.get_source_segment(src, kw.value) or ""
        assert ".get(\"price\")" not in segment and ".get('price')" not in segment, (
            f"{name} top_price aun usa cadena inline: {segment!r}"
        )

    pattern = re.compile(
        r'''[^\.\s]+\.get\(['"]price['"]\)\s+or\s+[^\.\s]+\.get\(['"]formatted_price['"]\)\s+or\s+[^\.\s]+\.get\(['"]precio['"]\)'''
    )
    matches = list(pattern.finditer(src))
    assert len(matches) == 1, (
        f"Se esperaba exactamente 1 cadena inline (C5-077), encontradas {len(matches)}"
    )
