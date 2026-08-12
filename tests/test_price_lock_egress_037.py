"""
BOT-BUILD-PRICE-LOCK-037 — Backstop price-aware del pipeline de egreso.

Valida que el caption del PASO 1 con crédito preserve el precio ($) DESPUÉS
de la coerción de egreso (4 líneas / 350 chars), cerrando la violación visible
de la Directiva #3 Visual-Lock sin relajar el límite ni degradar flujos
pineados donde el precio ya sobrevive (salvage 028, fallback 021 post-Fix-3).
"""

import logging
import re
import types

import pytest
from unittest.mock import AsyncMock

from app.services import egress_guard_service as egress_guard
from app.routers.whatsapp import (
    _coerce_caption_price_lock,
    _pipeline_egress,
    _send_whatsapp_image,
)


PHONE_E164 = "+573192564289"
PHONE_NUMBER_ID = "123456789012345"
IMG_URL = (
    "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos.appspot.com/"
    "o/products%2Fraider125.png?alt=media"
)


def _pipeline_replica(text: str):
    """Réplica exacta del pipeline unificado previo a _send_whatsapp_image."""
    txt, _ = egress_guard.enforce_urls(text)
    md_pattern = r"!?\[[\s\S]*?\]\s*\((https?://[^\s\)]+)\)"
    images = re.findall(md_pattern, txt)
    caption = re.sub(md_pattern, "", txt).strip()
    return caption, images


# ──────────────── P1-M1-LINEAS ────────────────

def test_p1_m1_lineas_happy_path_credito():
    """
    Escenario A (bug vivo): happy path PASO 1 con mención crediticia.
    El blurb de crédito empuja 💰 Precio fuera de la ventana de 4 líneas.
    El backstop debe fusionarlo con Ficha y conservar el $, la pregunta y la
    imagen extraída, todo dentro del contrato 4L/350c.
    """
    text = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        "¡Claro que tenemos crédito! Te presento la ⭐ TOP RESULT:\n"
        "Ficha Tecnica: TVS RAIDER 125\n"
        "💰 Precio: $6.790.000 (incluye SOAT, Matrícula, y tramites)\n"
        f"![TVS RAIDER 125]({IMG_URL})\n"
        "¿Con quién tengo el gusto?"
    )
    caption, images = _pipeline_replica(text)
    assert images == [IMG_URL]

    out = _coerce_caption_price_lock(caption, turn_id="P1")

    assert len(out.splitlines()) <= 4, f"Excede 4 líneas: {out!r}"
    assert len(out) <= 350, f"Excede 350 chars: {len(out)}"
    assert "Ficha Tecnica: TVS RAIDER 125" in out
    assert "💰 Precio: $6.790.000" in out
    assert re.search(r"\$\d+", out)
    assert "¿Con quién tengo el gusto?" in out
    assert IMG_URL not in out  # la imagen viaja como payload, no markdown


# ──────────────── P2-M2-CHARS ────────────────

def test_p2_m2_chars_ficha_larga():
    """
    Escenario B2: Ficha Tecnica con summary extenso del catálogo (> 350 chars
    totales). El corte por caracteres (Fase 2) decapita el precio. El backstop
    debe reubicarlo al inicio de la línea fusionada (T2) para que sobreviva.
    """
    ficha_larga = (
        "Ficha Tecnica: TVS RAIDER 125 — Motor 124.8 cm3 monocilindrico 4 tiempos, "
        "potencia 11.38 hp @ 7500 rpm, torque 11.2 Nm @ 6000 rpm, frenos de disco "
        "con CBS, suspension invertida, tanque 10 L, consumo aprox. 55 km/l, "
        "garantia extendida de fabrica."
    )
    text = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        f"{ficha_larga}\n"
        "💰 Precio: $6.790.000 (incluye SOAT, Matrícula, y tramites)\n"
        f"![TVS RAIDER 125]({IMG_URL})\n"
        "¿Con quién tengo el gusto?"
    )
    caption, _ = _pipeline_replica(text)
    assert len(caption) > 350, "precondición: caption debe exceder 350 chars"

    out = _coerce_caption_price_lock(caption, turn_id="P2")

    assert len(out.splitlines()) <= 4, f"Excede 4 líneas: {out!r}"
    assert len(out) <= 350, f"Excede 350 chars: {len(out)}"
    assert re.search(r"\$\d+", out), f"precio decapitado: {out!r}"
    assert "¿Con quién tengo el gusto?" in out


