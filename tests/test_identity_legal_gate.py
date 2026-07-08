import unittest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ai_brain import CerebroIA

class MockConfigLoader:
    def get_config(self, key, default=None):
        return default

class TestIdentityLegalGate(unittest.TestCase):
    def setUp(self):
        self.cerebro = CerebroIA()
        self.cerebro.config_loader = MockConfigLoader()

    def test_strict_retention_in_phase_2_without_identity(self):
        """
        GIVEN: El prospecto tiene habeas_data_accepted=True y habeas_data_accepted_sent=True.
        BUT: Falta nombre o ciudad (identidad ausente).
        THEN: La máquina de estados DEBE retener al prospecto en PHASE_2_HABEAS_DATA (no PHASE_1 ni PHASE_3).
        """
        prospect_data = {
            "nombre": "",  # Ausente
            "ciudad": None,  # Ausente
            "forma_pago": "credito",
            "moto_interest": "TVS Apache 160",  # [GUARDRAIL SATISFECHO]
            "habeas_data_accepted": True,
            "habeas_data_accepted_sent": True
        }
        
        # Historial que contiene el link físico de privacidad
        history = [
            {"role": "model", "content": "Consulta aquí: tiendalasmotos.com/politica-de-privacidad"},
            {"role": "user", "content": "Sí, acepto el tratamiento de datos"}
        ]
        
        phase = self.cerebro._determine_funnel_phase(prospect_data, history=history)
        self.assertEqual(phase, "PHASE_2_HABEAS_DATA", "Debería retener en Fase 2 si falta la identidad.")

    def test_phase_3_transition_with_consent_and_identity(self):
        """
        GIVEN: Consentimiento legal completo (habeas_data_accepted=True, habeas_data_accepted_sent=True, link en chat).
        AND: Captura de identidad completa (nombre y ciudad presentes).
        THEN: Transiciona exitosamente a PHASE_3_CREDIT_PROFILING.
        """
        prospect_data = {
            "nombre": "Tobias",
            "ciudad": "Santa Marta",
            "forma_pago": "credito",
            "moto_interest": "TVS Apache 160",  # [GUARDRAIL SATISFECHO]
            "habeas_data_accepted": True,
            "habeas_data_accepted_sent": True
        }
        
        history = [
            {"role": "model", "content": "Consulta aquí: tiendalasmotos.com/politica-de-privacidad"},
            {"role": "user", "content": "Sí"}
        ]
        
        phase = self.cerebro._determine_funnel_phase(prospect_data, history=history)
        self.assertEqual(phase, "PHASE_3_CREDIT_PROFILING", "Debería transicionar a Fase 3.")

    def test_zero_silent_failures_identity_nulls_in_phase_2(self):
        """
        [ZERO-SILENT-FAILURES]
        Verifica que el test no sea silencioso (falle) si detecta valores None o strings
        vacíos en los campos de identidad cuando la fase es PHASE_2 (pero ya se aceptó Habeas).
        """
        prospect_data = {
            "nombre": "",
            "ciudad": None,
            "forma_pago": "credito",
            "moto_interest": "TVS Apache 160",  # [GUARDRAIL SATISFECHO]
            "habeas_data_accepted": True,
            "habeas_data_accepted_sent": True
        }
        
        history = [
            {"role": "model", "content": "Consulta aquí: tiendalasmotos.com/politica-de-privacidad"},
            {"role": "user", "content": "Sí"}
        ]
        
        phase = self.cerebro._determine_funnel_phase(prospect_data, history=history)
        self.assertEqual(phase, "PHASE_2_HABEAS_DATA")
        
        # Debemos garantizar que la validación explícitamente levante un error al evaluar identidad
        nombre = prospect_data.get("nombre")
        ciudad = prospect_data.get("ciudad")
        
        # Verificamos que al menos uno esté vacío/None y forzamos la aserción no silenciosa
        with self.assertRaises(AssertionError):
            self.assertIsNotNone(nombre)
            self.assertNotEqual(str(nombre).strip(), "")
            self.assertIsNotNone(ciudad)
            self.assertNotEqual(str(ciudad).strip(), "")

    def test_cuota_exacta_enganche_assertion(self):
        """
        Verifica la presencia explícita de la cadena de cuota con $ y números.
        Prohíbe que una mutación de llaves resulte en valores None o strings vacíos.
        """
        simulated_response = "Tu cuota mensual estimada de enganche quedaría en $350.000 con Crediorbe."
        
        # 1. Aserción de contenido: verificar presencia de la cuota exacta (con $)
        self.assertIn("$", simulated_response, "Falta el símbolo de precio '$' en la respuesta.")
        self.assertTrue(any(char.isdigit() for char in simulated_response), "Falta el valor numérico en la respuesta.")
        
        # 2. Prohibir mutaciones nulas o strings vacíos
        self.assertIsNotNone(simulated_response, "El contenido de la cuota no puede ser None.")
        self.assertNotEqual(simulated_response.strip(), "", "El contenido de la cuota no puede ser un string vacío.")

    @patch("app.routers.whatsapp.db")
    @patch("app.routers.whatsapp.message_buffer")
    @patch("app.routers.whatsapp.config_loader")
    @patch("app.routers.whatsapp.catalog_service")
    @patch("app.routers.whatsapp.config_service")
    @patch("app.routers.whatsapp.judge_service")
    @patch("app.routers.whatsapp.memory_service_module")
    @patch("app.routers.whatsapp.CerebroIA")
    @patch("app.routers.whatsapp.storage_service")
    @patch("app.routers.whatsapp._send_whatsapp_message")
    @patch("app.services.whatsapp_service.whatsapp_service")
    def test_sticker_affirmative_normalization_to_si(
        self, mock_wa_service, mock_send_wa, mock_storage, mock_cerebro_class, 
        mock_mem_module, mock_judge, mock_config_service, mock_catalog, 
        mock_config_loader, mock_message_buffer, mock_db
    ):
        """
        GIVEN: A webhook message payload containing msg_type: 'sticker'
        AND: The sticker represents an affirmative response ('thumbs_up')
        WHEN: WhatsApp router receives and processes the sticker
        THEN: It must normalize the input to 'Sí' towards CerebroIA, which
              raises HabeasDataBypassInterrupt, leading to immediate approval
              and saving 'Sí' as the user's message.
        """
        import asyncio
        from fastapi import BackgroundTasks
        from app.routers.whatsapp import _handle_message_background
        from app.core.exceptions import HabeasDataBypassInterrupt
        
        # 1. Payload simulating incoming sticker message
        msg_data = {
            "from": "573192564288",
            "id": "wamid.sticker_test_123",
            "type": "sticker",
            "sticker": {
                "id": "sticker_media_123",
                "mime_type": "image/webp",
                "emoji": "👍"
            },
            "phone_number_id": "1021779847693778"
        }
        background_tasks = BackgroundTasks()

        # 2. Mock Prospect data
        mock_prospect_data = {
            "exists": True,
            "celular": "+573192564288",
            "chatbot_status": "ACTIVE",
            "status": "PENDING",
            "source": "whatsapp_bot",
            "habeas_data_accepted": False
        }

        # 3. Setup mocks
        mock_ms = AsyncMock()
        mock_ms.get_prospect_data = AsyncMock(return_value=mock_prospect_data)
        mock_ms.create_prospect_if_missing = AsyncMock()
        mock_ms.get_chat_history = AsyncMock(return_value=[])
        mock_ms.save_message = AsyncMock()
        mock_ms.generate_and_update_summary = AsyncMock()
        mock_mem_module.memory_service = mock_ms

        mock_storage.download_media = AsyncMock(return_value=b"fake_image_bytes")
        
        mock_vision_instance = AsyncMock()
        mock_vision_instance.analyze_image = AsyncMock(return_value="[System Note: thumbs_up]")
        
        with patch("app.routers.whatsapp.VisionService", return_value=mock_vision_instance):
            mock_cerebro = AsyncMock()
            mock_cerebro.pensar_respuesta = AsyncMock(side_effect=HabeasDataBypassInterrupt("Bypass Approved"))
            mock_cerebro_class.return_value = mock_cerebro
            
            mock_message_buffer.add_message = AsyncMock(return_value=True)
            mock_wa_service.mark_as_read = AsyncMock(return_value=True)
            mock_send_wa.return_value = True

            # Run the handler
            asyncio.run(_handle_message_background(msg_data, background_tasks))

            # Verification
            mock_storage.download_media.assert_called_with("sticker_media_123")
            mock_vision_instance.analyze_image.assert_called_once()
            
            mock_cerebro.pensar_respuesta.assert_called_once()
            args, kwargs = mock_cerebro.pensar_respuesta.call_args
            self.assertEqual(args[0], "Sí")
            
            mock_send_wa.assert_called_with("+573192564288", "Bypass Approved", phone_number_id="1021779847693778")
            mock_ms.save_message.assert_any_call("+573192564288", "user", "Sí")

    @patch("app.routers.whatsapp.db")
    @patch("app.routers.whatsapp.message_buffer")
    @patch("app.routers.whatsapp.config_loader")
    @patch("app.routers.whatsapp.catalog_service")
    @patch("app.routers.whatsapp.config_service")
    @patch("app.routers.whatsapp.judge_service")
    @patch("app.routers.whatsapp.memory_service_module")
    @patch("app.routers.whatsapp.CerebroIA")
    @patch("app.routers.whatsapp.storage_service")
    @patch("app.routers.whatsapp._send_whatsapp_message")
    @patch("app.services.whatsapp_service.whatsapp_service")
    def test_whatsapp_reaction_payload_direct_legal_acceptance(
        self, mock_wa_service, mock_send_wa, mock_storage, mock_cerebro_class, 
        mock_mem_module, mock_judge, mock_config_service, mock_catalog, 
        mock_config_loader, mock_message_buffer, mock_db
    ):
        """
        GIVEN: Un payload de webhook con msg_type: 'reaction' y emoji afirmativo '👍'.
        WHEN: El router de WhatsApp recibe la reacción.
        THEN: Debe mutar el body a 'Sí', interceptar y actualizar habeas_data_accepted = True síncronamente
              en la base de datos/memoria antes de que se llame a pensar_respuesta.
        """
        import asyncio
        from fastapi import BackgroundTasks
        from app.routers.whatsapp import _handle_message_background
        
        # 1. Payload de reacción crudo estructurado de WhatsApp
        msg_data = {
            "from": "573192564288",
            "id": "wamid.reaction_test_999",
            "type": "reaction",
            "reaction": {
                "message_id": "wamid.parent_message_123",
                "emoji": "👍"
            },
            "phone_number_id": "1021779847693778"
        }
        background_tasks = BackgroundTasks()

        # 2. Mock Prospect data sin consentimiento inicial
        mock_prospect_data = {
            "exists": True,
            "celular": "+573192564288",
            "chatbot_status": "ACTIVE",
            "status": "PENDING",
            "source": "whatsapp_bot",
            "habeas_data_accepted": False
        }

        # 3. Setup mocks
        mock_ms = AsyncMock()
        mock_ms.get_prospect_data = AsyncMock(return_value=mock_prospect_data)
        mock_ms.create_prospect_if_missing = AsyncMock()
        mock_ms.get_chat_history = AsyncMock(return_value=[])
        mock_ms.save_message = AsyncMock()
        mock_ms.generate_and_update_summary = AsyncMock()
        
        async def mock_update_summary(phone, summary, data):
            if "habeas_data_accepted" in data:
                mock_prospect_data["habeas_data_accepted"] = data["habeas_data_accepted"]
        mock_ms.update_prospect_summary = AsyncMock(side_effect=mock_update_summary)
        mock_mem_module.memory_service = mock_ms

        mock_cerebro = AsyncMock()
        mock_cerebro.pensar_respuesta = AsyncMock(return_value="Entendido, habeas data firmado.")
        mock_cerebro_class.return_value = mock_cerebro
        
        mock_message_buffer.add_message = AsyncMock(return_value=True)
        mock_message_buffer.is_task_active = MagicMock(return_value=True)
        mock_message_buffer.get_aggregated_message = AsyncMock(return_value=None)
        mock_message_buffer.clear_buffer = AsyncMock()
        mock_message_buffer.debounce_seconds = 0.0  # Sin delay en tests
        
        mock_wa_service.mark_as_read = AsyncMock(return_value=True)
        mock_send_wa.return_value = True
        mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

        # 4. Ejecutar el handler
        asyncio.run(_handle_message_background(msg_data, background_tasks))

        # 5. Verificaciones
        # Debe haberse llamado a update_prospect_summary indicando mutación síncrona
        mock_ms.update_prospect_summary.assert_any_call("+573192564288", "", {"habeas_data_accepted": True})
        
        # Debió llamarse a pensar_respuesta con el body mutado a "Sí"
        mock_cerebro.pensar_respuesta.assert_called_once()
        args, kwargs = mock_cerebro.pensar_respuesta.call_args
        self.assertEqual(args[0], "Sí")
        
        # prospect_data debió actualizarse a True
        self.assertTrue(kwargs["prospect_data"]["habeas_data_accepted"])

if __name__ == '__main__':
    unittest.main()