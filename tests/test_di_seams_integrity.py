"""
Integridad de Costuras DI — Etapa 3 Wave 05-03 [BOT-BUILD-ETAPA3-WAVE03-DI-SEAMS-001]

Verifica que los kwargs opcionales inyectados en los pipelines del God Node
(`_handle_message_background_impl`) y en los pipelines internos de egreso resuelven
correctamente los globals del módulo EN TIEMPO DE LLAMADA (nunca en def-time).

Patrón certificado (sprout_method_optional_deps):
  catalog=None        -> catalog or catalog_service
  vision_factory=None -> vision_factory or VisionService   (factoría: instanciación por llamada)
  db_client=None      -> db_client or db
  meta_sender=None    -> meta_sender or whatsapp_service   (import diferido preservado)

Pins de este archivo:
  DI-1  Firma: los 4 kwargs del God Node son keyword-only con default None
        (un default=global en firma = binding en def-time = monkeypatch roto).
        Las firmas públicas (webhook_handler, task_processor,
        _handle_message_background) NO fueron tocadas (constraint del ticket).
  DI-2  Rama TEXT: catalog inyectado se usa en lugar del global (juez/aliases).
  DI-3  Rama IMAGE: vision_factory inyectado se invoca en lugar de VisionService(db).
  DI-4  Rama IMAGE: db_client inyectado es el argumento de la factoría (identidad),
        no el global db.
  DI-5  Rama RESET: meta_sender inyectado emite la confirmación en lugar de
        whatsapp_service.
  DI-6  Helpers de egreso (_send_whatsapp_message / _send_whatsapp_image):
        meta_sender inyectado tiene prioridad; None cae al singleton diferido.
  DI-7  resolve_query_aliases: catalog como kwarg y fallback al global.
  DI-8  REGRESIÓN de patch targets: sin kwargs, los 25 patch targets heredados
        (catalog_service / VisionService / db / whatsapp_service) siguen
        dirigiendo el flujo — prueba de que la resolución es en tiempo de llamada.

Nota BOT-174 (mandato Wave 05-01): todo test que alcance el guard de inferencia
configura `ms.get_or_create_prospect = AsyncMock(...)` explícito — inmune a la
polución de identidad de clases Mock del contaminante heredado.
"""
import inspect

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks

from app.routers import whatsapp as wa_module
from app.routers.whatsapp import (
    _handle_message_background_impl,
    _send_whatsapp_image,
    _send_whatsapp_message,
    resolve_query_aliases,
)

PHONE_E164 = "+573192564288"
PHONE_RAW = "573192564288"
PHONE_NUMBER_ID = "999999"


# ── Builders de mocks (patrón canónico Wave 05-01) ────────────────────────────

def _build_ms_mock(prospect: dict | None = None) -> MagicMock:
    """MemoryService mockeado con superficie completa.

    WHY get_or_create_prospect explícito: inmunización BOT-174 sancionada por el
    propio guard (ver PYTEST-AUTOPSY-WAVE01.md §3 — polución de identidad Mock).
    """
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
    ms.update_prospect_summary = AsyncMock()
    ms.delete_prospect_completely = AsyncMock(return_value=True)
    ms.reset_phase_latches = AsyncMock(return_value=True)
    ms.get_or_create_prospect = AsyncMock(return_value=prospect)
    ms.get_prospect_data = AsyncMock(return_value=prospect)
    ms.get_chat_history = AsyncMock(return_value=[])
    return ms


def _build_buffer_mock() -> MagicMock:
    buffer = MagicMock()
    buffer.add_message = AsyncMock(return_value=True)
    buffer.is_task_active = MagicMock(return_value=True)
    buffer.get_aggregated_message = AsyncMock(return_value=None)
    buffer.clear_buffer = AsyncMock()
    buffer.debounce_seconds = 0.01
    return buffer


