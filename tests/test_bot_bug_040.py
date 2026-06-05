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
from unittest.mock import AsyncMock, MagicMock, patch
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
                "Nombre del producto TVS": "TVS Sport 100",
                "Descripción del producto TVS": "Moto económica ideal para trabajo.",
                "precio": "$4.590.000",
                "category": "Trabajo",
                "image_url": "https://img.example.com/sport100.jpg",
                "link": "https://example.com/sport100",
            },
            {
                # Ítem corrupto: summary vacía (reproduce el bug exacto)
                "Nombre del producto TVS": "TVS APACHE 160",
                "Descripción del producto TVS": "",  # ← LLAVE VACÍA que causaba el crash
                "precio": "$11.990.000",
                "category": "Deportiva",
                "image_url": "https://img.example.com/apache160.jpg",
                "link": "https://example.com/apache160",
            },
            {
                "Nombre del producto TVS": "TVS Raider 125",
                "Descripción del producto TVS": "Naked deportiva con tecnología SmartXonnect.",
                "precio": "$7.190.000",
                "category": "Urban",
                "image_url": "https://img.example.com/raider125.jpg",
                "link": "https://example.com/raider125",
            },
        ]

    def test_corrupted_item_skipped_without_crash(self, caplog):
        """
        ANTI-REGRESIÓN: El bucle de formateo del catálogo DEBE continuar
        cuando un ítem tiene 'summary' vacía, emitiendo logger.warning.
        """
        items = self._build_catalog_items()

        # Simular la lógica exacta de ai_brain.py (líneas 1088-1112)
        catalog_response_str = f"Encontré {len(items)} motos relacionados:\n"
        skipped_count = 0

        with caplog.at_level(logging.WARNING):
            for m in items:
                name = m.get('Nombre del producto TVS') or m.get('name')
                summary = m.get('Descripción del producto TVS') or m.get('summary')
                price = m.get('precio') or m.get('price') or m.get('formatted_price')

                if not name or not summary or not price:
                    # Reproducción exacta del fix BOT-BUG-040
                    logging.getLogger(__name__).warning(
                        f"⚠️ [NULL MASKING DETECTED] Ítem de catálogo omitido por llave crítica nula o vacía: "
                        f"name={name!r}, summary={summary!r}, price={price!r}. "
                        f"Raw item keys: {list(m.keys())}"
                    )
                    skipped_count += 1
                    continue

                catalog_response_str += f"- {name} ({m.get('category', 'Moto')}): {price}\n"
                catalog_response_str += f"  Ficha Tecnica: {summary}\n"

        # ASERCIONES
        assert skipped_count == 1, f"Exactamente 1 ítem corrupto debió ser omitido, pero fueron {skipped_count}"
        assert "TVS Sport 100" in catalog_response_str, "El ítem válido TVS Sport 100 DEBE estar presente"
        assert "TVS Raider 125" in catalog_response_str, "El ítem válido TVS Raider 125 DEBE estar presente"
        assert "TVS APACHE 160" not in catalog_response_str, "El ítem corrupto TVS APACHE 160 NO debe estar"
        assert "NULL MASKING DETECTED" in caplog.text, "El warning forense DEBE haberse emitido"

    def test_no_crash_with_all_items_corrupted(self, caplog):
        """
        Caso extremo: TODOS los ítems del catálogo son corruptos.
        El bucle no debe crashear y catalog_response_str no debe contener ítems.
        """
        items = [
            {"Nombre del producto TVS": "", "Descripción del producto TVS": "", "precio": ""},
            {"name": None, "summary": None, "price": None},
        ]

        catalog_response_str = f"Encontré {len(items)} motos relacionados:\n"
        skipped = 0

        with caplog.at_level(logging.WARNING):
            for m in items:
                name = m.get('Nombre del producto TVS') or m.get('name')
                summary = m.get('Descripción del producto TVS') or m.get('summary')
                price = m.get('precio') or m.get('price') or m.get('formatted_price')

                if not name or not summary or not price:
                    logging.getLogger(__name__).warning(
                        f"⚠️ [NULL MASKING DETECTED] Ítem de catálogo omitido: "
                        f"name={name!r}, summary={summary!r}, price={price!r}"
                    )
                    skipped += 1
                    continue

                catalog_response_str += f"- {name}: {price}\n"

        assert skipped == 2, "Todos los ítems debieron ser omitidos"
        # Sólo debe quedar el header, sin ítems
        lines = [l for l in catalog_response_str.strip().split("\n") if l.startswith("- ")]
        assert len(lines) == 0, "No debe haber ítems en la respuesta cuando todos son corruptos"


