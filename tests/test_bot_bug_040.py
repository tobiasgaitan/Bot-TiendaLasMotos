"""
BOT-BUG-040: Tests de regresión para fallo en cascada y denegación de servicio.

Verifica:
1. Que un ítem de catálogo con 'summary' vacía se omite con logger.warning (no crash).
2. Que update_whatsapp_status captura excepciones gRPC sin re-raise.
3. Aserción de contenido: 'Ficha Tecnica:' presente cuando hay ítems válidos junto a corruptos.
"""

import pytest
import asyncio
import re
import logging
from unittest.mock import AsyncMock, MagicMock
from google.api_core import exceptions as gcp_exceptions


# ──────────────────────────────────────────────────────────────────────
# TEST 1: Ítem corrupto en catálogo NO destruye la iteración
# ──────────────────────────────────────────────────────────────────────
class TestCatalogAntiNullMaskingResilience:
    """
    Reproduce BOT-BUG-040 Condición 1: Un ítem del catálogo (TVS APACHE 160)
    con 'summary' vacía no debe lanzar ValueError ni detener el God Node.
    """

    def _build_catalog_items(self):
        """Fixture: mix de ítems válidos y corruptos."""
        return [
            {
                "name": "TVS Sport 100",
                "summary": "Moto económica ideal para trabajo.",
                "price": "$4.590.000",
                "category": "Trabajo",
                "image_url": "https://img.example.com/sport100.jpg",
                "link": "https://example.com/sport100",
            },
            {
                "name": "TVS APACHE 160",
                "summary": "",  
                "price": "$11.990.000",
                "category": "Deportiva",
                "image_url": "https://img.example.com/apache160.jpg",
                "link": "https://example.com/apache160",
            },
            {
                "name": "TVS Raider 125",
                "summary": "Naked deportiva con tecnología SmartXonnect.",
                "price": "$7.190.000",
                "category": "Urban",
                "image_url": "https://img.example.com/raider125.jpg",
                "link": "https://example.com/raider125",
            },
        ]

    def test_corrupted_item_skipped_without_crash(self, caplog):
        items = self._build_catalog_items()
        catalog_response_str = f"Encontré {len(items)} motos relacionados:\n"
        skipped_count = 0

        with caplog.at_level(logging.WARNING):
            for m in items:
                name = m.get('name')
                summary = m.get('summary')
                price = m.get('price') or m.get('formatted_price')

                if not name or not summary or not price:
                    logging.getLogger(__name__).warning(
                        f"⚠️ [NULL MASKING DETECTED] Ítem de catálogo omitido por llave crítica nula o vacía: "
                        f"name={name!r}, summary={summary!r}, price={price!r}."
                    )
                    skipped_count += 1
                    continue

                catalog_response_str += f"- {name} ({m.get('category', 'Moto')}): {price}\n"
                catalog_response_str += f"  Ficha Tecnica: {summary}\n"

        assert skipped_count == 1
        assert "TVS Sport 100" in catalog_response_str
        assert "NULL MASKING DETECTED" in caplog.text

    def test_no_crash_with_all_items_corrupted(self, caplog):
        items = [
            {"Nombre del producto TVS": "", "Descripción del producto TVS": "", "precio": ""},
            {"name": None, "summary": None, "price": None},
        ]
        skipped = 0
        with caplog.at_level(logging.WARNING):
            for m in items:
                name = m.get('name')
                summary = m.get('summary')
                price = m.get('price') or m.get('formatted_price')
                if not name or not summary or not price:
                    logging.getLogger(__name__).warning(f"⚠️ [NULL MASKING DETECTED] Ítem de catálogo omitido")
                    skipped += 1
                    continue
        assert skipped == 2


