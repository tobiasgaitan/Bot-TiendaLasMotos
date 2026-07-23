"""
Integridad del Egreso Consolidado — Etapa 3 Wave 05-05
[BOT-BUILD-ETAPA3-WAVE05-FRAGMENT-TEXT-EGRESS-001]

Pins de paridad de `_pipeline_egress` (sprout method intra-archivo que consolida el
bloque post-rama del God Node — HANDOFF + PHASE_GATE — delegando el envío unificado
en `_process_and_send_egress_message`, BOT-BUGFIX-UNIFIED-EGRESS-PIPELINE-125).

  PEI-1  Texto plano: delegación al envío unificado con la firma exacta pineada
         por CH-5 (phone, text, phone_number_id=…); cero efectos colaterales.
  PEI-2  HANDOFF_TRIGGERED: set_human_help(True) + ponytail DEPRIORITIZED +
         transferencia + notificación — sin pasar por el envío unificado.
  PEI-3  PHASE_GATE_TRIGGERED (moto no confirmada): inyección de imagen dinámica
         con caption "Mira esta {Nombre}\n\n{texto}" + save(model); sin envío
         unificado. Costura catalog: kwarg prioritario / fallback al global.
  PEI-4  PHASE_GATE con moto confirmada: bypass de imagen y delegación al envío
         unificado con el texto despojado del prefijo.
  PEI-5  Unificación BOT-125 + Visual-Lock: texto con Markdown ![alt](url) →
         _send_whatsapp_image con caption limpio (estrategia A) y eco
         save(model) POSTERIOR al envío; patch targets de whatsapp_service
         vigentes (resolución meta_sender en tiempo de llamada).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers.whatsapp import _pipeline_egress

PHONE_E164 = "+573192564288"
PHONE_NUMBER_ID = "999999"
MOTO_NAME = "TVS Raider 125"
MOTO_URL = "http://catalog.test/raider125.png"


def _build_ms_mock() -> MagicMock:
    ms = MagicMock()
    ms.save_message = AsyncMock()
    ms.set_human_help_status = AsyncMock()
    ms.update_prospect_summary = AsyncMock()
    return ms


def _build_catalog_with_moto() -> MagicMock:
    catalog = MagicMock()
    catalog.search_catalog = MagicMock(return_value=[{
        "name": MOTO_NAME,
        "image_url": MOTO_URL,
        "formatted_price": "$9.000.000",
    }])
    return catalog


# ── PEI-1: Texto plano → envío unificado con firma exacta ────────────────────

@pytest.mark.asyncio
async def test_pei1_plain_text_delegates_to_unified_egress_exact_signature():
    """
    Texto sin prefijos de control: el pipeline consolida el egreso delegando en
    `_process_and_send_egress_message` con la firma exacta pineada por CH-5.
    """
    mock_ms = _build_ms_mock()
    mock_unified = AsyncMock(return_value=True)

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp._process_and_send_egress_message", mock_unified):
        await _pipeline_egress(
            "La Raider 125 es excelente.",
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            prospect_data={"exists": True},
            catalog=MagicMock(name="catalog"),
        )

    mock_unified.assert_awaited_once_with(
        PHONE_E164, "La Raider 125 es excelente.", phone_number_id=PHONE_NUMBER_ID
    )
    mock_ms.set_human_help_status.assert_not_called()
    mock_ms.save_message.assert_not_called()


# ── PEI-2: HANDOFF_TRIGGERED ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pei2_handoff_triggered_full_flow_without_unified_egress():
    """
    HANDOFF_TRIGGERED: set_human_help_status(True) → ponytail DEPRIORITIZED
    (correlación BOT-PONYTAIL-200) → mensaje de transferencia → notificación al
    equipo. El envío unificado NO se invoca con el prefijo crudo.
    """
    mock_ms = _build_ms_mock()
    mock_unified = AsyncMock(return_value=True)
    mock_sender = AsyncMock(return_value=True)
    mock_notif = MagicMock()
    mock_notif.notify_human_handoff = AsyncMock()

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp._process_and_send_egress_message", mock_unified), \
         patch("app.routers.whatsapp._send_whatsapp_message", mock_sender), \
         patch("app.services.notification_service.notification_service", mock_notif):
        await _pipeline_egress(
            "HANDOFF_TRIGGERED",
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            prospect_data={"exists": True},
            catalog=MagicMock(name="catalog"),
        )

    mock_ms.set_human_help_status.assert_awaited_once_with(PHONE_E164, True)
    ponytail_calls = [
        c for c in mock_ms.update_prospect_summary.await_args_list
        if c.args[2] == {"ponytail_status": "DEPRIORITIZED"}
    ]
    assert ponytail_calls, "Falta ponytail DEPRIORITIZED en el handoff."
    mock_sender.assert_awaited_once()
    assert "transferir con un compañero" in mock_sender.call_args.args[1]
    mock_notif.notify_human_handoff.assert_awaited_once_with(PHONE_E164, "ai_trigger")
    mock_unified.assert_not_called()


# ── PEI-3: PHASE_GATE (moto no confirmada) — imagen dinámica ─────────────────

@pytest.mark.asyncio
async def test_pei3_phase_gate_dynamic_image_injection_and_catalog_seam():
    """
    PHASE_GATE sin moto confirmada: búsqueda en catálogo del interés (o RAIDER 125
    por defecto), envío de imagen con caption "Mira esta {Nombre}\\n\\n{texto}" y
    save(model) — sin envío unificado. La costura catalog usa el kwarg inyectado
    (centinela global intacto) y, sin kwarg, el global parcheado.
    """
    injected_catalog = _build_catalog_with_moto()
    sentinel_catalog = MagicMock(name="global_catalog_sentinel")
    mock_ms = _build_ms_mock()
    mock_unified = AsyncMock(return_value=True)
    mock_image_sender = AsyncMock(return_value=True)

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp._process_and_send_egress_message", mock_unified), \
         patch("app.routers.whatsapp._send_whatsapp_image", mock_image_sender), \
         patch("app.routers.whatsapp.catalog_service", sentinel_catalog):
        await _pipeline_egress(
            "PHASE_GATE_TRIGGERED:Tenemos la Raider lista para ti.",
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            prospect_data={"exists": True, "moto_confirmada": False, "moto_interest": MOTO_NAME},
            catalog=injected_catalog,
        )

    injected_catalog.search_catalog.assert_called_once_with(MOTO_NAME)
    sentinel_catalog.search_catalog.assert_not_called()
    mock_image_sender.assert_awaited_once_with(
        PHONE_E164, MOTO_URL,
        caption=f"Mira esta {MOTO_NAME}\n\nTenemos la Raider lista para ti.",
        phone_number_id=PHONE_NUMBER_ID,
    )
    mock_ms.save_message.assert_awaited_once_with(PHONE_E164, "model", "Tenemos la Raider lista para ti.")
    mock_unified.assert_not_called()

    # Escenario b: sin kwarg catalog, el global parcheado dirige la búsqueda.
    global_catalog = _build_catalog_with_moto()
    mock_ms2 = _build_ms_mock()
    mock_image_sender2 = AsyncMock(return_value=True)
    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms2), \
         patch("app.routers.whatsapp._process_and_send_egress_message", AsyncMock(return_value=True)), \
         patch("app.routers.whatsapp._send_whatsapp_image", mock_image_sender2), \
         patch("app.routers.whatsapp.catalog_service", global_catalog):
        await _pipeline_egress(
            "PHASE_GATE_TRIGGERED:Tenemos la Raider lista para ti.",
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            prospect_data={"exists": True, "moto_confirmada": False, "moto_interest": None},
        )

    global_catalog.search_catalog.assert_called_once_with("RAIDER 125")
    mock_image_sender2.assert_awaited_once()


# ── PEI-4: PHASE_GATE con moto confirmada (bypass) ───────────────────────────

@pytest.mark.asyncio
async def test_pei4_phase_gate_bypass_when_moto_confirmed():
    """
    moto_confirmada=True: bypass de la inyección de imagen; el texto despojado
    del prefijo PHASE_GATE_TRIGGERED se delega al envío unificado.
    """
    mock_ms = _build_ms_mock()
    mock_unified = AsyncMock(return_value=True)
    mock_image_sender = AsyncMock(return_value=True)

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp._process_and_send_egress_message", mock_unified), \
         patch("app.routers.whatsapp._send_whatsapp_image", mock_image_sender):
        await _pipeline_egress(
            "PHASE_GATE_TRIGGERED:Tu Raider 125 te espera.",
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            prospect_data={"exists": True, "moto_confirmada": True},
            catalog=_build_catalog_with_moto(),
        )

    mock_image_sender.assert_not_called()
    mock_unified.assert_awaited_once_with(
        PHONE_E164, "Tu Raider 125 te espera.", phone_number_id=PHONE_NUMBER_ID
    )


# ── PEI-5: Unificación BOT-125 + Visual-Lock (markdown → imagen estrategia A) ─

@pytest.mark.asyncio
async def test_pei5_unified_egress_markdown_visual_lock_and_echo_save():
    """
    El egreso consolidado preserva la unificación BOT-125: texto con Markdown
    ![alt](url) → `_send_whatsapp_image` (estrategia A, caption limpio sin tags)
    y eco save(model) POSTERIOR al envío con el texto limpio. Los patch targets
    de los senders resuelven en tiempo de llamada.
    """
    timeline = []
    mock_ms = _build_ms_mock()

    async def _save(phone, role, content, **kwargs):
        timeline.append(("save", role, content))
        return True

    mock_ms.save_message = AsyncMock(side_effect=_save)

    async def _send_image(phone, url, caption="", phone_number_id=None, **kwargs):
        timeline.append(("send_image", url, caption))
        return True

    mock_image_sender = AsyncMock(side_effect=_send_image)
    mock_text_sender = AsyncMock(return_value=True)
    markdown_text = f"Mira esta {MOTO_NAME}\n\n![{MOTO_NAME}]({MOTO_URL})\n\nPrecio: $9.000.000"

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp._send_whatsapp_image", mock_image_sender), \
         patch("app.routers.whatsapp._send_whatsapp_message", mock_text_sender):
        await _pipeline_egress(
            markdown_text,
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            prospect_data={"exists": True},
            catalog=MagicMock(name="catalog"),
        )

    mock_image_sender.assert_awaited_once()
    _, url, caption = timeline[0]
    assert url == MOTO_URL, f"URL canónica alterada en el egreso: {url!r}"
    assert "![" not in caption and "](" not in caption, (
        f"El caption debía quedar limpio de Markdown (PCC Pro): {caption!r}"
    )
    assert f"Mira esta {MOTO_NAME}" in caption and "Precio: $9.000.000" in caption

    # Eco save(model) intra-egreso: POSTERIOR al envío y con el texto limpio.
    assert [e[0] for e in timeline] == ["send_image", "save"], (
        f"El eco save(model) debía ser posterior al envío: {timeline!r}"
    )
    _, role, saved_text = timeline[1]
    assert role == "model"
    assert "![" not in saved_text and "](" not in saved_text
    mock_text_sender.assert_not_called()