# ──────────────── P3/P4-T0-BYTE-IDENTICO ────────────────

def test_p3_t0_byte_identico_salvage_028():
    """
    El salvage canónico 028 ya entra en 4 líneas post-extracción; el wrapper
    debe colapsar a T0 y ser byte-idéntico a enforce_length directo.
    """
    caption = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos.\n"
        "Ficha Tecnica: Victory MRX 125\n"
        "💰 Precio: $5.000.000\n"
        f"![Victory MRX 125]({IMG_URL})\n"
        "¿Con quién tengo el gusto?"
    )
    out = _coerce_caption_price_lock(caption, turn_id="P3")
    expected = egress_guard.enforce_length(caption)
    assert out == expected


def test_p4_t0_byte_identico_fallback_021():
    """
    El fallback 021 post-Fix-3 (joiner \n) también sobrevive sin backstop;
    el wrapper debe ser byte-idéntico.
    """
    caption = (
        "¡Qué pena! Tuve un inconveniente procesando esa búsqueda. "
        "¿Me confirmas la moto que tienes en mente para buscarla mejor? 😅\n"
        "Ficha Tecnica: VICTORY MRX 125\n"
        "💰 Precio: $9.969.000 (incluye SOAT, Matrícula, y tramites)\n"
        "⭐ Recomendación TOP: VICTORY MRX 125"
    )
    out = _coerce_caption_price_lock(caption, turn_id="P4")
    expected = egress_guard.enforce_length(caption)
    assert out == expected


# ──────────────── P5-T0-SIN-PRECIO ────────────────

def test_p5_t0_sin_precio_byte_identico():
    """Sin $ en el caption el wrapper no debe alterar nada."""
    caption = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        "¿Con quién tengo el gusto?"
    )
    out = _coerce_caption_price_lock(caption, turn_id="P5")
    assert out == egress_guard.enforce_length(caption)


# ──────────────── P6-INTEGRACION-SEND-IMAGE (Z3) ────────────────

@pytest.mark.asyncio
async def test_p6_integration_send_image_z3():
    """
    _send_whatsapp_image es el chokepoint único de captions de imagen. Un
    caption M1 debe llegar a Meta con el precio preservado tras la coerción.
    """
    caption = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        "¡Claro que tenemos crédito! Te presento la ⭐ TOP RESULT:\n"
        "Ficha Tecnica: TVS RAIDER 125\n"
        "💰 Precio: $6.790.000 (incluye SOAT, Matrícula, y tramites)\n"
        "¿Con quién tengo el gusto?"
    )
    meta_sender = AsyncMock()
    await _send_whatsapp_image(
        PHONE_E164,
        IMG_URL,
        caption=caption,
        phone_number_id=PHONE_NUMBER_ID,
        meta_sender=meta_sender,
    )
    assert meta_sender.send_image_message.called
    args, kwargs = meta_sender.send_image_message.call_args
    _to, _image_url, sent_caption = args
    assert kwargs.get("phone_number_id") == PHONE_NUMBER_ID
    assert re.search(r"\$\d+", sent_caption), f"caption enviado sin precio: {sent_caption!r}"
    assert len(sent_caption.splitlines()) <= 4
    assert len(sent_caption) <= 350


# ──────────────── P7-NEEDS-INJECT (Z2 + doble coerción) ────────────────

