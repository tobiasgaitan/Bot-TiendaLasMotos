"""
Integridad del Pipeline Media/Visión — Etapa 3 Wave 05-04
[BOT-BUILD-ETAPA3-WAVE04-FRAGMENT-MEDIA-AUDIO-001]

Pins de paridad pre/post extracción de `_pipeline_media_vision` (sprout method
intra-archivo extraído del God Node; el cuerpo se movió VERBATIM). Certifican que
el comportamiento post-extracción es idéntico al pre-extracción pineado por las
waves 05-01 (E2E-IMAGE / ORDER-IMAGE) y 05-03 (DI-2/3/4/8).

  MVI-1  Paridad VisionService: la factoría se invoca UNA vez por llamada con el
         db_client resuelto (instanciación por llamada — no singleton) y
         analyze_image recibe los mismos argumentos (bytes, mime, phone, caption,
         catalog_items).
  MVI-2  Paridad de escrituras Firestore: update_prospect_summary(moto_interest +
         ponytail PENDING) ≺ pensar_respuesta ≺ egreso Meta (invariante CH-5).
  MVI-3  Visual-Lock PCC Pro intacto: Markdown ![Nombre](URL) + precio canónico
         anclado ("$" + "(incluye SOAT, Matrícula, y tramites)") inyectados cuando
         el LLM los omite.
  MVI-4  Patch targets heredados vigentes: sin kwargs, los globals VisionService /
         db / catalog_service parcheados dirigen el flujo.
  MVI-5  Cableado del orquestador: la rama media del impl delega en el pipeline
         (propagación de costuras + ctx) y preserva el EARLY EXIT (la gestión de
         sesión CRM no se alcanza para payloads media).
"""
import random
import re

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks

from app.routers.whatsapp import (
    _handle_message_background_impl,
    _pipeline_media_vision,
)
from tests.factories import make_catalog_item, format_cop

PHONE_E164 = "+573192564288"
PHONE_RAW = "573192564288"
PHONE_NUMBER_ID = "999999"
ANCHOR = "(incluye SOAT, Matrícula, y tramites)"


# ── Builders ──────────────────────────────────────────────────────────────────

def _image_payload(caption: str = "") -> dict:
    return {
        "from": PHONE_RAW,
        "id": "wamid.mvi",
        "type": "image",
        "phone_number_id": PHONE_NUMBER_ID,
        "image": {"id": "media-mvi-1", "mime_type": "image/jpeg", "caption": caption},
    }


def _build_ms_mock(timeline: list | None = None, prospect: dict | None = None) -> MagicMock:
    prospect = prospect or {
        "exists": True,
        "status": "IN_PROGRESS",
        "chatbot_status": "ACTIVE",
        "name": "Juan Test",
        "celular": PHONE_E164,
        "ai_summary": "Resumen previo",
        "human_help_requested": False,
    }
    ms = MagicMock()
    ms.create_prospect_if_missing = AsyncMock()
    ms.update_last_interaction = AsyncMock()
    ms.transition_to_in_progress = AsyncMock()
    ms.generate_and_update_summary = AsyncMock()
    ms.save_message = AsyncMock()
    ms.set_human_help_status = AsyncMock()
    ms.delete_prospect_completely = AsyncMock(return_value=True)
    ms.get_or_create_prospect = AsyncMock(return_value=prospect)
    ms.get_prospect_data = AsyncMock(return_value=prospect)
    ms.get_chat_history = AsyncMock(return_value=[])

    if timeline is not None:
        async def _ups(phone, text, fields, **kwargs):
            timeline.append(("update_prospect_summary", fields))
            return True

        ms.update_prospect_summary = AsyncMock(side_effect=_ups)

        async def _save(phone, role, content, **kwargs):
            timeline.append((f"save_message:{role}", content))
            return True

        ms.save_message = AsyncMock(side_effect=_save)
    else:
        ms.update_prospect_summary = AsyncMock()
    return ms


def _build_matched_item() -> tuple[dict, dict, str]:
    item = make_catalog_item(1, random.Random(2026))
    canonical_price = format_cop(item["price"])
    matched = {
        "id": item["id"],
        "name": item["name"],
        "image_url": item["image_url"],
        "price": item["price"],
        "formatted_price": canonical_price,
        "summary": item["summary"],
        "active": True,
    }
    return item, matched, canonical_price


