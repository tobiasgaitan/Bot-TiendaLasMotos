"""
Guard anti-regresión [BOT-PLAN-FIX-VISUAL-LOCK-MARKDOWN-008].

Doctrina: las imágenes del catálogo viajan como MARKDOWN EN TEXTO PLANO
(![Nombre_Moto](URL) byte-idéntico, renderizado como thumbnail vía
preview_url=True), NUNCA por WhatsApp Media API. La Media API (131053:
crawler de Meta 404 al descargar el weblink) mataba la entrega completa
— imagen y caption — vía status webhook asíncrono.

T1 — Path Markdown: 2 mensajes de texto (Msg1 token byte-idéntico, Msg2 texto
     limpio), CERO Media API, save(model) con texto RAW. Visual-Lock (precio +
     markdown) entregado en el mismo turno.
T2 — PHASE_GATE: inyección Markdown + fall-through; CERO Media API; markdown
     byte-idéntico en el primer mensaje; historia RAW.
T3 — REGLAS_DE_LONGITUD: el mensaje markdown es 1 línea y ≤350 chars incluso
     con la URL Firebase más larga; el texto viaja en mensaje separado.
T4 — Guard estático: _send_whatsapp_image( no puede reaparecer dentro de
     _process_and_send_egress_message ni de la rama PHASE_GATE del router.
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
# T1: Path Markdown — 2 mensajes de texto, CERO Media API, historia RAW
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_markdown_image_sent_as_plain_text_never_media_api():
    """
    [BOT-PLAN-FIX-VISUAL-LOCK-MARKDOWN-008] El token ![Nombre](URL) viaja como
    mensaje de texto BYTE-IDÉNTICO (Msg1), el texto limpio con el precio como
    Msg2, y jamás se invoca la Media API. Visual-Lock entregado en el mismo turno.
    """
    mock_ms = _build_ms_mock()
    mock_text_sender = AsyncMock(return_value=True)
    mock_image_sender = AsyncMock(return_value=True)

    token = f"![{MOTO_NAME}]({MOTO_URL})"
    response_text = f"¡Claro, Mario! La {MOTO_NAME} tiene un precio de $13.899.999.\n{token}\n¿Te gustaría conocerla?"

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp._send_whatsapp_message", mock_text_sender), \
         patch("app.routers.whatsapp._send_whatsapp_image", mock_image_sender):
        await _process_and_send_egress_message(PHONE_E164, response_text, phone_number_id=PHONE_NUMBER_ID)

    # CERO Media API
    mock_image_sender.assert_not_called()

    # Msg1 = Markdown byte-idéntico (constraint 'obligatorio' del ticket)
    calls = mock_text_sender.await_args_list
    assert len(calls) == 2, f"Debían enviarse 2 mensajes de texto (markdown + texto): {calls!r}"
    assert calls[0].args[0] == PHONE_E164
    assert calls[0].args[1] == token, f"El Markdown debía ser byte-idéntico: {calls[0].args[1]!r}"

    # Msg2 = texto limpio con el precio (Visual-Lock en el mismo turno)
    assert "$13.899.999" in calls[1].args[1]
    assert "![" not in calls[1].args[1]

    # Historia RAW con Markdown (fiel a lo recibido)
    mock_ms.save_message.assert_awaited_once_with(PHONE_E164, "model", response_text)


# ---------------------------------------------------------------------------
# T2: PHASE_GATE — inyección Markdown + fall-through, CERO Media API
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_phase_gate_uses_markdown_text_never_media_api():
    """
    [BOT-PLAN-FIX-VISUAL-LOCK-MARKDOWN-008] PHASE_GATE_TRIGGERED inyecta el
    Visual-Lock como Markdown en el texto y cae al envío unificado: el primer
    mensaje es el token byte-idéntico ![Nombre](URL), sin Media API.
    """
    injected_catalog = _build_catalog_with_moto()
    mock_ms = _build_ms_mock()
    mock_text_sender = AsyncMock(return_value=True)
    mock_image_sender = AsyncMock(return_value=True)

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.catalog_service", MagicMock(name="sentinel")), \
         patch("app.routers.whatsapp._send_whatsapp_message", mock_text_sender), \
         patch("app.routers.whatsapp._send_whatsapp_image", mock_image_sender):
        await _pipeline_egress(
            "PHASE_GATE_TRIGGERED:Tenemos la Apache lista para ti.",
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            prospect_data={"exists": True, "moto_confirmada": False, "moto_interest": MOTO_NAME},
            catalog=injected_catalog,
        )

    injected_catalog.search_catalog.assert_called_once_with(MOTO_NAME)
    mock_image_sender.assert_not_called()

    calls = mock_text_sender.await_args_list
    assert calls, "Debió enviarse al menos un mensaje de texto"
    assert calls[0].args[1] == f"![{MOTO_NAME}]({MOTO_URL})", (
        f"El primer mensaje debía ser el Markdown byte-idéntico del Phase-Gate: {calls[0].args[1]!r}"
    )
    # El texto ("Mira esta..." + cuerpo) viaja en el segundo mensaje
    assert any("Mira esta" in c.args[1] and "Tenemos la Apache lista para ti." in c.args[1] for c in calls[1:])

    # Historia RAW con el Markdown inyectado
    saved = [c for c in mock_ms.save_message.await_args_list]
    assert saved and f"![{MOTO_NAME}]({MOTO_URL})" in saved[0].args[2]


# ---------------------------------------------------------------------------
# T3: REGLAS_DE_LONGITUD — markdown = 1 línea ≤350 chars, texto separado
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_markdown_message_respects_whatsapp_length_rules():
    """
    [BOT-PLAN-FIX-VISUAL-LOCK-MARKDOWN-008] Con el peor caso de URL Firebase
    (~190 chars), el mensaje Markdown es 1 sola línea y ≤350 caracteres
    (CONTROL_DE_LINEAS del prompt), y el texto precio+pregunta viaja aparte.
    """
    mock_ms = _build_ms_mock()
    mock_text_sender = AsyncMock(return_value=True)

    token = f"![{MOTO_NAME}]({MOTO_URL})"  # ~226 chars (peor caso catálogo)
    response_text = f"La {MOTO_NAME} tiene un precio de $13.899.999 (incluye SOAT, Matrícula, y tramites).\n{token}\n¿Te gustaría visitar la sede?"

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp._send_whatsapp_message", mock_text_sender), \
         patch("app.routers.whatsapp._send_whatsapp_image", AsyncMock(return_value=True)):
        await _process_and_send_egress_message(PHONE_E164, response_text, phone_number_id=PHONE_NUMBER_ID)

    calls = mock_text_sender.await_args_list
    assert len(calls) == 2

    markdown_msg = calls[0].args[1]
    assert "\n" not in markdown_msg.strip(), "El mensaje Markdown debe ser 1 sola línea"
    assert len(markdown_msg) <= 350, f"Markdown message excede 350 chars: {len(markdown_msg)}"

    text_msg = calls[1].args[1]
    assert len(text_msg) <= 350, f"El texto limpio excede 350 chars: {len(text_msg)}"
    assert len(text_msg.splitlines()) <= 4, "El texto limpio excede 4 líneas"


# ---------------------------------------------------------------------------
# T4: Guard estático — Media API no puede reaparecer en el path de catálogo
# ---------------------------------------------------------------------------
def test_no_media_api_in_catalog_image_path_source():
    """
    [BOT-PLAN-FIX-VISUAL-LOCK-MARKDOWN-008] Guard estático antirregresión:
    escanea app/routers/whatsapp.py y falla si `_send_whatsapp_image(` reaparece
    dentro de `_process_and_send_egress_message` o de la rama PHASE_GATE.
    (El helper se preserva para su costura DI, pero queda PROHIBIDO en estos
    dos spans.) Patrón hermano de test_crediorbe_eradicated_from_source.
    """
    root = pathlib.Path(__file__).resolve().parents[1]
    src = (root / "app/routers/whatsapp.py").read_text(encoding="utf-8")

    # Span 1: cuerpo de _process_and_send_egress_message
    start = src.index("async def _process_and_send_egress_message")
    end = src.index("def _is_valid_statuses", start)
    unified_egress_span = src[start:end]
    assert "_send_whatsapp_image(" not in unified_egress_span, (
        "REGRESIÓN: Media API reintroducida en _process_and_send_egress_message. "
        "Las imágenes del catálogo viajan como Markdown en texto plano (FIX-VISUAL-LOCK-MARKDOWN-008)."
    )

    # Span 2: rama PHASE_GATE dentro de _pipeline_egress
    pg_start = src.index('if response_text.startswith("PHASE_GATE_TRIGGERED:")')
    pg_end = src.index("await _process_and_send_egress_message", pg_start)
    phase_gate_span = src[pg_start:pg_end]
    assert "_send_whatsapp_image(" not in phase_gate_span, (
        "REGRESIÓN: Media API reintroducida en la rama PHASE_GATE. "
        "El Visual-Lock se inyecta como Markdown y fluye al envío unificado."
    )