@pytest.mark.asyncio
async def test_p7_needs_inject_z2_double_coercion(monkeypatch):
    """
    Rama needs_inject (:2411) coacciona ANTES de llamar _send_whatsapp_image.
    El wrapper debe proteger el precio en :2411 para que la segunda coerción
    en :2848 (T0) lo reciba ya sano.
    """
    import app.routers.whatsapp as wa

    captured = {}

    async def fake_send_image(
        to_phone, image_url, caption, phone_number_id=None, *, meta_sender=None, turn_id=None
    ):
        captured["caption"] = caption
        captured["turn_id"] = turn_id
        return True

    monkeypatch.setattr(wa, "_send_whatsapp_image", fake_send_image)
    monkeypatch.setattr(
        wa, "memory_service_module", types.SimpleNamespace(memory_service=None)
    )

    response_text = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        "¡Claro que tenemos crédito! Te presento la ⭐ TOP RESULT:\n"
        "Ficha Tecnica: TVS RAIDER 125\n"
        "💰 Precio: $6.790.000 (incluye SOAT, Matrícula, y tramites)\n"
        "¿Con quién tengo el gusto?"  # sin Markdown image -> trigger missing_or_stripped
    )
    prospect_data = {
        "_catalog_top_name": "TVS RAIDER 125",
        "_catalog_top_image": IMG_URL,
    }

    await wa._pipeline_egress(
        response_text,
        user_phone=PHONE_E164,
        phone_number_id=PHONE_NUMBER_ID,
        prospect_data=prospect_data,
        catalog=None,
        trace_id="P7",
    )

    assert "caption" in captured
    sent_caption = captured["caption"]
    assert captured.get("turn_id") == "P7", "turn_id debe propagarse desde _pipeline_egress a Z2"
    assert re.search(r"\$\d+", sent_caption), f"caption Z2 sin precio: {sent_caption!r}"
    assert len(sent_caption.splitlines()) <= 4
    assert len(sent_caption) <= 350
    assert "¿Con quién tengo el gusto?" in sent_caption


# ──────────────── P8-T3-RESIDUAL ────────────────

def test_p8_t3_residual_logs_forensic(caplog):
    """
    Si hay $ pero no hay anclas Ficha/💰 para compactar, el helper cae a T3:
    conserva el comportamiento actual y deja log forense 🚨 [PRICE-LOCK].
    """
    caption = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        "Línea de contexto adicional número dos\n"
        "Línea de contexto adicional número tres\n"
        "$6.790.000 es el precio de la moto\n"
        "¿Con quién tengo el gusto?"
    )
    with caplog.at_level(logging.WARNING):
        out = _coerce_caption_price_lock(caption, turn_id="P8")

    assert out == egress_guard.enforce_length(caption)
    assert "🚨 [PRICE-LOCK]" in caplog.text
    assert "residual" in caplog.text


# ──────────────── P9-TURN-ID-LOG (H2) ────────────────

@pytest.mark.asyncio
async def test_p9_turn_id_propagation_to_price_lock_log(caplog):
    """
    H2: _send_whatsapp_image acepta turn_id y lo propaga al log 🛡️ [PRICE-LOCK]
    cuando dispara T1/T2/T3.
    """
    caption = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        "¡Claro que tenemos crédito! Te presento la ⭐ TOP RESULT:\n"
        "Ficha Tecnica: TVS RAIDER 125\n"
        "💰 Precio: $6.790.000 (incluye SOAT, Matrícula, y tramites)\n"
        "¿Con quién tengo el gusto?"
    )
    meta_sender = AsyncMock()
    with caplog.at_level(logging.INFO):
        await _send_whatsapp_image(
            PHONE_E164,
            IMG_URL,
            caption=caption,
            phone_number_id=PHONE_NUMBER_ID,
            meta_sender=meta_sender,
            turn_id="P9-TRACE",
        )
    assert "🛡️ [PRICE-LOCK]" in caplog.text
    assert "P9-TRACE" in caplog.text
    sent_caption = meta_sender.send_image_message.call_args[0][2]
    assert re.search(r"\$\d+", sent_caption)


# ──────────────── P10-MERGE-DECOY-GUARD (H3) ────────────────

def test_p10_merge_anchor_ignores_bare_dollar_decoy():
    r"""
    H3: sin línea 💰, el merge solo ancla a líneas con keyword 'precio' + $\d+.
    Un decoy tipo 'Cuotas desde $200.000' no debe pegarse a la Ficha Tecnica.
    """
    caption = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        "Te doy toda la info de la Raider 125\n"
        "Ficha Tecnica: TVS RAIDER 125\n"
        "Cuotas desde $200.000 con crédito directo\n"
        "Precio final: $6.790.000 (incluye SOAT, Matrícula, y tramites)\n"
        "¿Con quién tengo el gusto?"
    )
    out = _coerce_caption_price_lock(caption, turn_id="P10")

    assert re.search(r"\$6[\.,]?790[\.,]?000", out), f"precio real perdido: {out!r}"
    assert "$200.000" not in out, f"decoy pegado a la ficha: {out!r}"
    assert len(out.splitlines()) <= 4, f"excede 4 líneas: {out!r}"
    assert len(out) <= 350, f"excede 350 chars: {len(out)}"
    assert "¿Con quién tengo el gusto?" in out
