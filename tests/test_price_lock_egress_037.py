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
    _price_lock_failure_reason,
    _price_lock_rescue_top4,
    _send_whatsapp_image,
    _split_ficha_price_line,
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


# ──────────────── P11-H3-PROSA-UNICA (R1.4 anti-decoy) ────────────────

def test_p11_h3_prosa_unica_linea_dollar():
    """
    R1.4: precio en prosa sin emoji 💰 ni keyword 'precio', siendo la ÚNICA
    línea $ y con Ficha presente → debe anclarse a la Ficha y sobrevivir.
    Mordida: eliminar la rama R1.4 (unicidad) → P11 FAIL.
    """
    caption = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        "¡Claro que tenemos crédito directo! 🏍️\n"
        "Ficha Tecnica: VICTORY NEW LIFE 125\n"
        "La NEW LIFE 125 es perfecta para la ciudad y arranca en $7.690.000 lista para financiar.\n"
        "¿Con quién tengo el gusto?"
    )
    out = _coerce_caption_price_lock(caption, turn_id="P11")

    assert len(out.splitlines()) <= 4, f"excede 4 líneas: {out!r}"
    assert len(out) <= 350, f"excede 350 chars: {len(out)}"
    assert "Ficha Tecnica: VICTORY NEW LIFE 125" in out
    assert re.search(r"\$\d+", out), f"precio perdido: {out!r}"
    assert "¿Con quién tengo el gusto?" in out


# ──────────────── P12-H2-FICHA-EMBEBIDA (R2 split) ────────────────

def test_p12_h2_ficha_parrafo_con_precio_embebido():
    """
    R2: Ficha Tecnica como párrafo largo con 'Precio: $X' embebido al final.
    p_idx == f_idx en el helper original; el split compacto debe preservar
    modelo + precio. Mordida: eliminar R2 → P12 FAIL.
    """
    ficha_larga = (
        "Ficha Tecnica: VICTORY NEW LIFE 125 — Motor 124.8 cm3 monocilindrico 4 tiempos SOHC, "
        "potencia 11.1 hp @ 8000 rpm, torque 10.9 Nm @ 6000 rpm, frenos de disco con CBS, "
        "suspension delantera telescopica e invertida, tanque 11 L, consumo aprox. 52 km/l, "
        "peso 127 kg, garantia extendida de fabrica, colores disponibles negro y blanco. "
        "Precio: $7.690.000 (incluye SOAT, Matrícula, y tramites)"
    )
    caption = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        "¡Claro que tenemos crédito directo, estrenarla es muy fácil! 🏍️\n"
        f"{ficha_larga}\n"
        "¿Con quién tengo el gusto?"
    )
    out = _coerce_caption_price_lock(caption, turn_id="P12")

    assert len(out.splitlines()) <= 4, f"excede 4 líneas: {out!r}"
    assert len(out) <= 350, f"excede 350 chars: {len(out)}"
    assert "Ficha Tecnica: VICTORY NEW LIFE 125" in out
    assert re.search(r"\$7[\.,]?690[\.,]?000", out), f"precio perdido: {out!r}"
    assert "¿Con quién tengo el gusto?" in out


def test_p12b_h2_ficha_degenerate_model_cond2():
    """
    COND-2: delimitador degenerado imposible de extraer modelo. El fallback
    del split NUNCA emite 'Ficha Tecnica:  ·' y SIEMPRE conserva 💰 Precio.
    """
    caption = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        "Ficha Tecnica: — disponible por $7.690.000 (incluye SOAT, Matrícula, y tramites)\n"
        "¿Con quién tengo el gusto?"
    )
    out = _coerce_caption_price_lock(caption, turn_id="P12b")

    assert "Ficha Tecnica:  ·" not in out, f"prefijo vacío prohibido: {out!r}"
    assert re.search(r"\$7[\.,]?690[\.,]?000", out), f"precio perdido: {out!r}"
    assert len(out.splitlines()) <= 4
    assert len(out) <= 350


# ──────────────── P13-MULTI-DOLLAR-AMBIGUO ────────────────