def _build_wa_mock() -> MagicMock:
    wa = MagicMock()
    wa.mark_as_read = AsyncMock()
    wa.send_text_message = AsyncMock()
    wa.send_image_message = AsyncMock()
    return wa


def _image_msg() -> dict:
    return {
        "from": PHONE_RAW,
        "id": "wamid.di_image",
        "type": "image",
        "phone_number_id": PHONE_NUMBER_ID,
        "image": {"id": "media-di-1", "mime_type": "image/jpeg"},
    }


def _build_image_harness() -> dict:
    """Arnés de la rama IMAGE con cortocircuito controlado: analyze_image explota
    y el flujo termina por el manejador de contingencia (egreso real mockeado a
    nivel servicio). Permite aislar las costuras vision_factory/db_client/catalog.
    """
    mock_storage = MagicMock()
    mock_storage.download_media = AsyncMock(return_value=b"img-bytes")
    mock_vision = MagicMock()
    mock_vision.analyze_image = AsyncMock(side_effect=RuntimeError("vision boom (DI harness)"))
    return {
        "storage": mock_storage,
        "vision": mock_vision,
        "wa_source": _build_wa_mock(),
        "buffer": _build_buffer_mock(),
    }


# ── DI-1: Firma (anti-binding en def-time + constraint de firmas públicas) ────

def test_di_seams_signature_none_defaults_and_public_signatures_untouched():
    """
    Pin estático de la costura: los 4 kwargs del God Node existen, son
    keyword-only y su default es None (resolución runtime). Un default=global
    en firma fijaría el objeto en def-time y rompería los 25 patch targets.
    Además, los helpers de egreso y resolve_query_aliases exponen su costura,
    y las firmas públicas del ticket quedan intactas.
    """
    sig = inspect.signature(_handle_message_background_impl)
    for name in ("catalog", "vision_factory", "db_client", "meta_sender"):
        assert name in sig.parameters, f"Falta la costura {name!r} en el God Node"
        param = sig.parameters[name]
        assert param.default is None, (
            f"VIOLACIÓN def-time: {name} tiene default {param.default!r}; "
            "debe ser None para resolver el global en tiempo de llamada."
        )
        assert param.kind is inspect.Parameter.KEYWORD_ONLY, (
            f"{name} debe ser keyword-only (estabilidad de llamadas posicionales heredadas)."
        )

    for fn in (_send_whatsapp_message, _send_whatsapp_image):
        param = inspect.signature(fn).parameters["meta_sender"]
        assert param.default is None
        assert param.kind is inspect.Parameter.KEYWORD_ONLY

    param = inspect.signature(resolve_query_aliases).parameters["catalog"]
    assert param.default is None

    # Constraint del ticket: firmas públicas intactas (sin las nuevas costuras).
    for fn_name in ("webhook_handler", "task_processor", "_handle_message_background"):
        public_sig = inspect.signature(getattr(wa_module, fn_name))
        for seam in ("catalog", "vision_factory", "db_client", "meta_sender"):
            assert seam not in public_sig.parameters, (
                f"La firma pública {fn_name} fue modificada con la costura {seam!r} "
                "(prohibido por el ticket)."
            )


# ── DI-2: catalog inyectado (rama TEXT) ───────────────────────────────────────