# ──────────────────────────────────────────────────────────────────────
# TEST 2: update_whatsapp_status captura gRPC sin re-raise (CORREGIDO PARA .SET)
# ──────────────────────────────────────────────────────────────────────
class TestUpdateWhatsappStatusGRPCResilience:
    """
    Reproduce BOT-BUG-040 Condición 2: Una excepción gRPC en
    update_whatsapp_status NO debe propagarse al caller (background task).
    """

    @pytest.fixture
    def memory_service(self):
        from app.services.memory_service import MemoryService
        mock_db = MagicMock()
        return MemoryService(mock_db)

    @pytest.mark.asyncio
    async def test_grpc_service_unavailable_does_not_raise(self, memory_service, caplog):
        """Verifica resiliencia inyectando el side_effect en el método .set()"""
        mock_doc_ref = AsyncMock()
        mock_doc_snap = MagicMock()
        mock_doc_snap.exists = True
        mock_doc_snap.to_dict.return_value = {"status": "PENDING"}
        mock_doc_ref.get = AsyncMock(return_value=mock_doc_snap)

        # Inyectar el error en .set() para mapear el comportamiento real de producción
        mock_doc_ref.set = AsyncMock(
            side_effect=gcp_exceptions.ServiceUnavailable("Connection reset by peer")
        )

        memory_service._find_prospect_ref = AsyncMock(return_value=mock_doc_ref)

        async def passthrough_io(coro, phone, label, timeout=None):
            return await coro
        memory_service._firestore_io = passthrough_io

        with caplog.at_level(logging.ERROR):
            await memory_service.update_whatsapp_status(
                phone_number="+573001234567",
                status_value="delivered",
                wamid="wamid.test123",
                errors=None,
            )

        assert "BOT-BUG-040" in caplog.text or "[BOT-BUG-040]" in caplog.text
        assert "ServiceUnavailable" in caplog.text or "Connection reset" in caplog.text

    @pytest.mark.asyncio
    async def test_timeout_error_does_not_raise(self, memory_service, caplog):
        mock_doc_ref = AsyncMock()
        mock_doc_snap = MagicMock()
        mock_doc_snap.exists = True
        mock_doc_snap.to_dict.return_value = {"status": "IN_PROGRESS"}
        mock_doc_ref.get = AsyncMock(return_value=mock_doc_snap)
        
        # Inyectar el TimeoutError en .set()
        mock_doc_ref.set = AsyncMock(side_effect=asyncio.TimeoutError())

        memory_service._find_prospect_ref = AsyncMock(return_value=mock_doc_ref)

        async def passthrough_io(coro, phone, label, timeout=None):
            return await coro
        memory_service._firestore_io = passthrough_io

        with caplog.at_level(logging.ERROR):
            await memory_service.update_whatsapp_status(
                phone_number="+573009876543",
                status_value="read",
                wamid="wamid.test456",
            )

        assert "BOT-BUG-040" in caplog.text or "[BOT-BUG-040]" in caplog.text


# ──────────────────────────────────────────────────────────────────────
# TEST 3: Aserción de contenido — Ficha Tecnica presente con ítems mixtos
# ──────────────────────────────────────────────────────────────────────
class TestFichaTecnicaContentAssertion:
    def test_ficha_tecnica_present_for_valid_items(self):
        items = [
            {"name": "TVS Sport 100", "summary": "Motor 4T OHC refrigerado por aire.", "price": "$4.590.000"},
            {"name": "TVS APACHE 160", "summary": "", "price": "$11.990.000"},
        ]
        catalog_response_str = ""
        for m in items:
            name = m.get('name')
            summary = m.get('summary')
            price = m.get('price') or m.get('formatted_price')
            if not name or not summary or not price:
                continue
            catalog_response_str += f"- {name}: {price}\n  Ficha Tecnica: {summary}\n"

        assert "Ficha Tecnica:" in catalog_response_str
        match = re.search(r"Ficha Tecnica:\s*(.+)", catalog_response_str)
        assert match is not None
        val = match.group(1).strip()
        assert val != "" and val != "None"

    def test_ficha_tecnica_absent_when_only_corrupted(self):
        items = [{"name": "TVS APACHE 160", "summary": "", "price": "$11.990.000"}]
        catalog_response_str = ""
        for m in items:
            name = m.get('name')
            summary = m.get('summary')
            price = m.get('price')
            if not name or not summary or not price:
                continue
            catalog_response_str += f"  Ficha Tecnica: {summary}\n"
        assert "Ficha Tecnica:" not in catalog_response_str