def test_p13_multi_dollar_ambiguous_stays_t3(caplog):
    """
    Múltiples líneas $ sin 💰 ni keyword 'precio', ambas fuera de la ventana
    de 4 líneas, deben quedar en T3; el merge no debe pegar un decoy.
    Mordida: anclar siempre la primera $ → P13 FAIL.
    """
    caption = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        "Ficha Tecnica: TVS RAIDER 125\n"
        "Te doy toda la info de financiación\n"
        "Cuotas desde $200.000 con crédito directo\n"
        "Seguro todo riesgo $350.000 anual\n"
        "¿Con quién tengo el gusto?"
    )
    with caplog.at_level(logging.WARNING):
        out = _coerce_caption_price_lock(caption, turn_id="P13")

    assert out == egress_guard.enforce_length(caption)
    assert "🚨 [PRICE-LOCK]" in caplog.text
    assert "reason=multi_dollar_ambiguous" in caplog.text
    assert "$200.000" not in out and "$350.000" not in out


# ──────────────── P15-PRECIOS-PLURAL (Finding 1 hardener) ────────────────

def test_p15_precios_plural_keyword_multi_dollar():
    """
    R1.2 plural: caption multi-$ sin 💰, donde la línea real usa 'Precios'
    (plural). Debe anclarse a la Ficha y sobrevivir; el decoy de cuotas no.
    Mordida: revertir a \bprecio\b (sin plural) → P15 FAIL (T3 ambiguo).
    """
    caption = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        "Ficha Tecnica: VICTORY NEW LIFE 125\n"
        "Te doy toda la info de financiación\n"
        "Cuotas desde $200.000 con crédito directo\n"
        "Precios especiales: $6.790.000 (incluye SOAT, Matrícula, y tramites)\n"
        "¿Con quién tengo el gusto?"
    )
    out = _coerce_caption_price_lock(caption, turn_id="P15")

    assert re.search(r"\$6[\.,]?790[\.,]?000", out), f"precio real perdido: {out!r}"
    assert "$200.000" not in out, f"decoy pegado: {out!r}"
    assert len(out.splitlines()) <= 4, f"excede 4 líneas: {out!r}"
    assert len(out) <= 350, f"excede 350 chars: {len(out)}"
    assert "¿Con quién tengo el gusto?" in out


# ──────────────── P16-FICHA-TEXT-FIRST + nits (Finding 2 hardener) ────────────────

def test_p16_ficha_text_first_cond2_plus_nits():
    """
    COND-2 text-first: ficha con summary técnico (sin delimitador real tras
    el 'modelo') y Precio embebido al final. No debe emitir 'Ficha Tecnica:'
    con etiqueta basura; precio viaja como línea 💰 Precio: desnuda.
    Nit A: token de precio nunca termina en punto de oración.
    Nit B: '(Incluye ...)' con mayúscula inicial viaja.
    Mordida: quitar requisito de delimitador → P16 FAIL (etiqueta basura).
    """
    ficha_text_first = (
        "Ficha Tecnica: Motor 124.8 cm3 monocilindrico 4 tiempos SOHC, potencia 11.1 hp @ 8000 rpm, "
        "torque 10.9 Nm @ 6000 rpm, frenos de disco con CBS, suspension telescopica, tanque 11 L, "
        "consumo aprox. 52 km/l, peso 127 kg, garantia extendida de fabrica, colores negro y blanco. "
        "Precio: $7.690.000 (Incluye SOAT y Matrícula)"
    )
    caption = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        "¡Claro que tenemos crédito directo, estrenarla es muy fácil! 🏍️\n"
        f"{ficha_text_first}\n"
        "¿Con quién tengo el gusto?"
    )
    assert len(caption) > 350, "precondición: caption debe exceder 350 chars"

    out = _coerce_caption_price_lock(caption, turn_id="P16")

    assert len(out.splitlines()) <= 4, f"excede 4 líneas: {out!r}"
    assert len(out) <= 350, f"excede 350 chars: {len(out)}"
    assert re.search(r"\$7[\.,]?690[\.,]?000", out), f"precio perdido: {out!r}"
    assert "Ficha Tecnica: Motor 124" not in out, f"etiqueta basura emitida: {out!r}"
    assert "💰 Precio: $7.690.000 (Incluye SOAT y Matrícula)" in out

    # Nit A: token de precio nunca absorbe el punto final de oración.
    out_b = _split_ficha_price_line(["Ficha Tecnica: — cuesta $8.900.000. listo"], 0)
    assert "$8.900.000" in out_b, f"precio no viaja: {out_b!r}"
    assert "$8.900.000." not in out_b, f"punto final pegado al monto: {out_b!r}"