@pytest.mark.asyncio
async def test_catalog_kwarg_overrides_global_catalog_service_in_text_branch():
    """
    Rama TEXT: el mock de catalog_service pasado como kwarg es usado por el
    contexto del Juez (catalog.search) y por resolve_query_aliases, en lugar
    del global del módulo (parcheado con un centinela que jamás debe tocarse).
    """
    mock_ms = _build_ms_mock()
    mock_wa = _build_wa_mock()
    mock_cerebro = MagicMock()
    mock_cerebro.pensar_respuesta = AsyncMock(return_value="Respuesta aprobada del bot.")
    mock_judge = MagicMock()
    mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

    injected_catalog = MagicMock(name="injected_catalog")
    injected_catalog.search = MagicMock(return_value=[])
    sentinel_catalog = MagicMock(name="global_catalog_sentinel")
    sentinel_catalog.search = MagicMock(return_value=[])

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=mock_cerebro), \
         patch("app.routers.whatsapp.judge_service", mock_judge), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa), \
         patch("app.routers.whatsapp.catalog_service", sentinel_catalog), \
         patch("app.routers.whatsapp.message_buffer", _build_buffer_mock()), \
         patch("app.routers.whatsapp.db", MagicMock(name="global_db")), \
         patch("app.routers.whatsapp._process_and_send_egress_message", new_callable=AsyncMock):

        msg_payload = {
            "from": PHONE_RAW,
            "id": "wamid.di_catalog",
            "type": "text",
            "phone_number_id": PHONE_NUMBER_ID,
            "text": "Quiero una moto económica",
        }
        await _handle_message_background_impl(msg_payload, BackgroundTasks(), catalog=injected_catalog)

    injected_catalog.search.assert_called()
    sentinel_catalog.search.assert_not_called()


# ── DI-3: vision_factory inyectado (rama IMAGE) ───────────────────────────────

@pytest.mark.asyncio
async def test_vision_factory_kwarg_overrides_global_vision_service_in_image_branch():
    """
    Rama IMAGE: el mock de vision_factory pasado como kwarg es invocado (una
    sola vez, preservando la instanciación por llamada) en lugar de
    VisionService(db) — el global parcheado queda intacto.
    """
    harness = _build_image_harness()
    injected_factory = MagicMock(name="injected_vision_factory", return_value=harness["vision"])
    sentinel_factory = MagicMock(name="global_VisionService_sentinel")
    injected_catalog = MagicMock(name="injected_catalog")
    injected_catalog.get_vision_catalog_projection = MagicMock(return_value=[])
    sentinel_catalog = MagicMock(name="global_catalog_sentinel")
    mock_db = MagicMock(name="injected_db")
    mock_meta = _build_wa_mock()

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", None), \
         patch("app.routers.whatsapp.storage_service", harness["storage"]), \
         patch("app.routers.whatsapp.VisionService", sentinel_factory), \
         patch("app.routers.whatsapp.catalog_service", sentinel_catalog), \
         patch("app.routers.whatsapp.db", MagicMock(name="global_db_sentinel")), \
         patch("app.services.whatsapp_service.whatsapp_service", harness["wa_source"]), \
         patch("app.routers.whatsapp.message_buffer", harness["buffer"]):

        await _handle_message_background_impl(
            _image_msg(),
            BackgroundTasks(),
            catalog=injected_catalog,
            vision_factory=injected_factory,
            db_client=mock_db,
            meta_sender=mock_meta,
        )

    injected_factory.assert_called_once_with(mock_db)
    sentinel_factory.assert_not_called()
    harness["vision"].analyze_image.assert_awaited_once()
    injected_catalog.get_vision_catalog_projection.assert_called_once()
    sentinel_catalog.get_vision_catalog_projection.assert_not_called()


# ── DI-4: db_client inyectado (rama IMAGE, identidad del argumento) ───────────

