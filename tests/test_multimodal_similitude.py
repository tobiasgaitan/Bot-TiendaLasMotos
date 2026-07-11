import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.catalog_service import CatalogService
from app.services.vision_service import VisionService

def test_match_catalog_item_by_image_priority():
    """
    Test that CatalogService.match_catalog_item_by_image matches by ID first,
    then by exact image_url, then by SequenceMatcher >= 0.85.
    """
    catalog = CatalogService()
    
    # Mock items
    mock_items = [
        {
            "id": "tvs_sport",
            "name": "TVS Sport 100",
            "image_url": "https://images.com/tvs_sport.jpg",
            "price": 6200000
        },
        {
            "id": "tvs_raider",
            "name": "TVS Raider 125",
            "image_url": "https://images.com/tvs_raider.jpg",
            "price": 7500000
        },
        {
            "id": "akt_nkd",
            "name": "AKT NKD 125",
            "image_url": "https://images.com/akt_nkd.jpg",
            "price": 5200000
        }
    ]
    
    catalog._items = mock_items
    catalog._items_by_id = {item["id"]: item for item in mock_items}
    
    # 1. Match by ID
    res_id = catalog.match_catalog_item_by_image("MOTO_DETECTADA: TVS Sport | Model ID: tvs_raider")
    assert res_id is not None
    assert res_id["id"] == "tvs_raider", "Should match by ID first even if name says TVS Sport"
    
    # 2. Match by exact image_url
    res_url = catalog.match_catalog_item_by_image("MOTO_DETECTADA: AKT | Match URL: https://images.com/tvs_sport.jpg")
    assert res_url is not None
    assert res_url["id"] == "tvs_sport", "Should match by exact image_url"

    # 3. Match by SequenceMatcher (fuzzy) >= 0.85
    # SequenceMatcher of "TVS Sport 100" and "TVS Sport 100" is 1.0
    res_fuzzy = catalog.match_catalog_item_by_image("MOTO_DETECTADA: TVS Sport 100")
    assert res_fuzzy is not None
    assert res_fuzzy["id"] == "tvs_sport"

    # SequenceMatcher of "TVS Sport 10" vs "TVS Sport 100" is 0.923 (>= 0.85)
    res_fuzzy2 = catalog.match_catalog_item_by_image("TVS Sport 10")
    assert res_fuzzy2 is not None
    assert res_fuzzy2["id"] == "tvs_sport"

    # 4. Fallback search_items when SequenceMatcher < 0.85 but tokens match
    with patch.object(catalog, 'search_items', return_value=[mock_items[2]]) as mock_search:
        res_fallback = catalog.match_catalog_item_by_image("NKD")
        assert res_fallback is not None
        assert res_fallback["id"] == "akt_nkd"
        mock_search.assert_called_once_with("NKD")

def test_vision_service_catalog_serialization_anti_null_masking():
    """
    Test that VisionService logs a warning with traceback (Anti-Null Masking)
    if catalog items have empty name or image_url.
    """
    mock_db = MagicMock()
    mock_db.project = "test-project-123"
    
    mock_genai_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"type": "other", "description": "test"}'
    mock_genai_client.models.generate_content.return_value = mock_response

    # Item with missing name
    corrupt_items = [
        {"id": "bad_item_1", "name": None, "image_url": "https://img.url"},
        {"id": "bad_item_2", "name": "Victory Neo", "image_url": ""}
    ]

    with patch("app.services.vision_service.genai.Client", return_value=mock_genai_client), \
         patch("app.services.vision_service.logger.warning") as mock_log_warning:
        
        service = VisionService(db=mock_db)
        
        # Calling analyze_image with corrupt catalog items should trigger warnings
        # but NOT prevent execution if a response is returned
        service.client = mock_genai_client
        service._model_id = "gemini-2.5-flash"
        
        # We need to wrap it because analyze_image is async
        import asyncio
        asyncio.run(service.analyze_image(
            image_bytes=b"dummy",
            mime_type="image/jpeg",
            phone="12345",
            caption="test",
            catalog_items=corrupt_items
        ))
        
        # Check that logger.warning was called exactly twice (once for each corrupt item)
        assert mock_log_warning.call_count == 2
        
        args1, _ = mock_log_warning.call_args_list[0]
        assert "[INTEGRITY VIOLATION]" in args1[0]
        assert "bad_item_1" in args1[0]
        assert "Traceback:" in args1[0]

        args2, _ = mock_log_warning.call_args_list[1]
        assert "[INTEGRITY VIOLATION]" in args2[0]
        assert "bad_item_2" in args2[0]
        assert "Traceback:" in args2[0]