# ──────────────── P14-REGRESSION-GUARD ────────────────

@pytest.mark.parametrize(
    "caption,expect_price_survives,expect_byte_identical,expected_reason",
    [
        # T0 byte-identico (cabe en 4 líneas, $ sobrevive sin intervención)
        ("Ficha Tecnica: X\n💰 Precio: $1.000\n¿Con quién tengo el gusto?", True, True, None),
        # P1/P2-like: rescate activo (>$ línea se pierde, helper la salva)
        ("Linea A\nLinea B\nFicha Tecnica: X\n💰 Precio: $1.000\n¿Con quién tengo el gusto?", True, False, None),
        # P5: sin precio, T0 byte-identico
        ("Linea A\n¿Con quién tengo el gusto?", False, True, None),
        # COND-1: $ único SIN Ficha, fuera de ventana → T3 (R1.4 no dispara sin f_idx)
        ("Linea A\nLinea B\nLinea C\n$1.000 es el valor\n¿Con quién tengo el gusto?", False, True, "no_ficha_line"),
    ],
)
def test_p14_regression_guard_invariants(
    caption, expect_price_survives, expect_byte_identical, expected_reason, caplog
):
    """Guardas de no-regresión: invarianzas del wrapper v2 vs v10.70.0."""
    with caplog.at_level(logging.WARNING):
        out = _coerce_caption_price_lock(caption, turn_id="P14")

    has_price = bool(re.search(r"\$\d+", out))
    assert has_price == expect_price_survives, (
        f"invariante de precio rota: caption={caption!r} out={out!r}"
    )
    if expect_byte_identical:
        assert out == egress_guard.enforce_length(caption)
    if expected_reason:
        assert f"reason={expected_reason}" in caplog.text


# ──────────────── P17-P21: T3 RESCUE (BOT-BUILD-PRICE-LOCK-T3-074) ────────────────


def test_p17_live_repro_383_254_rescue_preserves_price(caplog):
    """
    Reproducción estructural SIN PII del evento en vivo 2026-08-14 02:50Z:
    caption con saludo, blurb crediticio extenso, Ficha Tecnica con summary
    largo, 💰 Precio y cierre; T0/T1/T2 pierden el $; T3-rescue lo conserva.
    """
    ficha_larga = (
        "Ficha Tecnica: TVS RAIDER 125 — Motor 124.8 cc monocilíndrico 4T SOHC, "
        "potencia 11.38 hp @ 7500 rpm, torque 11.2 Nm @ 6000 rpm, frenos de disco "
        "con CBS, suspensión invertida, tanque 10 L, consumo aprox. 55 km/l, "
        "garantía extendida de fábrica, colores disponibles."
    )
    caption = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        "¡Claro que tenemos crédito directo, estrenarla es muy fácil! 🏍️\n"
        "Te doy toda la info de financiación para que armes el plan perfecto.\n"
        f"{ficha_larga}\n"
        "💰 Precio: $6.790.000 (incluye SOAT, Matrícula, y tramites)\n"
        "¿Con quién tengo el gusto?"
    )
    assert len(caption) >= 380, f"precondición longitud: {len(caption)}"

    with caplog.at_level(logging.INFO):
        out = _coerce_caption_price_lock(caption, turn_id="P17")

    assert "tier=T3-rescue" in caplog.text, "P17 debe ejecutar T3-rescue"
    assert len(out.splitlines()) <= 4, f"excede 4 líneas: {out!r}"
    assert len(out) <= 350, f"excede 350 chars: {len(out)}"
    assert re.search(r"\$6[\.,]?790[\.,]?000", out), f"precio perdido: {out!r}"
    assert "Ficha Tecnica: TVS RAIDER 125" in out
    assert "¿Con quién tengo el gusto?" in out


