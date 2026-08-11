"""
BOT-BUILD-SALVAGE-CAP-028 — Refuerzo del caption canónico PASO 1 en rama
salvage de PCC + blindaje forense ZSF del log HTTP de Gemini.

Pines:
  P1-CAPTION-4L-PRIMER-CONTACTO
  P2-CAPTION-4L-NOMBRE
  P3-SALUDO-GENERICO
  P4-JOINER-FIX3-PARITY
  P5-ZSF-SINGLE-LINE
  P5b-ZSF-TRUNCATED-BODY
  P6-ZSF-NEVER-RAISES-AND-NOT-EMPTY

Contrato asumido en P1/P2: el salvage siempre dispone de _catalog_top_name
(ver guarda en app/services/ai_brain.py :1353); aquí testeamos el helper de
caption con top_name poblado.
"""

import json
import re

import pytest

from app.services.ai_brain import CerebroIA
from app.services import egress_guard_service as egress_guard


PHONE_E164 = "+573192564289"
TOP_NAME = "Victory MRX 125"
FAKE_PRICE = "$5.000.000"
FAKE_IMG = (
    "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos.appspot.com/"
    "o/products%2Fmrx-125.png?alt=media"
)


def _egress_replica(caption: str):
    """
    Réplica inline del pipeline unificado de egreso (whatsapp.py
    _process_and_send_egress_message :2446-2474 + _send_whatsapp_image :2847).
    """
    txt, _ = egress_guard.enforce_urls(caption)
    markdown_pattern = r"!?\[[\s\S]*?\]\s*\((https?://[^\s\)]+)\)"
    images = re.findall(markdown_pattern, txt)
    cap = re.sub(markdown_pattern, "", txt).strip()
    return egress_guard.enforce_length(cap), images


# ──────────────── P1-CAPTION-4L-PRIMER-CONTACTO ────────────────

def test_p_028_p1_caption_4l_primer_contacto():
    """
    Primer contacto (nombre vacío) en salvage → post-egreso debe caber en
    4 líneas / 350 chars y contener saludo genérico + Ficha + 💰 + cierre.
    """
    brain = CerebroIA(catalog_service=None)
    caption = brain._build_canonical_paso1_caption(
        top_name=TOP_NAME,
        top_price=FAKE_PRICE,
        top_image=FAKE_IMG,
        user_name="",
    )
    out, images = _egress_replica(caption)

    assert len(out.splitlines()) <= 4, f"Caption excede 4 líneas: {out!r}"
    assert len(out) <= 350, f"Caption excede 350 chars: {len(out)}"
    assert "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos." in out
    assert "Ficha Tecnica: Victory MRX 125" in out
    assert "💰 Precio: $5.000.000" in out
    assert "¿Con quién tengo el gusto?" in out
    assert images == [FAKE_IMG]


# ──────────────── P2-CAPTION-4L-NOMBRE ────────────────

def test_p_028_p2_caption_4l_nombre_presente():
    """
    Nombre presente en salvage → saludo personalizado y 💰 deben sobrevivir
    al egreso (regresión de H1: enforce_length no debe decapitar 💰).
    """
    brain = CerebroIA(catalog_service=None)
    caption = brain._build_canonical_paso1_caption(
        top_name=TOP_NAME,
        top_price=FAKE_PRICE,
        top_image=FAKE_IMG,
        user_name="Mario",
    )
    out, _ = _egress_replica(caption)

    assert len(out.splitlines()) <= 4, f"Caption excede 4 líneas: {out!r}"
    assert len(out) <= 350, f"Caption excede 350 chars: {len(out)}"
    assert "¡Hola Mario! Soy Juan Pablo, asesor de Tienda Las Motos." in out
    assert "Ficha Tecnica: Victory MRX 125" in out
    assert "💰 Precio: $5.000.000" in out
    assert "¿Con quién tengo el gusto?" in out


# ──────────────── P3-SALUDO-GENERICO ────────────────

def test_p_028_p3_saludo_generico_primer_contacto():
    """
    El builder siempre incluye el saludo cálido canónico de Juan Pablo;
    cuando el nombre está vacío o es 'desconocido' usa la variante genérica.
    """
    brain = CerebroIA(catalog_service=None)
    for user_name in ("", "desconocido"):
        caption = brain._build_canonical_paso1_caption(
            top_name=TOP_NAME,
            top_price=FAKE_PRICE,
            top_image=FAKE_IMG,
            user_name=user_name,
        )
        assert "¡Hola! Soy Juan Pablo, asesor de Tienda Las Motos." in caption
        assert "¡Hola Mario!" not in caption