def _run_moto_image_pipeline(timeline: list) -> dict:
    """Arnés compartido de la ruta moto: devuelve los mocks y el texto de egreso."""
    item, matched, canonical_price = _build_matched_item()
    mock_ms = _build_ms_mock(timeline)
    mock_cerebro = MagicMock()

    async def _pensar(*args, **kwargs):
        timeline.append(("pensar_respuesta", None))
        # Respuesta deliberadamente SIN imagen ni precio → el Visual Lock debe inyectarlos.
        return f"Claro, la {item['name']} es una dura."

    mock_cerebro.pensar_respuesta = AsyncMock(side_effect=_pensar)
    mock_vision = MagicMock()
    mock_vision.analyze_image = AsyncMock(return_value=f"MOTO_DETECTADA: {item['name']}")
    mock_catalog = MagicMock()
    mock_catalog.get_vision_catalog_projection = MagicMock(return_value=[])
    mock_catalog.match_catalog_item_by_image = MagicMock(return_value=matched)
    mock_catalog._rehydrate_formatted_price = MagicMock(return_value=canonical_price)
    mock_storage = MagicMock()
    mock_storage.download_media = AsyncMock(return_value=b"fake_image_bytes")

    captured = {}

    async def _egress(phone, text, phone_number_id=None, **kwargs):
        timeline.append(("egress", text))
        captured["text"] = text
        return True

    mocks = {
        "ms": mock_ms, "cerebro": mock_cerebro, "vision": mock_vision,
        "catalog": mock_catalog, "storage": mock_storage, "captured": captured,
        "matched": matched, "canonical_price": canonical_price, "item": item,
    }
    patches = (
        patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock),
        patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms),
        patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro),
        patch("app.routers.whatsapp.storage_service", mock_storage),
        patch("app.routers.whatsapp.catalog_service", mock_catalog),
        patch("app.routers.whatsapp.VisionService", return_value=mock_vision),
        patch("app.routers.whatsapp.db", MagicMock(name="global_db")),
        patch("app.routers.whatsapp._process_and_send_egress_message", AsyncMock(side_effect=_egress)),
        patch("app.routers.whatsapp._send_whatsapp_message", AsyncMock(return_value=True)),
    )
    mocks["patches"] = patches
    return mocks


# ── MVI-1: Paridad VisionService (argumentos + frecuencia + por llamada) ──────

@pytest.mark.asyncio
async def test_mvi1_vision_service_call_parity_and_per_call_instantiation():
    """
    La factoría de visión se invoca exactamente UNA vez POR LLAMADA al pipeline con
    el db_client resuelto, y analyze_image recibe los argumentos heredados exactos.
    Dos invocaciones consecutivas ⇒ dos instanciaciones (no singleton).
    """
    payload = _image_payload(caption="foto moto")
    for call_number in (1, 2):
        mock_vision = MagicMock()
        mock_vision.analyze_image = AsyncMock(side_effect=RuntimeError("short-circuit"))
        injected_factory = MagicMock(name="injected_vision_factory", return_value=mock_vision)
        injected_db = MagicMock(name="injected_db")
        injected_catalog = MagicMock(name="injected_catalog")
        injected_catalog.get_vision_catalog_projection = MagicMock(return_value=["p1", "p2"])
        sentinel_factory = MagicMock(name="global_VisionService_sentinel")
        sentinel_db = MagicMock(name="global_db_sentinel")

        with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
             patch("app.routers.whatsapp.memory_service_module.memory_service", None), \
             patch("app.routers.whatsapp.storage_service") as mock_storage, \
             patch("app.routers.whatsapp.VisionService", sentinel_factory), \
             patch("app.routers.whatsapp.catalog_service", MagicMock(name="catalog_sentinel")), \
             patch("app.routers.whatsapp.db", sentinel_db), \
             patch("app.routers.whatsapp._send_whatsapp_message", AsyncMock(return_value=True)):
            mock_storage.download_media = AsyncMock(return_value=b"img-bytes")

            await _pipeline_media_vision(
                payload,
                vision_factory=injected_factory,
                db_client=injected_db,
                catalog=injected_catalog,
                user_phone=PHONE_E164,
                msg_type="image",
                phone_number_id=PHONE_NUMBER_ID,
            )

        injected_factory.assert_called_once_with(injected_db)
        sentinel_factory.assert_not_called()
        mock_vision.analyze_image.assert_awaited_once_with(
            b"img-bytes", "image/jpeg", PHONE_E164, caption="foto moto", catalog_items=["p1", "p2"]
        ), f"Argumentos de analyze_image alterados en la llamada #{call_number}"


