"""
Guard de doctrina Media API [BOT-BUILD-REVERT-VISUAL-LOCK-009].

Doctrina RESTAURADA: las imágenes del catálogo se envían por WhatsApp Business
Media API (send_image_message, payload type='image' con link+caption) — el
ÚNICO mecanismo que renderiza imagen EMBEBIDA en el cliente WhatsApp. El
experimento FIX-008 (Markdown como texto plano) mostró al usuario el string
literal '![Nombre](URL)' en lugar de la imagen y fue revertido (0e53ce6).

T1 — Egreso unificado: Markdown del LLM → _send_whatsapp_image con URL canónica
     y caption limpio (estrategia A); el token Markdown NO viaja como texto.
T2 — PHASE_GATE: imagen dinámica vía Media API con caption "Mira esta {Nombre}"
     y early return (sin envío unificado).
T3 — Contrato de renderizado: send_image_message construye el payload Meta
     type='image' + image.link + image.caption (lo que WhatsApp renderiza
     como imagen embebida, no como texto).
T4 — Guard estático antirregresión: _process_and_send_egress_message y la rama
     PHASE_GATE DEBEN contener la llamada a _send_whatsapp_image( — prohibido
     reintroducir el envío de imágenes de catálogo como texto Markdown plano
     (constraint 'prohibido' del ticket REVERT-009).
"""

import pathlib
import re

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers.whatsapp import _pipeline_egress, _process_and_send_egress_message

PHONE_E164 = "+573192564288"
PHONE_NUMBER_ID = "999999"
MOTO_NAME = "TVS APACHE RTR 200 4V XC FI ABS"
MOTO_URL = (
    "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos.appspot.com/o/"
    "products%2F1772685781061_Apache-200-4V-XC-FI.png?alt=media&token=6f2c8db4-a5cc-40be-8700-3fc0698d7a46"
)


def _build_ms_mock() -> MagicMock:
    ms = MagicMock()
    ms.save_message = AsyncMock()
    return ms


def _build_catalog_with_moto() -> MagicMock:
    catalog = MagicMock()
    catalog.search_catalog = MagicMock(return_value=[{
        "name": MOTO_NAME,
        "image_url": MOTO_URL,
        "formatted_price": "$13.899.999",
    }])
    return catalog


# ---------------------------------------------------------------------------
# T1: Egreso unificado — Media API (estrategia A), markdown NO viaja como texto
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_catalog_image_uses_media_api_never_plain_markdown_text():
    """
    [BOT-BUILD-REVERT-VISUAL-LOCK-009] El Markdown del LLM se intercepta y la
    imagen se envía por Media API con el texto limpio como caption (estrategia
    A). El token '![Nombre](URL)' jamás se envía como mensaje de texto plano.
    """
    mock_ms = _build_ms_mock()
    mock_image_sender = AsyncMock(return_value=True)
    mock_text_sender = AsyncMock(return_value=True)

    response_text = (
        f"¡Claro, Mario! La {MOTO_NAME} tiene un precio de $13.899.999.\n"
        f"![{MOTO_NAME}]({MOTO_URL})\n"
        "¿Te gustaría conocerla?"
    )

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp._send_whatsapp_image", mock_image_sender), \
         patch("app.routers.whatsapp._send_whatsapp_message", mock_text_sender):
        await _process_and_send_egress_message(PHONE_E164, response_text, phone_number_id=PHONE_NUMBER_ID)

    # Media API invocada EXACTAMENTE una vez con la URL canónica y caption limpio
    mock_image_sender.assert_awaited_once()
    args = mock_image_sender.await_args
    assert args.args[0] == PHONE_E164
    assert args.args[1] == MOTO_URL, f"La imagen debe ir por Media API con la URL canónica: {args.args[1]!r}"
    caption = args.kwargs.get("caption", "")
    assert "$13.899.999" in caption, "El caption debe portar el precio (Visual-Lock)"
    assert "![" not in caption and "](" not in caption, "El caption debe quedar limpio de tags"

    # El token Markdown NO se envía como texto plano (error del experimento FIX-008)
    for c in mock_text_sender.await_args_list:
        body = c.args[1]
        assert not re.search(r"!\[[^\]]*\]\(https?://", body), (
            f"REGRESIÓN FIX-008: imagen de catálogo enviada como texto Markdown plano: {body!r}"
        )