# ──────────────── P4-JOINER-FIX3-PARITY ────────────────

def test_p_028_p4_joiner_fix3_parity():
    """
    Paridad con Fix-3 de BOT-BUILD-EMPTY-CANDIDATE-021: el joiner interno
    es '\\n', no '\\n\\n'. Cada parte canónica ocupa su propia línea.
    """
    brain = CerebroIA(catalog_service=None)
    caption = brain._build_canonical_paso1_caption(
        top_name=TOP_NAME,
        top_price=FAKE_PRICE,
        top_image=FAKE_IMG,
        user_name="Mario",
    )

    assert "\n\n" not in caption, f"Aún usa joiner \\n\\n: {caption!r}"
    lines = caption.splitlines()
    assert any("Soy Juan Pablo" in ln for ln in lines)
    assert any("Ficha Tecnica:" in ln for ln in lines)
    assert any("💰 Precio:" in ln for ln in lines)
    assert any(f"![{TOP_NAME}]" in ln for ln in lines)
    assert any("¿Con quién tengo el gusto?" in ln for ln in lines)


# ──────────────── P5-ZSF-SINGLE-LINE ────────────────

def test_p_028_p5_zsf_single_line_bounded():
    """
    El serializador de cuerpo HTTP pretty-printed colapsa a UNA línea,
    conserva la metadata del error 429 y no excede el cap por defecto.
    """
    pretty_429 = (
        '{\n'
        '  "error": {\n'
        '    "code": 429,\n'
        '    "message": "Quota exceeded",\n'
        '    "status": "RESOURCE_EXHAUSTED"\n'
        '  }\n'
        '}'
    )

    class FakeErr(Exception):
        details = json.loads(pretty_429)
        message = "fallback"

    out = CerebroIA._format_gemini_error_body(FakeErr())

    assert len(out.splitlines()) == 1, f"No quedó en 1 línea: {out!r}"
    assert "429" in out
    assert "RESOURCE_EXHAUSTED" in out
    assert len(out) <= 800


# ──────────────── P5b-ZSF-TRUNCATED-BODY ────────────────

def test_p_028_p5b_zsf_truncated_marker():
    """
    Cuerpo de error mayor al cap debe llevar marca explícita de truncado.
    """
    big_details = {"error": {"code": 429, "message": "x" * 2000}}

    class FakeErr(Exception):
        details = big_details

    out = CerebroIA._format_gemini_error_body(FakeErr(), cap=100)

    assert "…[truncated" in out
    assert len(out) <= 140  # cap + marca de truncado razonable


# ──────────────── P6-ZSF-NEVER-RAISES-AND-NOT-EMPTY ────────────────

def test_p_028_p6_zsf_never_raises_and_not_empty():
    """
    El serializador nunca lanza y nunca retorna string vacío, incluso ante
    inputs degenerados (bytes, response sin .text, details no serializable,
    excepción plana).
    """

    class RespBytes:
        text = b"\x89PNG\r\n"

    class RespNoText:
        pass

    class DetailsWeird:
        def __repr__(self):
            raise RuntimeError("boom")

    class MsgOnly(Exception):
        pass

    class ZeroMsg(Exception):
        # Falsy y no subscriptable: fuerza la rama _fallback() del serializador.
        details = None
        response = None
        message = 0

    cases = [
        type("E1", (Exception,), {"details": {"a": 1}, "response": None, "message": None})(),
        type("E2", (Exception,), {"details": None, "response": RespBytes(), "message": None})(),
        type("E3", (Exception,), {"details": None, "response": RespNoText(), "message": "fallback msg"})(),
        type("E4", (Exception,), {"details": DetailsWeird(), "response": None, "message": None})(),
        MsgOnly("hello"),
        ZeroMsg(),
    ]

    for e in cases:
        out = CerebroIA._format_gemini_error_body(e)
        assert isinstance(out, str), f"Retorno no string para {type(e).__name__}"
        assert out.strip() != "", f"Retorno vacío para {type(e).__name__}"