# ── MVI-2: Paridad escrituras Firestore (orden CH-5) ──────────────────────────

@pytest.mark.asyncio
async def test_mvi2_firestore_writes_parity_and_state_precedes_egress():
    """
    Ruta moto: persistencia bloqueante del match (moto_interest + ponytail PENDING)
    precede a la inferencia y al egreso — el orden transaccional pineado por
    ORDER-IMAGE (Wave 05-01) se preserva tras la extracción.
    """
    timeline = []
    mocks = _run_moto_image_pipeline(timeline)
    with mocks["patches"][0], mocks["patches"][1], mocks["patches"][2], mocks["patches"][3], \
         mocks["patches"][4], mocks["patches"][5], mocks["patches"][6], mocks["patches"][7], \
         mocks["patches"][8]:
        await _pipeline_media_vision(
            _image_payload(),
            user_phone=PHONE_E164,
            msg_type="image",
            phone_number_id=PHONE_NUMBER_ID,
        )

    labels = [label for label, _ in timeline]
    # Escrituras Firestore pineadas
    ups_calls = [fields for label, fields in timeline if label == "update_prospect_summary"]
    assert ups_calls, f"update_prospect_summary nunca se invocó. Timeline: {labels}"
    assert ups_calls[0] == {
        "moto_interest": mocks["matched"]["name"],
        "ponytail_status": "PENDING",
    }, f"Payload de update_prospect_summary alterado: {ups_calls[0]!r}"

    # Invariante CH-5: escritura de estado ≺ inferencia ≺ egreso Meta.
    i_ups = labels.index("update_prospect_summary")
    i_pensar = labels.index("pensar_respuesta")
    i_egress = labels.index("egress")
    assert i_ups < i_pensar < i_egress, (
        f"VIOLACIÓN CH-5 post-extracción: orden {labels}. "
        "Se exige update_prospect_summary ≺ pensar_respuesta ≺ egreso."
    )
    # save(user) del mensaje simulado también precede al egreso.
    assert "save_message:user" in labels and labels.index("save_message:user") < i_egress


# ── MVI-3: Visual-Lock PCC Pro intacto ────────────────────────────────────────

@pytest.mark.asyncio
async def test_mvi3_visual_lock_pcc_pro_intact():
    """
    El LLM omite imagen y precio: el Visual Lock post-generación inyecta el Markdown
    canónico ![Nombre](URL) y el precio anclado ($ + anchor de paquete) — formato
    PCC Pro byte-compatible con el comportamiento pre-extracción.
    """
    timeline = []
    mocks = _run_moto_image_pipeline(timeline)
    with mocks["patches"][0], mocks["patches"][1], mocks["patches"][2], mocks["patches"][3], \
         mocks["patches"][4], mocks["patches"][5], mocks["patches"][6], mocks["patches"][7], \
         mocks["patches"][8]:
        await _pipeline_media_vision(
            _image_payload(),
            user_phone=PHONE_E164,
            msg_type="image",
            phone_number_id=PHONE_NUMBER_ID,
        )

    egress_text = mocks["captured"].get("text", "")
    matched = mocks["matched"]
    assert re.search(r"!\[.+?\]\(https?://[^\s\)]+\)", egress_text), (
        f"Visual-Lock roto: falta Markdown de imagen canónica en el egreso: {egress_text!r}"
    )
    assert f"![{matched['name']}]({matched['image_url']})" in egress_text, (
        f"El Markdown no referencia el ítem canónico: {egress_text!r}"
    )
    expected_price = f"{mocks['canonical_price']} {ANCHOR}"
    assert f"Precio: {expected_price}" in egress_text, (
        f"Visual-Lock roto: falta el precio canónico anclado {expected_price!r} "
        f"en el egreso: {egress_text!r}"
    )
    assert "$" in egress_text, "Símbolo monetario ausente en el egreso (PCC Pro)."