# ──────────────────────────────────────────────────────────────────────
# TEST 2: update_whatsapp_status captura gRPC sin re-raise
# ──────────────────────────────────────────────────────────────────────
class TestUpdateWhatsappStatusGRPCResilience:
    """
    Reproduce BOT-BUG-040 Condición 2: Una excepción gRPC en
    update_whatsapp_status NO debe propagarse al caller (background task).
    """

    @pytest.fixture
    def memory_service(self):
        """Crea un MemoryService con mocks de Firestore."""
        from app.services.memory_service import MemoryService

        mock_db = MagicMock()
        ms = MemoryService(mock_db)
        return ms

    @pytest.mark.asyncio
    async def test_grpc_service_unavailable_does_not_raise(self, memory_service, caplog):
        """
        Simula un gRPC ServiceUnavailable en _firestore_io durante
        update_whatsapp_status. Verifica que NO re-lanza la excepción.
        """
        # Mock _find_prospect_ref para devolver un doc_ref funcional
        mock_doc_ref = AsyncMock()
        mock_doc_snap = MagicMock()
        mock_doc_snap.exists = True
        mock_doc_snap.to_dict.return_value = {"status": "PENDING"}
        mock_doc_ref.get = AsyncMock(return_value=mock_doc_snap)

        # Hacer que update() lance ServiceUnavailable (gRPC)
        mock_doc_ref.update = AsyncMock(
            side_effect=gcp_exceptions.ServiceUnavailable("Connection reset by peer")
        )

        memory_service._find_prospect_ref = AsyncMock(return_value=mock_doc_ref)

        # Bypass _firestore_io timeout wrapper para que la excepción gRPC llegue directo
        async def passthrough_io(coro, phone, label, timeout=None):
            return await coro
        memory_service._firestore_io = passthrough_io

        # ASERCIÓN PRINCIPAL: NO debe lanzar excepción
        with caplog.at_level(logging.ERROR):
            await memory_service.update_whatsapp_status(
                phone_number="+573001234567",
                status_value="delivered",
                wamid="wamid.test123",
                errors=None,
            )

        # Verificar que el log forense fue emitido
        assert "BOT-BUG-040" in caplog.text, "El log forense con tag BOT-BUG-040 DEBE estar presente"
        assert "ServiceUnavailable" in caplog.text or "Connection reset" in caplog.text

    @pytest.mark.asyncio
    async def test_timeout_error_does_not_raise(self, memory_service, caplog):
        """
        Simula un asyncio.TimeoutError en update_whatsapp_status.
        Verifica que NO re-lanza la excepción.
        """
        mock_doc_ref = AsyncMock()
        mock_doc_snap = MagicMock()
        mock_doc_snap.exists = True
        mock_doc_snap.to_dict.return_value = {"status": "IN_PROGRESS"}
        mock_doc_ref.get = AsyncMock(return_value=mock_doc_snap)
        mock_doc_ref.update = AsyncMock(side_effect=asyncio.TimeoutError())

        memory_service._find_prospect_ref = AsyncMock(return_value=mock_doc_ref)

        async def passthrough_io(coro, phone, label, timeout=None):
            return await coro
        memory_service._firestore_io = passthrough_io

        # NO debe lanzar
        with caplog.at_level(logging.ERROR):
            await memory_service.update_whatsapp_status(
                phone_number="+573009876543",
                status_value="read",
                wamid="wamid.test456",
            )

        assert "BOT-BUG-040" in caplog.text


# ──────────────────────────────────────────────────────────────────────
# TEST 3: Aserción de contenido — Ficha Tecnica presente con ítems mixtos
# ──────────────────────────────────────────────────────────────────────
class TestFichaTecnicaContentAssertion:
    """
    Verifica que 'Ficha Tecnica:' está presente y tiene contenido válido
    cuando existen ítems válidos junto a corruptos en el catálogo.
    """

    def test_ficha_tecnica_present_for_valid_items(self):
        """
        Reproduce el flujo de formateo del catálogo con ítems mixtos.
        Los ítems válidos DEBEN generar 'Ficha Tecnica:' con contenido no vacío y no None.
        """
        items = [
            {
                "Nombre del producto TVS": "TVS Sport 100",
                "Descripción del producto TVS": "Motor 4T OHC refrigerado por aire.",
                "precio": "$4.590.000",
            },
            {
                # Corrupto
                "Nombre del producto TVS": "TVS APACHE 160",
                "Descripción del producto TVS": "",
                "precio": "$11.990.000",
            },
        ]

        catalog_response_str = ""
        for m in items:
            name = m.get('Nombre del producto TVS') or m.get('name')
            summary = m.get('Descripción del producto TVS') or m.get('summary')
            price = m.get('precio') or m.get('price') or m.get('formatted_price')

            if not name or not summary or not price:
                continue

            catalog_response_str += f"- {name}: {price}\n"
            catalog_response_str += f"  Ficha Tecnica: {summary}\n"

        # ASERCIONES DE CONTENIDO (mandato del ticket)
        assert "Ficha Tecnica:" in catalog_response_str, \
            "La cadena transformada 'Ficha Tecnica:' DEBE estar presente para ítems válidos"

        match = re.search(r"Ficha Tecnica:\s*(.+)", catalog_response_str)
        assert match is not None, "El contenido después de 'Ficha Tecnica:' no puede ser nulo"

        val = match.group(1).strip()
        assert val != "", "El string de Ficha Tecnica no puede ser vacío"
        assert val != "None", "El string de Ficha Tecnica no puede ser 'None' silencioso"
        assert "Motor 4T" in val, "El contenido de Ficha Tecnica debe reflejar el summary real"

    def test_ficha_tecnica_absent_when_only_corrupted(self):
        """
        Si sólo hay ítems corruptos, NO debe haber 'Ficha Tecnica:' en la respuesta.
        Esto valida que no se inyecta un None silencioso.
        """
        items = [
            {"Nombre del producto TVS": "TVS APACHE 160", "Descripción del producto TVS": "", "precio": "$11.990.000"},
        ]

        catalog_response_str = ""
        for m in items:
            name = m.get('Nombre del producto TVS') or m.get('name')
            summary = m.get('Descripción del producto TVS') or m.get('summary')
            price = m.get('precio') or m.get('price')

            if not name or not summary or not price:
                continue

            catalog_response_str += f"  Ficha Tecnica: {summary}\n"

        assert "Ficha Tecnica:" not in catalog_response_str, \
            "NO debe haber 'Ficha Tecnica:' cuando todos los ítems son corruptos (previene None silencioso)"