def test_p18_t3_ficha_off_window(caplog):
    """
    La línea Ficha Tecnica queda fuera de las primeras 4 líneas; T1/T2 no
    logran anclar el precio a una línea dentro de la ventana. T3-rescue lo
    inyecta junto al saludo y sobrevive.
    """
    caption = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        "¡Claro que tenemos crédito directo! 🏍️\n"
        "Te doy toda la info de financiación para que armes el plan perfecto.\n"
        "Con este crédito las cuotas son muy cómodas y el proceso es 100% digital.\n"
        "Ficha Tecnica: VICTORY NEW LIFE 125 — ficha técnica completa\n"
        "💰 Precio: $7.690.000 (incluye SOAT, Matrícula, y tramites)\n"
        "¿Con quién tengo el gusto?"
    )
    with caplog.at_level(logging.INFO):
        out = _coerce_caption_price_lock(caption, turn_id="P18")

    assert "tier=T3-rescue" in caplog.text, "P18 debe ejecutar T3-rescue"
    assert len(out.splitlines()) <= 4, f"excede 4 líneas: {out!r}"
    assert len(out) <= 350, f"excede 350 chars: {len(out)}"
    assert re.search(r"\$7[\.,]?690[\.,]?000", out), f"precio perdido: {out!r}"
    assert "Ficha Tecnica: VICTORY NEW LIFE 125" in out
    assert "¿Con quién tengo el gusto?" in out


def test_p19_t3_char_truncation_rescue_keeps_full_amount(caplog):
    """
    La línea fusionada T1/T2 supera el presupuesto de caracteres y truncaría
    el monto; T3-rescue usa una línea compacta que no se corta a mitad.
    El input fuerza el rescue: dos blurbs largos empujan la línea fusionada
    más allá del budget de caracteres, por lo que T1/T2 pierden el precio.
    """
    ficha_larga = (
        "Ficha Tecnica: VICTORY NEW LIFE 125 — Motor 124.8 cc monocilíndrico 4T SOHC "
        "potencia 11.1 hp @ 8000 rpm torque 10.9 Nm @ 6000 rpm frenos de disco con CBS "
        "suspensión delantera telescópica e invertida tanque 11 L consumo 52 km/l "
        "peso 127 kg garantía extendida colores negro y blanco."
    )
    caption = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        "¡Claro que tenemos crédito directo, estrenarla es muy fácil! 🏍️\n"
        "Te doy toda la info de financiación para que armes el plan perfecto con cuotas cómodas y aprobación inmediata.\n"
        "Además, el crédito incluye seguro de deuda y opción de refinanciación sin comisiones ocultas.\n"
        f"{ficha_larga}\n"
        "💰 Precio: $7.690.000 (incluye SOAT, Matrícula, y tramites)\n"
        "¿Con quién tengo el gusto?"
    )
    with caplog.at_level(logging.INFO):
        out = _coerce_caption_price_lock(caption, turn_id="P19")

    assert "tier=T3-rescue" in caplog.text, "P19 debe ejecutar T3-rescue"
    assert len(out.splitlines()) <= 4, f"excede 4 líneas: {out!r}"
    assert len(out) <= 350, f"excede 350 chars: {len(out)}"
    assert "💰 Precio: $7.690.000" in out, f"monto truncado: {out!r}"
    assert "¿Con quién tengo el gusto?" in out


def test_p20_forensic_label_anchor_merged_but_truncated():
    """
    C5-064: _price_lock_failure_reason debe distinguir entre 'no hubo merge'
    y 'merge existió pero se perdió post-coerción'.
    """
    merge_exists_but_truncated = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        "¡Claro que tenemos crédito directo! 🏍️\n"
        "Te doy toda la info de financiación para que armes el plan perfecto.\n"
        "Ficha Tecnica: TVS RAIDER 125\n"
        "💰 Precio: $6.790.000 (incluye SOAT, Matrícula, y tramites)\n"
        "¿Con quién tengo el gusto?"
    )
    no_merge_possible = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        "Línea de contexto adicional\n"
        "Otra línea de contexto\n"
        "$6.790.000 es el precio de la moto\n"
        "¿Con quién tengo el gusto?"
    )

    assert _price_lock_failure_reason(merge_exists_but_truncated) == "anchor_merged_but_truncated"
    assert _price_lock_failure_reason(no_merge_possible) == "no_ficha_line"