# ── MVI-4: Patch targets heredados vigentes (sin kwargs) ─────────────────────

@pytest.mark.asyncio
async def test_mvi4_patch_targets_survive_without_kwargs():
    """
    Sin kwargs, los globals del módulo parcheados (VisionService, db, catalog_service)
    dirigen el flujo del pipeline — la resolución runtime preserva los 12 patch
    targets de VisionService y los 35 de db heredados.
    """
    mock_vision = MagicMock()
    mock_vision.analyze_image = AsyncMock(side_effect=RuntimeError("short-circuit"))
    global_factory = MagicMock(name="patched_VisionService", return_value=mock_vision)
    global_db = MagicMock(name="patched_db")
    global_catalog = MagicMock(name="patched_catalog")
    global_catalog.get_vision_catalog_projection = MagicMock(return_value=[])

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", None), \
         patch("app.routers.whatsapp.storage_service") as mock_storage, \
         patch("app.routers.whatsapp.VisionService", global_factory), \
         patch("app.routers.whatsapp.catalog_service", global_catalog), \
         patch("app.routers.whatsapp.db", global_db), \
         patch("app.routers.whatsapp._send_whatsapp_message", AsyncMock(return_value=True)):
        mock_storage.download_media = AsyncMock(return_value=b"img-bytes")

        await _pipeline_media_vision(
            _image_payload(),
            user_phone=PHONE_E164,
            msg_type="image",
            phone_number_id=PHONE_NUMBER_ID,
        )

    global_factory.assert_called_once_with(global_db)
    global_catalog.get_vision_catalog_projection.assert_called_once()
    mock_vision.analyze_image.assert_awaited_once()


# ── MVI-5: Cableado del orquestador (delegación + EARLY EXIT) ────────────────

@pytest.mark.asyncio
async def test_mvi5_orchestrator_delegates_media_branch_with_seam_propagation():
    """
    La rama media del impl delega en `_pipeline_media_vision` propagando las costuras
    resueltas (catalog/vision_factory/db_client/meta_sender) y el ctx (user_phone,
    msg_type, phone_number_id). Tras la delegación, el impl hace EARLY EXIT: la
    gestión de sesión CRM (get_prospect_data) jamás se alcanza para payloads media.
    """
    mock_pipeline = AsyncMock(name="patched__pipeline_media_vision")
    mock_ms = _build_ms_mock()
    mock_wa = MagicMock()
    mock_wa.mark_as_read = AsyncMock()
    mock_catalog_global = MagicMock(name="global_catalog")
    mock_vision_global = MagicMock(name="global_VisionService")
    mock_db_global = MagicMock(name="global_db")

    buffer = MagicMock()
    buffer.add_message = AsyncMock(return_value=True)
    buffer.clear_messages = AsyncMock()

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp._pipeline_media_vision", mock_pipeline), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog_global), \
         patch("app.routers.whatsapp.VisionService", mock_vision_global), \
         patch("app.routers.whatsapp.db", mock_db_global), \
         patch("app.routers.whatsapp.message_buffer", buffer):

        payload = _image_payload()
        await _handle_message_background_impl(payload, BackgroundTasks())

    mock_pipeline.assert_awaited_once()
    call = mock_pipeline.call_args
    assert call.args[0] is payload, "El payload no se propagó posicionalmente."
    assert call.kwargs["catalog"] is mock_catalog_global
    assert call.kwargs["vision_factory"] is mock_vision_global
    assert call.kwargs["db_client"] is mock_db_global
    assert call.kwargs["meta_sender"] is mock_wa, (
        "El meta_sender resuelto (import diferido → singleton parcheado) no se propagó."
    )
    assert call.kwargs["user_phone"] == PHONE_E164
    assert call.kwargs["msg_type"] == "image"
    assert call.kwargs["phone_number_id"] == PHONE_NUMBER_ID

    # EARLY EXIT: la sesión CRM nunca se abre para media.
    mock_ms.get_prospect_data.assert_not_called()
    mock_ms.create_prospect_if_missing.assert_not_called()
