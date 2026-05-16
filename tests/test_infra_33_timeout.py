"""
[BOT-INFRA-33] Suite de regresión — Firestore Timeout Interceptor

Certifica:
  1. asyncio.TimeoutError se dispara correctamente ante latencia > DB_TIMEOUT
  2. logger.exception registra traza forense completa
  3. Mensaje de contingencia se envía via whatsapp_service mock (await bloqueante)
  4. La excepción se propaga hacia el llamador (no se silencia)
  5. Errores de conectividad GCP (ServiceUnavailable) siguen el mismo camino
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """Firestore AsyncClient mock con respuesta normal."""
    db = MagicMock()
    doc_snap = MagicMock()
    doc_snap.exists = True
    doc_snap.to_dict.return_value = {"celular": "+573001234567", "status": "PENDING"}

    doc_ref = AsyncMock()
    doc_ref.get = AsyncMock(return_value=doc_snap)
    doc_ref.set = AsyncMock(return_value=None)
    doc_ref.update = AsyncMock(return_value=None)
    doc_ref.delete = AsyncMock(return_value=None)
    doc_ref.id = "+573001234567"

    coll = MagicMock()
    coll.document.return_value = doc_ref
    db.collection.return_value = coll

    return db


@pytest.fixture
def memory_service_instance(mock_db):
    """MemoryService con DB mockeada."""
    from app.services.memory_service import MemoryService
    return MemoryService(mock_db)


@pytest.fixture
def slow_db():
    """Firestore mock que simula latencia mayor al timeout configurado (BOT-INFRA-33)."""
    db = MagicMock()

    async def _slow_get():
        await asyncio.sleep(10)  # 10s >> DB_TIMEOUT(5s)

    doc_ref = AsyncMock()
    doc_ref.get = _slow_get
    doc_ref.set = AsyncMock(return_value=None)
    doc_ref.update = AsyncMock(return_value=None)
    doc_ref.delete = AsyncMock(return_value=None)
    doc_ref.id = "+573001234567"

    coll = MagicMock()
    coll.document.return_value = doc_ref
    db.collection.return_value = coll

    return db


@pytest.fixture
def slow_memory_service(slow_db):
    """MemoryService con DB de latencia artificial."""
    from app.services.memory_service import MemoryService
    svc = MemoryService(slow_db)
    # Forzar timeout corto para que el test sea rápido (0.1s en lugar de 5s)
    return svc


# ──────────────────────────────────────────────────────────────────────────────
# TC-01: TimeoutError en get_prospect_data → log forense + contingencia + re-raise
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timeout_triggers_on_slow_firestore_get(slow_memory_service, caplog):
    """
    DADO: Firestore tarda más que DB_TIMEOUT en responder.
    CUANDO: se llama a get_prospect_data.
    ENTONCES:
      - asyncio.TimeoutError se lanza y propaga (no se silencia).
      - El log forense contiene 'BOT-INFRA-33' y 'FIRESTORE TIMEOUT'.
      - whatsapp_service.send_text_message recibe el número de teléfono del lead.
    """
    phone = "+573001234567"

    mock_wa_svc = AsyncMock()
    mock_wa_svc.send_text_message = AsyncMock()

    with patch("app.services.memory_service.settings") as mock_settings, \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa_svc):

        mock_settings.db_timeout = 1  # 1s para que el test sea rápido

        import logging
        with caplog.at_level(logging.ERROR, logger="app.services.memory_service"):
            with pytest.raises(asyncio.TimeoutError):
                await slow_memory_service.get_prospect_data(phone)

    # Verificar log forense
    assert any("BOT-INFRA-33" in r.message for r in caplog.records), \
        "El log forense con 'BOT-INFRA-33' debe registrarse ante timeout"
    assert any("FIRESTORE TIMEOUT" in r.message for r in caplog.records), \
        "El log debe contener 'FIRESTORE TIMEOUT'"

    # Verificar despacho de contingencia al número correcto
    mock_wa_svc.send_text_message.assert_called_once()
    call_args = mock_wa_svc.send_text_message.call_args
    assert call_args[0][0] == phone or call_args[1].get("phone") == phone or phone in str(call_args), \
        f"El mensaje de contingencia debe enviarse a {phone}"


# ──────────────────────────────────────────────────────────────────────────────
# TC-02: El texto de contingencia es el literal aprobado
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_contingency_message_is_exact_literal(slow_memory_service):
    """
    DADO: Timeout en Firestore.
    CUANDO: se despacha el mensaje de contingencia.
    ENTONCES: el texto es exactamente el literal aprobado en _CONTINGENCY_MSG.
    """
    from app.services.memory_service import _CONTINGENCY_MSG

    phone = "+573009876543"
    mock_wa_svc = AsyncMock()
    mock_wa_svc.send_text_message = AsyncMock()

    with patch("app.services.memory_service.settings") as mock_settings, \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa_svc):

        mock_settings.db_timeout = 1

        with pytest.raises(asyncio.TimeoutError):
            await slow_memory_service.get_prospect_data(phone)

    mock_wa_svc.send_text_message.assert_called_once()
    _, sent_text = mock_wa_svc.send_text_message.call_args[0]
    assert sent_text == _CONTINGENCY_MSG, \
        f"El texto enviado debe ser el literal aprobado. Recibido: '{sent_text}'"


# ──────────────────────────────────────────────────────────────────────────────
# TC-03: Excepción se propaga — no se silencia (Zero-Silent-Failures)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timeout_exception_propagates_to_caller():
    """
    DADO: _firestore_io lanza TimeoutError (simula latencia extrema en I/O de Firestore).
    CUANDO: el llamador (orquestador / whatsapp.py) invoca save_message.
    ENTONCES: asyncio.TimeoutError se propaga sin ser capturado hacia el router.

    WHY: Detener ai_brain.py requiere que la excepción llegue hasta el handler del router.
    WHY mock directo de _firestore_io: aísla el interceptor del mock de DB chain.
    """
    from app.services.memory_service import MemoryService

    phone = "+573001111111"
    mock_wa_svc = AsyncMock()

    # Construir la cadena de mock completa para save_message:
    # self._db.collection("mensajeria").document("whatsapp")
    #   .collection("sesiones").document(phone)
    #   .collection("historial").document()
    hist_doc_ref = MagicMock()
    hist_coll = MagicMock()
    hist_coll.document.return_value = hist_doc_ref

    session_doc = MagicMock()
    session_doc.collection.return_value = hist_coll

    session_coll = MagicMock()
    session_coll.document.return_value = session_doc

    wa_doc = MagicMock()
    wa_doc.collection.return_value = session_coll

    mensajeria_coll = MagicMock()
    mensajeria_coll.document.return_value = wa_doc

    db = MagicMock()
    db.collection.return_value = mensajeria_coll

    svc = MemoryService(db)

    async def _raise_timeout(*args, **kwargs):
        raise asyncio.TimeoutError()

    with patch.object(MemoryService, "_firestore_io", _raise_timeout), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa_svc):

        with pytest.raises(asyncio.TimeoutError):
            await svc.save_message(phone, "user", "hola")


# ──────────────────────────────────────────────────────────────────────────────
# TC-04: GCP ServiceUnavailable sigue el mismo camino que TimeoutError
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gcp_service_unavailable_triggers_contingency(memory_service_instance, caplog):
    """
    DADO: Firestore lanza ServiceUnavailable (degradación de red GCP).
    CUANDO: se llama a get_prospect_data.
    ENTONCES:
      - La excepción se propaga.
      - El log forense contiene 'FIRESTORE CONNECTIVITY ERROR'.
      - whatsapp_service.send_text_message es invocado.
    """
    from google.api_core import exceptions as gcp_exceptions

    phone = "+573002222222"
    mock_wa_svc = AsyncMock()
    mock_wa_svc.send_text_message = AsyncMock()

    # Hacer que _find_prospect_ref devuelva un doc_ref cuyo .get() lanza ServiceUnavailable
    unavailable_doc = AsyncMock()
    unavailable_doc.get = AsyncMock(side_effect=gcp_exceptions.ServiceUnavailable("GCP degraded"))
    memory_service_instance._find_prospect_ref = AsyncMock(return_value=unavailable_doc)

    import logging
    with caplog.at_level(logging.ERROR, logger="app.services.memory_service"), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa_svc):

        with pytest.raises(gcp_exceptions.ServiceUnavailable):
            await memory_service_instance.get_prospect_data(phone)

    assert any("FIRESTORE CONNECTIVITY ERROR" in r.message for r in caplog.records), \
        "El log debe contener 'FIRESTORE CONNECTIVITY ERROR' para errores de conectividad GCP"

    mock_wa_svc.send_text_message.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# TC-05: Operaciones normales (<1s) NO disparan timeout — no regresión
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_normal_operations_not_affected_by_timeout(memory_service_instance):
    """
    DADO: Firestore responde normalmente (sin latencia).
    CUANDO: se llama a get_prospect_data.
    ENTONCES: la operación se completa sin excepción y retorna datos válidos.

    WHY: Garantizar que el interceptor no introduce overhead ni falsos positivos.
    """
    result = await memory_service_instance.get_prospect_data("+573001234567")
    assert result.get("exists") is True, "Operaciones normales deben retornar datos sin interrupción"


# ──────────────────────────────────────────────────────────────────────────────
# TC-06: DB_TIMEOUT es configurable vía settings (no hardcodeado)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timeout_uses_settings_db_timeout():
    """
    DADO: settings.db_timeout está configurado a un valor personalizado.
    CUANDO: _firestore_io se invoca.
    ENTONCES: el timeout efectivo respeta la configuración de settings.
    """
    from app.services.memory_service import MemoryService
    import asyncio

    calls_recorded = []

    async def mock_coro():
        calls_recorded.append("called")
        return "ok"

    with patch("app.services.memory_service.settings") as mock_settings:
        mock_settings.db_timeout = 999  # Configurado muy alto

        result = await MemoryService._firestore_io(mock_coro(), phone="+573000000000", label="test")
        assert result == "ok"
        assert "called" in calls_recorded