@pytest.mark.asyncio
async def test_db_client_kwarg_overrides_global_db_in_image_branch():
    """
    Rama IMAGE: el mock de db_client pasado como kwarg es el argumento recibido
    por la factoría de visión (identidad estricta), NO el global db del módulo.
    """
    harness = _build_image_harness()
    injected_factory = MagicMock(name="injected_vision_factory", return_value=harness["vision"])
    injected_catalog = MagicMock(name="injected_catalog")
    injected_catalog.get_vision_catalog_projection = MagicMock(return_value=[])
    mock_db = MagicMock(name="injected_db_client")
    global_db_sentinel = MagicMock(name="global_db_sentinel")
    mock_meta = _build_wa_mock()

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", None), \
         patch("app.routers.whatsapp.storage_service", harness["storage"]), \
         patch("app.routers.whatsapp.catalog_service", MagicMock(name="global_catalog_sentinel")), \
         patch("app.routers.whatsapp.db", global_db_sentinel), \
         patch("app.services.whatsapp_service.whatsapp_service", harness["wa_source"]), \
         patch("app.routers.whatsapp.message_buffer", harness["buffer"]):

        await _handle_message_background_impl(
            _image_msg(),
            BackgroundTasks(),
            catalog=injected_catalog,
            vision_factory=injected_factory,
            db_client=mock_db,
            meta_sender=mock_meta,
        )

    factory_arg = injected_factory.call_args[0][0]
    assert factory_arg is mock_db, "La factoría no recibió el db_client inyectado."
    assert factory_arg is not global_db_sentinel, (
        "VIOLACIÓN de costura: la factoría recibió el global db pese al kwarg inyectado."
    )


# ── DI-5: meta_sender inyectado (rama RESET) ──────────────────────────────────

@pytest.mark.asyncio
async def test_meta_sender_kwarg_overrides_whatsapp_service_in_reset_branch():
    """
    Rama RESET: el mock de meta_sender pasado como kwarg emite tanto el acuse
    READ-FIRST (mark_as_read) como la confirmación de reinicio
    (send_text_message), en lugar del singleton whatsapp_service (parcheado con
    un centinela que jamás debe tocarse).
    """
    mock_ms = _build_ms_mock()
    sentinel_wa = _build_wa_mock()
    mock_meta = _build_wa_mock()

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.services.whatsapp_service.whatsapp_service", sentinel_wa), \
         patch("app.routers.whatsapp.message_buffer", _build_buffer_mock()):

        msg_payload = {
            "from": PHONE_RAW,
            "id": "wamid.di_reset",
            "type": "text",
            "phone_number_id": PHONE_NUMBER_ID,
            "text": "/reset",
        }
        await _handle_message_background_impl(msg_payload, BackgroundTasks(), meta_sender=mock_meta)

    mock_meta.mark_as_read.assert_awaited_once()
    mock_meta.send_text_message.assert_awaited_once()
    sentinel_wa.mark_as_read.assert_not_called()
    sentinel_wa.send_text_message.assert_not_called()


# ── DI-6: meta_sender en helpers de egreso ────────────────────────────────────

@pytest.mark.asyncio
async def test_meta_sender_kwarg_in_sender_helpers_and_global_fallback():
    """
    _send_whatsapp_message / _send_whatsapp_image: el kwarg meta_sender tiene
    prioridad sobre el singleton diferido; con meta_sender=None el import
    diferido de whatsapp_service resuelve en tiempo de llamada (patch vigente).
    """
    mock_meta = _build_wa_mock()
    sentinel_wa = _build_wa_mock()

    with patch("app.services.whatsapp_service.whatsapp_service", sentinel_wa):
        ok_text = await _send_whatsapp_message(
            PHONE_E164, "hola", phone_number_id=PHONE_NUMBER_ID, meta_sender=mock_meta
        )
        ok_image = await _send_whatsapp_image(
            PHONE_E164, "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/x.png?alt=media", caption="cap", phone_number_id=PHONE_NUMBER_ID,
            meta_sender=mock_meta,
        )

    assert ok_text is True and ok_image is True
    mock_meta.send_text_message.assert_awaited_once_with(PHONE_E164, "hola", phone_number_id=PHONE_NUMBER_ID)
    mock_meta.send_image_message.assert_awaited_once_with(PHONE_E164, "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/x.png?alt=media", "cap", phone_number_id=PHONE_NUMBER_ID)
    sentinel_wa.send_text_message.assert_not_called()
    sentinel_wa.send_image_message.assert_not_called()

    # Fallback: sin kwarg, el singleton diferido (parcheado) resuelve en tiempo de llamada.
    with patch("app.services.whatsapp_service.whatsapp_service", sentinel_wa):
        await _send_whatsapp_message(PHONE_E164, "hola2", phone_number_id=PHONE_NUMBER_ID)
        await _send_whatsapp_image(PHONE_E164, "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/y.png?alt=media", caption="cap2", phone_number_id=PHONE_NUMBER_ID)
    sentinel_wa.send_text_message.assert_awaited_once_with(PHONE_E164, "hola2", phone_number_id=PHONE_NUMBER_ID)
    sentinel_wa.send_image_message.assert_awaited_once_with(PHONE_E164, "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos-documents/o/y.png?alt=media", "cap2", phone_number_id=PHONE_NUMBER_ID)