@pytest.mark.asyncio
async def test_incoming_image_webhook_multimodal_similitude_flow():
    """
    Verifies the integration of the multimodal similarity pipeline in the webhook flow.
    Ensures that when an image is received, it aligns with a catalog item, updates 
    moto_interest in Firestore synchronously, and sends the message using the egress pipeline.
    """
    import app.routers.whatsapp as whatsapp
    from app.routers.whatsapp import _handle_message_background
    from fastapi import BackgroundTasks
    
    whatsapp._ensure_services_sync()
    orig_debounce = whatsapp.message_buffer.debounce_seconds
    whatsapp.message_buffer.debounce_seconds = 0.0
    
    user_phone = "+573009999999"
    
    try:
        await whatsapp.message_buffer.clear_buffer(user_phone)
        if user_phone in whatsapp.message_buffer._processed_wamids:
            whatsapp.message_buffer._processed_wamids[user_phone].clear()
            
        msg_data = {
            "from": user_phone,
            "id": "wamid.multimodal_test_158",
            "type": "image",
            "image": {
                "id": "media_id_158",
                "mime_type": "image/jpeg",
                "caption": "Quiero esta moto"
            },
            "phone_number_id": "12345678"
        }
        
        mock_prospect_data = {
            "exists": True,
            "celular": user_phone,
            "chatbot_status": "ACTIVE",
            "status": "IN_PROGRESS",
            "habeas_data_accepted": True,
            "nombre": "Juan Multimodal",
            "ciudad": "Cali",
            "forma_pago": "credito",
            "moto_interest": None
        }

        # Mock memory service
        mock_ms = AsyncMock()
        mock_ms.get_prospect_data = AsyncMock(return_value=mock_prospect_data)
        mock_ms.create_prospect_if_missing = AsyncMock()
        mock_ms.get_chat_history = AsyncMock(return_value=[])
        mock_ms.save_message = AsyncMock()
        mock_ms.generate_and_update_summary = AsyncMock()
        mock_ms.update_last_interaction = AsyncMock()
        mock_ms.transition_to_in_progress = AsyncMock()
        mock_ms.set_human_help_status = AsyncMock()
        mock_ms.update_prospect_summary = AsyncMock()

        # Mock GenAI client for CerebroIA response
        mock_client = MagicMock()
        mock_chat = AsyncMock()
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_part = MagicMock()
        
        mock_part.text = "Perfecto. La TVS Sport 100 cuesta $6.200.000. Ficha Tecnica: Gran rendimiento. ![TVS Sport 100](https://img.url/tvs_sport.jpg)"
        mock_part.function_call = None
        mock_candidate.content.parts = [mock_part]
        mock_response.candidates = [mock_candidate]
        mock_chat.send_message = AsyncMock(return_value=mock_response)
        mock_client.aio.chats.create = MagicMock(return_value=mock_chat)

        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json = MagicMock(return_value={"messages": [{"id": "wamid.outbound_158"}]})

        # Mock VisionService output
        mock_vision = AsyncMock()
        mock_vision.analyze_image = AsyncMock(return_value="MOTO_DETECTADA: TVS Sport 100 | Match URL: https://img.url/tvs_sport.jpg | Model ID: tvs_sport")

        # Mock Catalog items
        mock_catalog_item = {
            "id": "tvs_sport",
            "name": "TVS Sport 100",
            "image_url": "https://img.url/tvs_sport.jpg",
            "price": 6200000,
            "category": "sport",
            "active": True
        }
        
        with patch("app.routers.whatsapp.settings") as mock_settings, \
             patch("app.routers.whatsapp.db", MagicMock()), \
             patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
             patch("app.routers.whatsapp.judge_service") as mock_judge, \
             patch("app.routers.whatsapp.VisionService", return_value=mock_vision), \
             patch("app.routers.whatsapp.storage_service.download_media", AsyncMock(return_value=b"dummy_bytes")), \
             patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_http_post, \
             patch("app.services.whatsapp_service.whatsapp_service.mark_as_read", AsyncMock()), \
             patch("app.services.ai_brain.genai.Client", return_value=mock_client), \
             patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
             patch("app.services.ai_brain.SDK_AVAILABLE", True), \
             patch.object(whatsapp.catalog_service, "_items", [mock_catalog_item]), \
             patch.object(whatsapp.catalog_service, "_items_by_id", {"tvs_sport": mock_catalog_item}):

            mock_http_post.return_value = mock_http_response
            mock_settings.whatsapp_app_secret = None
            mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

            # Execute handler
            background_tasks = BackgroundTasks()
            await _handle_message_background(msg_data, background_tasks)

            # Assert that update_prospect_summary was called to save 'moto_interest' synchronously
            mock_ms.update_prospect_summary.assert_any_call(
                user_phone, "", {"moto_interest": "TVS Sport 100"}
            )
            
            # Assert that the outbound Meta payload was built correctly with the mapped image
            assert mock_http_post.call_count == 1
            meta_payload = mock_http_post.call_args.kwargs.get("json")
            assert meta_payload is not None
            assert meta_payload.get("type") == "image"
            assert meta_payload["image"]["link"] == "https://img.url/tvs_sport.jpg"
            assert "TVS Sport 100" in meta_payload["image"]["caption"]
            assert "$6.200.000" in meta_payload["image"]["caption"]
            
    finally:
        whatsapp.message_buffer.debounce_seconds = orig_debounce