def test_p21_no_regression_other_paths():
    """
    Verificación explícita de que T0, paths sin precio y T1/T2 exitosos no
    cambian de comportamiento tras introducir T3-rescue.
    """
    # T0 byte-idéntico
    t0 = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos.\n"
        "Ficha Tecnica: Victory MRX 125\n"
        "💰 Precio: $5.000.000\n"
        "¿Con quién tengo el gusto?"
    )
    assert _coerce_caption_price_lock(t0, turn_id="P21-T0") == egress_guard.enforce_length(t0)

    # Sin precio
    no_price = "¡Hola! Soy Juan Pablo.\n¿Con quién tengo el gusto?"
    assert _coerce_caption_price_lock(no_price, turn_id="P21-NO$") == egress_guard.enforce_length(no_price)

    # T1/T2 exitoso (P1/P2-like)
    t1 = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        "¡Claro que tenemos crédito! Te presento la ⭐ TOP RESULT:\n"
        "Ficha Tecnica: TVS RAIDER 125\n"
        "💰 Precio: $6.790.000 (incluye SOAT, Matrícula, y tramites)\n"
        f"![TVS RAIDER 125]({IMG_URL})\n"
        "¿Con quién tengo el gusto?"
    )
    caption_t1, _ = _pipeline_replica(t1)
    out_t1 = _coerce_caption_price_lock(caption_t1, turn_id="P21-T1")
    assert re.search(r"\$6[\.,]?790[\.,]?000", out_t1)
    assert "Ficha Tecnica: TVS RAIDER 125" in out_t1
    assert "¿Con quién tengo el gusto?" in out_t1

    # T3-rescue no se dispara cuando no hay Ficha (preserva P8)
    no_ficha = (
        "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos. 😊\n"
        "Línea de contexto adicional número dos\n"
        "Línea de contexto adicional número tres\n"
        "$6.790.000 es el precio de la moto\n"
        "¿Con quién tengo el gusto?"
    )
    assert _coerce_caption_price_lock(no_ficha, turn_id="P21-NOFICHA") == egress_guard.enforce_length(no_ficha)


def test_p22_greeting_with_literal_price_prefix_excluded(caplog):
    """
    [BOT-BUILD-PRICE-LOCK-T3-074+RF / R1] El saludo puede contener el prefijo
    literal "💰 Precio:" sin dígitos (salida no canónica del modelo). El rescue
    no debe asumir que filtered[0] == greeting y descartar una línea de
    contenido legítima. Colateral documentado: C5-075 (prefijo duplicado,
    cosmético).
    """
    caption = (
        "¡Hola! 💰 Precio: especial de lanzamiento\n"
        "Línea de contexto uno que debe sobrevivir\n"
        "Te doy toda la info de financiación para que armes el plan perfecto.\n"
        "Con este crédito las cuotas son muy cómodas y el proceso es 100% digital.\n"
        "Ficha Tecnica: TVS RAIDER 125 — ficha técnica\n"
        "💰 Precio: $6.790.000 (incluye SOAT, Matrícula, y tramites)\n"
        "¿Con quién tengo el gusto?"
    )
    with caplog.at_level(logging.INFO):
        out = _coerce_caption_price_lock(caption, turn_id="P22")

    assert "tier=T3-rescue" in caplog.text, "P22 debe ejecutar T3-rescue"
    assert len(out.splitlines()) <= 4, f"excede 4 líneas: {out!r}"
    assert len(out) <= 350, f"excede 350 chars: {len(out)}"
    assert "Línea de contexto uno que debe sobrevivir" in out, (
        f"línea de contenido descartada erróneamente: {out!r}"
    )
    assert re.search(r"\$6[\.,]?790[\.,]?000", out), f"precio perdido: {out!r}"
    assert "¿Con quién tengo el gusto?" in out
