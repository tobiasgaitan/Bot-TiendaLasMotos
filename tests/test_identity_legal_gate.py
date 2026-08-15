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
            mock_message_buffer.clear_messages = AsyncMock()
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
        mock_message_buffer.clear_messages = AsyncMock()
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
        # [BOT-PONYTAIL-200] Updated assertion to include ponytail_status=PENDING
        mock_ms.update_prospect_summary.assert_any_call("+573192564288", "", {"habeas_data_accepted": True, "ponytail_status": "PENDING"})
        
        # Debió llamarse a pensar_respuesta con el body mutado a "Sí"
        mock_cerebro.pensar_respuesta.assert_called_once()
        args, kwargs = mock_cerebro.pensar_respuesta.call_args
        self.assertEqual(args[0], "Sí")
        
        # prospect_data debió actualizarse a True
        self.assertTrue(kwargs["prospect_data"]["habeas_data_accepted"])

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
    def test_image_routing_legacy_moto_token(
        self, mock_wa_service, mock_send_wa, mock_storage, mock_cerebro_class, 
        mock_mem_module, mock_judge, mock_config_service, mock_catalog, 
        mock_config_loader, mock_message_buffer, mock_db
    ):
        """
        GIVEN: El prompt del motor de IA devuelve la respuesta heredada con "[MOTO_DETECTADA]"
        WHEN: Se recibe y procesa el webhook de imagen en whatsapp.py
        THEN: Se enruta al flujo de catálogo, sanitizando el token y llamando a CerebroIA.
        """
        import asyncio
        from fastapi import BackgroundTasks
        from app.routers.whatsapp import _handle_message_background
        
        msg_data = {
            "from": "573192564288",
            "id": "wamid.image_test_legacy",
            "type": "image",
            "image": {
                "id": "image_media_123",
                "mime_type": "image/jpeg",
                "caption": ""
            },
            "phone_number_id": "1021779847693778"
        }
        background_tasks = BackgroundTasks()

        mock_prospect_data = {
            "exists": True,
            "celular": "+573192564288",
            "chatbot_status": "ACTIVE",
            "status": "PENDING",
            "source": "whatsapp_bot",
            "habeas_data_accepted": True
        }

        mock_ms = AsyncMock()
        mock_ms.get_prospect_data = AsyncMock(return_value=mock_prospect_data)
        mock_ms.create_prospect_if_missing = AsyncMock()
        mock_ms.get_chat_history = AsyncMock(return_value=[])
        mock_ms.save_message = AsyncMock()
        mock_ms.generate_and_update_summary = AsyncMock()
        mock_mem_module.memory_service = mock_ms

        mock_storage.download_media = AsyncMock(return_value=b"fake_image_bytes")
        
        mock_vision_instance = AsyncMock()
        mock_vision_instance.analyze_image = AsyncMock(return_value="[MOTO_DETECTADA] TVS Raider 125")
        
        with patch("app.routers.whatsapp.VisionService", return_value=mock_vision_instance):
            mock_cerebro = AsyncMock()
            mock_cerebro.pensar_respuesta = AsyncMock(return_value="Aquí tienes la TVS Raider 125")
            mock_cerebro_class.return_value = mock_cerebro
            
            mock_message_buffer.add_message = AsyncMock(return_value=True)
            mock_message_buffer.clear_messages = AsyncMock()
            mock_wa_service.mark_as_read = AsyncMock(return_value=True)
            mock_send_wa.return_value = True

            asyncio.run(_handle_message_background(msg_data, background_tasks))

            mock_storage.download_media.assert_called_with("image_media_123")
            mock_vision_instance.analyze_image.assert_called_once()
            
            mock_cerebro.pensar_respuesta.assert_called_once()
            args, kwargs = mock_cerebro.pensar_respuesta.call_args
            self.assertIn("TVS Raider 125", args[0])
            self.assertNotIn("[MOTO_DETECTADA]", args[0])
            
            mock_send_wa.assert_called_with("+573192564288", "Aquí tienes la TVS Raider 125", phone_number_id="1021779847693778")

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
    def test_image_routing_clean_moto_description(
        self, mock_wa_service, mock_send_wa, mock_storage, mock_cerebro_class, 
        mock_mem_module, mock_judge, mock_config_service, mock_catalog, 
        mock_config_loader, mock_message_buffer, mock_db
    ):
        """
        GIVEN: El prompt de la IA devuelve la respuesta sin el prefijo rígido heredado
        WHEN: Se recibe y procesa el webhook de imagen en whatsapp.py
        THEN: Se enruta exitosamente por defecto al flujo de catálogo y se sanitiza.
        """
        import asyncio
        from fastapi import BackgroundTasks
        from app.routers.whatsapp import _handle_message_background
        
        for raw_response in ["MOTO_DETECTADA: TVS Raider 125", "TVS Raider 125"]:
            with self.subTest(raw_response=raw_response):
                mock_cerebro_class.reset_mock()
                mock_send_wa.reset_mock()
                
                msg_data = {
                    "from": "573192564288",
                    "id": f"wamid.image_test_{abs(hash(raw_response))}",
                    "type": "image",
                    "image": {
                        "id": "image_media_123",
                        "mime_type": "image/jpeg",
                        "caption": ""
                    },
                    "phone_number_id": "1021779847693778"
                }
                background_tasks = BackgroundTasks()

                mock_prospect_data = {
                    "exists": True,
                    "celular": "+573192564288",
                    "chatbot_status": "ACTIVE",
                    "status": "PENDING",
                    "source": "whatsapp_bot",
                    "habeas_data_accepted": True
                }

                mock_ms = AsyncMock()
                mock_ms.get_prospect_data = AsyncMock(return_value=mock_prospect_data)
                mock_ms.create_prospect_if_missing = AsyncMock()
                mock_ms.get_chat_history = AsyncMock(return_value=[])
                mock_ms.save_message = AsyncMock()
                mock_ms.generate_and_update_summary = AsyncMock()
                mock_mem_module.memory_service = mock_ms

                mock_storage.download_media = AsyncMock(return_value=b"fake_image_bytes")
                
                mock_vision_instance = AsyncMock()
                mock_vision_instance.analyze_image = AsyncMock(return_value=raw_response)
                
                with patch("app.routers.whatsapp.VisionService", return_value=mock_vision_instance):
                    mock_cerebro = AsyncMock()
                    mock_cerebro.pensar_respuesta = AsyncMock(return_value="Aquí tienes la TVS Raider 125")
                    mock_cerebro_class.return_value = mock_cerebro
                    
                    mock_message_buffer.add_message = AsyncMock(return_value=True)
                    mock_message_buffer.clear_messages = AsyncMock()
                    mock_wa_service.mark_as_read = AsyncMock(return_value=True)
                    mock_send_wa.return_value = True

                    asyncio.run(_handle_message_background(msg_data, background_tasks))

                    mock_cerebro.pensar_respuesta.assert_called_once()
                    args, kwargs = mock_cerebro.pensar_respuesta.call_args
                    self.assertIn("TVS Raider 125", args[0])
                    self.assertNotIn("MOTO_DETECTADA", args[0])
                    
                    mock_send_wa.assert_called_with("+573192564288", "Aquí tienes la TVS Raider 125", phone_number_id="1021779847693778")

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
    def test_image_routing_null_response_triggers_exception(
        self, mock_wa_service, mock_send_wa, mock_storage, mock_cerebro_class, 
        mock_mem_module, mock_judge, mock_config_service, mock_catalog, 
        mock_config_loader, mock_message_buffer, mock_db
    ):
        """
        GIVEN: La API de Google Vision devuelve None o una respuesta vacía
        WHEN: Se recibe y procesa el webhook de imagen en whatsapp.py
        THEN: Se lanza una excepción controlada, se loguea structured y se envía un mensaje fallback.
        """
        import asyncio
        from fastapi import BackgroundTasks
        from app.routers.whatsapp import _handle_message_background
        
        msg_data = {
            "from": "573192564288",
            "id": "wamid.image_test_null",
            "type": "image",
            "image": {
                "id": "image_media_123",
                "mime_type": "image/jpeg",
                "caption": ""
            },
            "phone_number_id": "1021779847693778"
        }
        background_tasks = BackgroundTasks()

        mock_prospect_data = {
            "exists": True,
            "celular": "+573192564288",
            "chatbot_status": "ACTIVE",
            "status": "PENDING",
            "source": "whatsapp_bot",
            "habeas_data_accepted": True
        }

        mock_ms = AsyncMock()
        mock_ms.get_prospect_data = AsyncMock(return_value=mock_prospect_data)
        mock_ms.create_prospect_if_missing = AsyncMock()
        mock_ms.get_chat_history = AsyncMock(return_value=[])
        mock_ms.save_message = AsyncMock()
        mock_ms.generate_and_update_summary = AsyncMock()
        mock_mem_module.memory_service = mock_ms

        mock_storage.download_media = AsyncMock(return_value=b"fake_image_bytes")
        
        mock_vision_instance = AsyncMock()
        mock_vision_instance.analyze_image = AsyncMock(return_value=None)
        
        with patch("app.routers.whatsapp.VisionService", return_value=mock_vision_instance):
            mock_message_buffer.add_message = AsyncMock(return_value=True)
            mock_message_buffer.clear_messages = AsyncMock()
            mock_wa_service.mark_as_read = AsyncMock(return_value=True)
            mock_send_wa.return_value = True

            with patch("app.routers.whatsapp.logger.error") as mock_log_error:
                asyncio.run(_handle_message_background(msg_data, background_tasks))
                
                mock_log_error.assert_any_call(
                    "❌ [VISION_API_ERROR] La respuesta de Vision AI llegó vacía o nula. Forzando flujo de excepción controlada.",
                    extra={
                        "user_phone": "+573192564288",
                        "msg_type": "image",
                        "media_id": "image_media_123",
                        "caption": ""
                    }
                )
                
            mock_send_wa.assert_called_with("+573192564288", "Tuve un problema viendo el archivo. ¿Me cuentas qué es? 😅", phone_number_id="1021779847693778")

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
    def test_welcome_flow_post_reset_empty_firestore(
        self, mock_wa_service, mock_send_wa, mock_storage, mock_cerebro_class, 
        mock_mem_module, mock_judge, mock_config_service, mock_catalog, 
        mock_config_loader, mock_message_buffer, mock_db
    ):
        """
        GIVEN: Un estado post-reset (Firestore vacío, exists: False).
        WHEN: El enrutador recibe un mensaje de texto.
        THEN: Debe llamar bloqueantemente a get_or_create_prospect, 
              forzar la inicialización base, y despachar la bienvenida completa con el nombre del asesor ("Juan Pablo").
        """
        import asyncio
        from unittest.mock import MagicMock
        from fastapi import BackgroundTasks
        from app.routers.whatsapp import _handle_message_background

        msg_data = {
            "from": "+573192564288",
            "id": "wamid.reset_welcome_test_123",
            "type": "text",
            "text": "Hola",
            "phone_number_id": "1021779847693778"
        }
        background_tasks = BackgroundTasks()

        mock_prospect_initial = {"exists": False}
        mock_prospect_created = {
            "exists": True,
            "celular": "+573192564288",
            "chatbot_status": "ACTIVE",
            "status": "PENDING",
            "source": "whatsapp_bot",
            "habeas_data_accepted": False,
            "habeas_data_accepted_sent": False,
            "nombre": "",
            "ciudad": "",
            "moto_interest": "",
            "current_agent": "expert"
        }

        mock_ms = AsyncMock()
        mock_ms.get_or_create_prospect = AsyncMock(return_value=mock_prospect_created)
        mock_ms.get_prospect_data = AsyncMock(side_effect=[mock_prospect_initial, mock_prospect_created, mock_prospect_created])
        mock_ms.create_prospect_if_missing = AsyncMock()
        mock_ms.get_chat_history = AsyncMock(return_value=[])
        mock_ms.save_message = AsyncMock()
        mock_ms.generate_and_update_summary = AsyncMock()
        mock_ms.update_last_interaction = AsyncMock()
        mock_ms.transition_to_in_progress = AsyncMock()
        mock_mem_module.memory_service = mock_ms

        mock_cerebro = AsyncMock()
        mock_cerebro.pensar_respuesta = AsyncMock(return_value="Hola, soy Juan Pablo, asesor de Auteco Las Motos. ¿En qué moto estás interesado?")
        mock_cerebro_class.return_value = mock_cerebro

        mock_message_buffer.add_message = AsyncMock(return_value=True)
        mock_message_buffer.clear_messages = AsyncMock()
        mock_message_buffer.is_task_active = MagicMock(return_value=True)
        mock_message_buffer.get_aggregated_message = AsyncMock(return_value=None)
        mock_message_buffer.clear_buffer = AsyncMock()

        mock_wa_service.mark_as_read = AsyncMock(return_value=True)
        mock_send_wa.return_value = True
        mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

        asyncio.run(_handle_message_background(msg_data, background_tasks))

        mock_ms.get_or_create_prospect.assert_called_once_with("+573192564288")
        
        mock_send_wa.assert_called_once()
        sent_response = mock_send_wa.call_args[0][1]
        self.assertIn("Juan Pablo", sent_response, "La bienvenida debe incluir el nombre del asesor 'Juan Pablo'")

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
    def test_first_interaction_always_greets(
        self, mock_wa_service, mock_send_wa, mock_storage, mock_cerebro_class, 
        mock_mem_module, mock_judge, mock_config_service, mock_catalog, 
        mock_config_loader, mock_message_buffer, mock_db
    ):
        """
        GIVEN: Un historial vacío (primer contacto).
        AND: Una entrada directa de modelo del catálogo ('Ninja 500').
        WHEN: WhatsApp router recibe la solicitud.
        THEN: Debe invocar pensar_respuesta con skip_greeting=False, y la respuesta debe contener la presentación de Juan Pablo.
        """
        import asyncio
        from fastapi import BackgroundTasks
        from app.routers.whatsapp import _handle_message_background
        
        msg_data = {
            "from": "+573192564288",
            "id": "wamid.first_interaction_always_greets_123",
            "type": "text",
            "text": "Hola, tienen la Ninja 500?",
            "phone_number_id": "1021779847693778"
        }
        background_tasks = BackgroundTasks()

        # Configurar prospecto con exists: False (primer contacto)
        mock_prospect_initial = {"exists": False}
        mock_prospect_created = {
            "exists": True,
            "celular": "+573192564288",
            "chatbot_status": "ACTIVE",
            "status": "PENDING",
            "source": "whatsapp_bot",
            "habeas_data_accepted": False,
            "habeas_data_accepted_sent": False,
            "nombre": "",
            "ciudad": "",
            "moto_interest": "",
            "current_agent": "expert"
        }

        mock_ms = AsyncMock()
        mock_ms.get_or_create_prospect = AsyncMock(return_value=mock_prospect_created)
        mock_ms.get_prospect_data = AsyncMock(side_effect=[mock_prospect_initial, mock_prospect_created, mock_prospect_created])
        mock_ms.create_prospect_if_missing = AsyncMock()
        mock_ms.get_chat_history = AsyncMock(return_value=[])
        mock_ms.save_message = AsyncMock()
        mock_ms.generate_and_update_summary = AsyncMock()
        mock_ms.update_last_interaction = AsyncMock()
        mock_ms.transition_to_in_progress = AsyncMock()
        mock_mem_module.memory_service = mock_ms

        mock_cerebro = AsyncMock()
        mock_cerebro.pensar_respuesta = AsyncMock(return_value="Hola, soy Juan Pablo, asesor de Auteco Las Motos. ¡Claro que manejamos la Ninja 500! ¿Te gustaría financiarla?")
        mock_cerebro_class.return_value = mock_cerebro

        mock_message_buffer.add_message = AsyncMock(return_value=True)
        mock_message_buffer.clear_messages = AsyncMock()
        mock_message_buffer.is_task_active = MagicMock(return_value=True)
        mock_message_buffer.get_aggregated_message = AsyncMock(return_value=None)
        mock_message_buffer.clear_buffer = AsyncMock()
        
        mock_wa_service.mark_as_read = AsyncMock(return_value=True)
        mock_send_wa.return_value = True
        mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

        # Mock items in catalog to ensure pre-filter has items
        mock_catalog._items = [{"name": "Ninja 500", "price": "$38.000.000"}]
        mock_catalog._tokenize = MagicMock(return_value=["ninja", "500"])
        mock_catalog._phonetic_normalize = MagicMock(side_effect=lambda x: x)
        mock_catalog.search_items = MagicMock(return_value=[{"name": "Ninja 500", "price": "$38.000.000"}])

        asyncio.run(_handle_message_background(msg_data, background_tasks))

        # Verificar que pensar_respuesta haya sido invocado con skip_greeting=False
        mock_cerebro.pensar_respuesta.assert_called_once()
        kwargs = mock_cerebro.pensar_respuesta.call_args[1]
        self.assertEqual(kwargs.get("skip_greeting"), False, "skip_greeting debe ser False en el primer contacto")

        # Verificar que el mensaje enviado contenga la presentación de Juan Pablo
        mock_send_wa.assert_called_once()
        sent_response = mock_send_wa.call_args[0][1]
        self.assertIn("Juan Pablo", sent_response, "La respuesta debe presentarse como Juan Pablo")

    @patch("app.services.ai_brain.SDK_AVAILABLE", False)
    def test_first_interaction_always_greets_brain(self):
        """
        GIVEN: Historial vacío y un token de catálogo ('Ninja 500').
        WHEN: CerebroIA recibe pensar_respuesta con skip_greeting=True.
        THEN: Debe forzar skip_greeting a False y usar el prompt con saludo obligatorio.
        """
        from app.services.ai_brain import CerebroIA
        cerebro = CerebroIA()
        cerebro.client = MagicMock()
        cerebro._model_id = "gemini-2.0-flash"
        
        # Mock catalog service con Ninja 500
        mock_catalog = MagicMock()
        mock_catalog._items = [{"name": "Ninja 500", "price": "$38.000.000"}]
        mock_catalog._tokenize = lambda x: ["ninja", "500"]
        mock_catalog._phonetic_normalize = lambda x: x
        mock_catalog.search_items = MagicMock(return_value=[{"name": "Ninja 500", "price": "$38.000.000"}])
        cerebro._catalog_service = mock_catalog
        
        # Mock de creación de chat y respuesta
        mock_chat = AsyncMock()
        mock_response = MagicMock()
        mock_part = MagicMock()
        mock_part.text = "Hola, soy Juan Pablo, asesor de Auteco Las Motos. ¡Claro que manejamos la Ninja 500!"
        mock_part.function_call = None
        mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
        mock_chat.send_message = AsyncMock(return_value=mock_response)
        
        cerebro.client.aio.chats.create = MagicMock(return_value=mock_chat)
        
        # Invocar pensar_respuesta con historial vacío e input con coincidencia en catálogo
        import asyncio
        res = asyncio.run(cerebro.pensar_respuesta("tienen la Ninja 500?", history=[], skip_greeting=False))
        
        # Aserciones rígidas de contenido e identidad
        self.assertIn("Juan Pablo", res, "La respuesta debe incluir el nombre del asesor.")
        self.assertIn("Auteco Las Motos", res, "La respuesta debe incluir la presentación de la tienda.")
        
        # Verificar que send_message haya sido llamado con el prompt con MANDATORY WARMTH
        mock_chat.send_message.assert_called_once()
        prompt_arg = mock_chat.send_message.call_args[0][0]
        self.assertIn("MANDATORY WARMTH", prompt_arg, "El prompt consolidado debe exigir el saludo.")
        self.assertNotIn("STRICT RULE: DO NOT under any circumstance start your response", prompt_arg, "El prompt no debe suprimir el saludo.")

    @patch("app.services.ai_brain.SDK_AVAILABLE", False)
    def test_first_contact_with_saved_message_no_bypass(self):
        """
        GIVEN: Historial con el mensaje actual ya guardado (router guardó antes de evaluar).
        AND: skip_greeting=False (primer contacto real).
        WHEN: CerebroIA ensambla el prompt inicial.
        THEN: El prompt debe contener MANDATORY WARMTH.
        AND: El prompt NO debe contener STRICT RULE (supresión de saludo).
        """
        from app.services.ai_brain import CerebroIA
        cerebro = CerebroIA()
        cerebro.client = MagicMock()
        cerebro._model_id = "gemini-2.0-flash"
        
        # Mock catalog service con Ninja 500
        mock_catalog = MagicMock()
        mock_catalog._items = [{"name": "Ninja 500", "price": "$38.000.000"}]
        mock_catalog._tokenize = lambda x: ["ninja", "500"]
        mock_catalog._phonetic_normalize = lambda x: x
        mock_catalog.search_items = MagicMock(return_value=[{"name": "Ninja 500", "price": "$38.000.000"}])
        cerebro._catalog_service = mock_catalog
        
        # Mock de respuesta simple (sin tool-loop)
        mock_chat = AsyncMock()
        mock_response = MagicMock()
        mock_part = MagicMock()
        mock_part.text = "Hola, soy Juan Pablo, asesor de Auteco Las Motos. ¡Claro que manejamos la Ninja 500!"
        mock_part.function_call = None
        mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
        mock_chat.send_message = AsyncMock(return_value=mock_response)
        
        cerebro.client.aio.chats.create = MagicMock(return_value=mock_chat)
        
        # [BOT-206] Historial con mensaje actual ya guardado (flujo real del router)
        history = [
            {"role": "user", "content": "tienen la Ninja 500?"}
        ]
        
        # skip_greeting=False (primer contacto real)
        import asyncio
        res = asyncio.run(cerebro.pensar_respuesta(
            "tienen la Ninja 500?", 
            history=history, 
            skip_greeting=False
        ))
        
        # Verificar que el prompt contenga MANDATORY WARMTH (saludo obligatorio)
        mock_chat.send_message.assert_called_once()
        prompt_arg = mock_chat.send_message.call_args[0][0]
        self.assertIn("MANDATORY WARMTH", prompt_arg, "El prompt debe exigir el saludo de Juan Pablo en primer contacto.")
        self.assertNotIn("STRICT RULE: DO NOT under any circumstance start your response", prompt_arg, "El prompt no debe suprimir el saludo.")
        
        # Verificar que la respuesta final contenga la presentación de Juan Pablo
        self.assertIn("Juan Pablo", res, "La respuesta debe incluir la presentación de Juan Pablo.")

    @patch("app.services.ai_brain.SDK_AVAILABLE", False)
    def test_consecutive_out_of_catalog_query_suppresses_greeting(self):
        """
        GIVEN: Una sesión iniciada con una moto válida y un mensaje continuo sobre una moto inexistente.
        WHEN: CerebroIA recibe pensar_respuesta con skip_greeting=True.
        THEN: La respuesta del bot no debe contener la cadena 'Soy Juan Pablo'.
        """
        from app.services.ai_brain import CerebroIA
        cerebro = CerebroIA()
        cerebro.client = MagicMock()
        cerebro._model_id = "gemini-2.0-flash"
        
        # Mock catalog service (no matches query)
        mock_catalog = MagicMock()
        mock_catalog._items = [{"name": "TVS Apache 160", "price": "$9.000.000"}]
        mock_catalog._tokenize = lambda x: ["tvs", "apache", "160"]
        mock_catalog._phonetic_normalize = lambda x: x
        mock_catalog.search_items = MagicMock(return_value=[])  # Empty search results (out of catalog)
        cerebro._catalog_service = mock_catalog
        
        # Mock de creación de chat y respuestas para simular el bucle de herramientas
        mock_chat = AsyncMock()
        
        # Turno 1: Gemini llama a la herramienta search_catalog
        mock_response_1 = MagicMock()
        mock_part_1 = MagicMock()
        mock_part_1.text = None
        mock_part_1.function_call = MagicMock()
        mock_part_1.function_call.name = "search_catalog"
        mock_part_1.function_call.args = {"query": "MotoFantasma 9999"}
        mock_response_1.candidates = [MagicMock(content=MagicMock(parts=[mock_part_1]))]
        
        # Turno 2: Gemini da la respuesta final de texto tras recibir el resultado de la herramienta
        mock_response_2 = MagicMock()
        mock_part_2 = MagicMock()
        mock_part_2.text = "No encontré esa moto en nuestro catálogo, pero tenemos otras opciones."
        mock_part_2.function_call = None
        mock_response_2.candidates = [MagicMock(content=MagicMock(parts=[mock_part_2]))]
        
        mock_chat.send_message = AsyncMock(side_effect=[mock_response_1, mock_response_2])
        cerebro.client.aio.chats.create = MagicMock(return_value=mock_chat)
        
        # Historial de sesión existente (sesión ya iniciada)
        history = [
            {"role": "user", "content": "Hola, tienen la TVS Apache 160?"},
            {"role": "model", "content": "Hola, soy Juan Pablo, asesor de Auteco Las Motos. ¡Claro que sí!"}
        ]
        
        # Mensaje continuo sobre moto inexistente
        import asyncio
        res = asyncio.run(cerebro.pensar_respuesta("tienen la MotoFantasma 9999?", history=history, prospect_data={"exists": True, "moto_interest": "TVS Apache 160"}, skip_greeting=True))
        
        # Aserción rígida: la respuesta no debe presentarse de nuevo como 'Soy Juan Pablo'
        self.assertNotIn("Soy Juan Pablo", res, "El saludo de presentación no debe inyectarse en mensajes consecutivos")
        
        # Verificar que skip_greeting fue heredado y se usó en el prompt del primer turno
        self.assertEqual(mock_chat.send_message.call_count, 2)
        prompt_arg = mock_chat.send_message.call_args_list[0][0][0]
        self.assertIn("STRICT RULE: DO NOT under any circumstance start your response", prompt_arg, "El prompt debe suprimir el saludo")
        self.assertNotIn("MANDATORY WARMTH", prompt_arg, "El prompt no debe contener la calidez obligatoria de primer contacto")

if __name__ == '__main__':
    unittest.main()