# ── DI-7: resolve_query_aliases (kwarg + fallback global) ─────────────────────

def test_resolve_query_aliases_catalog_kwarg_and_global_fallback():
    """
    resolve_query_aliases: el catalog pasado (kwarg o posicional — paridad
    heredada) se usa para los aliases; con catalog=None se resuelve el global
    del módulo en tiempo de llamada.
    """
    aliases = {"semiautomatica": ["señoritera"]}
    injected_catalog = MagicMock(name="injected_catalog")
    injected_catalog.get_catalog_aliases = MagicMock(return_value=aliases)

    assert resolve_query_aliases("quiero una señoritera", catalog=injected_catalog) == "semiautomatica"
    injected_catalog.get_catalog_aliases.assert_called_once()

    # Paridad posicional heredada (2º argumento).
    injected_catalog.get_catalog_aliases.reset_mock()
    assert resolve_query_aliases("quiero una señoritera", injected_catalog) == "semiautomatica"
    injected_catalog.get_catalog_aliases.assert_called_once()

    # Fallback al global del módulo (resolución runtime del patch target).
    global_catalog = MagicMock(name="global_catalog")
    global_catalog.get_catalog_aliases = MagicMock(return_value=aliases)
    with patch("app.routers.whatsapp.catalog_service", global_catalog):
        assert resolve_query_aliases("quiero una señoritera") == "semiautomatica"
    global_catalog.get_catalog_aliases.assert_called_once()


# ── DI-8: REGRESIÓN — patch targets vigentes sin kwargs ──────────────────────

@pytest.mark.asyncio
async def test_patch_targets_regression_without_kwargs_image_branch():
    """
    Regresión de los 25 patch targets: SIN kwargs, los globals parcheados en
    `app.routers.whatsapp` (VisionService, db, catalog_service) y en el módulo
    fuente (whatsapp_service) siguen dirigiendo el flujo — prueba de que la
    resolución de las costuras ocurre en tiempo de llamada y no en def-time.
    """
    harness = _build_image_harness()
    global_factory = MagicMock(name="patched_VisionService", return_value=harness["vision"])
    global_db = MagicMock(name="patched_db")
    global_catalog = MagicMock(name="patched_catalog")
    global_catalog.get_vision_catalog_projection = MagicMock(return_value=[])

    with patch("app.routers.whatsapp._ensure_services", new_callable=AsyncMock), \
         patch("app.routers.whatsapp.memory_service_module.memory_service", None), \
         patch("app.routers.whatsapp.storage_service", harness["storage"]), \
         patch("app.routers.whatsapp.VisionService", global_factory), \
         patch("app.routers.whatsapp.catalog_service", global_catalog), \
         patch("app.routers.whatsapp.db", global_db), \
         patch("app.services.whatsapp_service.whatsapp_service", harness["wa_source"]), \
         patch("app.routers.whatsapp.message_buffer", harness["buffer"]):

        await _handle_message_background_impl(_image_msg(), BackgroundTasks())

    global_factory.assert_called_once_with(global_db)
    global_catalog.get_vision_catalog_projection.assert_called_once()
    harness["wa_source"].mark_as_read.assert_awaited_once()
    # Cortocircuito de contingencia: egreso de error a través del singleton parcheado.
    harness["wa_source"].send_text_message.assert_awaited_once()