# ---------------------------------------------------------------------------
# T2: PHASE_GATE — imagen dinámica por Media API + early return
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_phase_gate_image_uses_media_api_with_caption():
    """
    [BOT-BUILD-REVERT-VISUAL-LOCK-009] PHASE_GATE sin moto confirmada envía la
    imagen dinámica por Media API con caption "Mira esta {Nombre}" + texto, y
    detiene el flujo (early return, sin envío unificado).
    """
    injected_catalog = _build_catalog_with_moto()
    mock_ms = _build_ms_mock()
    mock_image_sender = AsyncMock(return_value=True)
    mock_unified = AsyncMock(return_value=True)

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp._send_whatsapp_image", mock_image_sender), \
         patch("app.routers.whatsapp._process_and_send_egress_message", mock_unified):
        await _pipeline_egress(
            "PHASE_GATE_TRIGGERED:Tenemos la Apache lista para ti.",
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            prospect_data={"exists": True, "moto_confirmada": False, "moto_interest": MOTO_NAME},
            catalog=injected_catalog,
        )

    mock_image_sender.assert_awaited_once_with(
        PHONE_E164, MOTO_URL,
        caption=f"Mira esta {MOTO_NAME}\n\nTenemos la Apache lista para ti.",
        phone_number_id=PHONE_NUMBER_ID,
    )
    mock_unified.assert_not_called()
    mock_ms.save_message.assert_awaited_once_with(
        PHONE_E164, "model", "Tenemos la Apache lista para ti."
    )


# ---------------------------------------------------------------------------
# T3: Contrato de renderizado — payload Meta type='image' (imagen embebida)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_send_image_message_builds_embedded_image_payload():
    """
    [BOT-BUILD-REVERT-VISUAL-LOCK-009] Lo que hace que WhatsApp RENDERICE la
    imagen (en lugar de mostrar texto) es el payload type='image' con link.
    Pin del contrato exacto de send_image_message con la Graph API.
    """
    from app.services.whatsapp_service import WhatsAppService

    service = WhatsAppService.__new__(WhatsAppService)
    service.phone_number_id = PHONE_NUMBER_ID
    service.headers = {"Authorization": "Bearer test", "Content-Type": "application/json"}

    captured = {}

    class _FakeResponse:
        status_code = 200
        def json(self):
            return {"messages": [{"id": "wamid.test_img_render"}]}
        def raise_for_status(self):
            return None

    class _FakeClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def post(self, url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            return _FakeResponse()

    with patch("app.services.whatsapp_service.httpx.AsyncClient", return_value=_FakeClient()):
        await service.send_image_message(
            PHONE_E164, MOTO_URL, caption=f"La {MOTO_NAME} cuesta $13.899.999", phone_number_id=PHONE_NUMBER_ID
        )

    payload = captured["json"]
    assert payload["messaging_product"] == "whatsapp"
    assert payload["type"] == "image", "Solo type='image' renderiza imagen embebida en WhatsApp"
    assert payload["image"]["link"] == MOTO_URL
    assert "$13.899.999" in payload["image"]["caption"]
    # Anti-regresión: el Markdown NO es un mecanismo de envío de imagen válido
    assert "![Moto]" not in str(payload)


# ---------------------------------------------------------------------------
# T4: Guard estático — Media API obligatoria en el path de imágenes de catálogo
# ---------------------------------------------------------------------------
def test_media_api_mandatory_in_catalog_image_paths_source():
    """
    [BOT-BUILD-REVERT-VISUAL-LOCK-009] Guard estático antirregresión: los spans
    de egreso de imágenes de catálogo DEBEN contener `_send_whatsapp_image(`.
    Falla si se reintroduce el envío de imágenes como texto Markdown plano
    (constraint 'prohibido' del ticket REVERT-009).
    """
    root = pathlib.Path(__file__).resolve().parents[1]
    src = (root / "app/routers/whatsapp.py").read_text(encoding="utf-8")

    # Span 1: _process_and_send_egress_message (estrategia A restaurada)
    start = src.index("async def _process_and_send_egress_message")
    end = src.index("def _is_valid_statuses", start)
    unified_span = src[start:end]
    assert "_send_whatsapp_image(" in unified_span, (
        "REGRESIÓN FIX-008: el egreso unificado perdió la Media API (estrategia A). "
        "Las imágenes del catálogo DEBEN enviarse por send_image_message."
    )

    # Span 2: rama PHASE_GATE (imagen dinámica restaurada)
    pg_start = src.index('if response_text.startswith("PHASE_GATE_TRIGGERED:")')
    pg_end = src.index("await _process_and_send_egress_message", pg_start)
    phase_gate_span = src[pg_start:pg_end]
    assert "_send_whatsapp_image(" in phase_gate_span, (
        "REGRESIÓN FIX-008: PHASE_GATE perdió la imagen dinámica por Media API."
    )

    # Span 3: el egreso unificado NO debe enviar tokens Markdown como texto plano
    assert 'join(image_lines)' not in unified_span, (
        "REGRESIÓN FIX-008: patrón de Markdown-en-texto-plano detectado en el egreso."
    )
