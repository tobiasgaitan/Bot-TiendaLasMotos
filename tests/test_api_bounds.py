import pytest
import hmac
import hashlib
import json
from fastapi.testclient import TestClient
from fastapi import HTTPException
from unittest.mock import patch, AsyncMock, MagicMock
from app.main import app
from app.core.config import settings
from app.services.whatsapp_service import whatsapp_service
from app.services.catalog_service import catalog_service
from app.services.config_service import config_service

client = TestClient(app)

def test_webhook_signature_missing():
    # Send request without signature header
    response = client.post("/webhook", json={"foo": "bar"})
    assert response.status_code == 401
    assert "Signature missing" in response.json()["detail"]

def test_webhook_signature_invalid():
    # Send request with invalid signature header
    headers = {"X-Hub-Signature-256": "sha256=invalid_signature_hex"}
    response = client.post("/webhook", json={"foo": "bar"}, headers=headers)
    assert response.status_code == 401
    assert "Signature mismatch" in response.json()["detail"]

def test_webhook_signature_valid():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123456",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "1234567890", "phone_number_id": "1234567890"},
                    "messages": [{
                        "from": "573000000000",
                        "id": "msg_123",
                        "timestamp": "1622548800",
                        "text": {"body": "test message"},
                        "type": "text"
                    }]
                },
                "field": "messages"
            }]
        }]
    }
    
    raw_body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    signature = "sha256=" + hmac.new(
        settings.whatsapp_app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()
    
    headers = {"X-Hub-Signature-256": signature, "Content-Type": "application/json"}
    
    # Mock services so it doesn't try to call Meta or Firestore
    with patch("app.routers.whatsapp._is_valid_message", return_value=True), \
         patch("app.routers.whatsapp._extract_message_data", return_value={"from": "573000000000", "id": "msg_123", "type": "text", "text": "test"}), \
         patch("app.routers.whatsapp.BackgroundTasks.add_task") as mock_add_task:
        
        response = client.post("/webhook", content=raw_body, headers=headers)
        assert response.status_code == 200
        assert response.json() == {"status": "received"}

@pytest.mark.asyncio
async def test_template_components_payload_sanity():
    to_phone = "573000000000"
    template_name = "test_template"
    language_code = "es_CO"
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={"messages": [{"id": "wamid.123"}]})
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        
        # Test empty components
        await whatsapp_service.send_template_message(
            to_phone=to_phone,
            template_name=template_name,
            language_code=language_code,
            components=[]
        )
        called_args = mock_post.call_args[1]
        called_payload = called_args["json"]
        assert "components" not in called_payload["template"]

        # Test components with only None or empty strings
        await whatsapp_service.send_template_message(
            to_phone=to_phone,
            template_name=template_name,
            language_code=language_code,
            components=[None, "", "  "]
        )
        called_args = mock_post.call_args[1]
        called_payload = called_args["json"]
        assert "components" not in called_payload["template"]

        # Test components with a dict containing empty parameters
        await whatsapp_service.send_template_message(
            to_phone=to_phone,
            template_name=template_name,
            language_code=language_code,
            components=[{"type": "body", "parameters": []}]
        )
        called_args = mock_post.call_args[1]
        called_payload = called_args["json"]
        assert "components" not in called_payload["template"]

        # Test components with valid values (should include components)
        await whatsapp_service.send_template_message(
            to_phone=to_phone,
            template_name=template_name,
            language_code=language_code,
            components=["Valid Parameter"]
        )
        called_args = mock_post.call_args[1]
        called_payload = called_args["json"]
        assert "components" in called_payload["template"]
        assert called_payload["template"]["components"][0]["parameters"][0]["text"] == "Valid Parameter"

def test_pcc_ficha_tecnica_content_assertion():
    """
    Test unitario de aserción de contenido para Ficha Tecnica.
    Verifica que la cadena 'Ficha Tecnica:' esté presente y no resulte en None/vacío,
    incluso si ocurren mutaciones de llaves.
    """
    mock_item = {
        "id": "1",
        "name": "TVS Sport 100",
        "price": 5000000,
        "cc": 100,
        "category": "Urban",
        "image_url": "http://img.url/tvs",
        "link": "http://link.url/tvs",
        "description": "Economica y rendidora.",
        "summary": "Excelente moto TVS Sport 100.",
        "search_tokens": ["tvs", "sport", "100", "urban"],
        "search_text": "tvs sport 100 urban",
        "searchBy": ["tvs", "sport", "100"]
    }
    
    with patch.object(catalog_service, '_items', [mock_item]), \
         patch.object(catalog_service, '_db', MagicMock()), \
         patch.object(config_service, '_financial_config', None), \
         patch.object(config_service, 'get_registration_cost', return_value=0):
        
        catalog_service.load_configurations = MagicMock()
        catalog_service._cache_service.clear()
        
        res = catalog_service.search_catalog("TVS")
        
        # 1. Aserción de presencia explícita
        assert "Ficha Tecnica:" in res, "Debe incluir la etiqueta de la Ficha Técnica."
        
        # 2. Aserción de no-nulo y no-vacío
        import re
        match = re.search(r"Ficha Tecnica:\s*(.+)", res)
        assert match is not None, "El valor de Ficha Tecnica no debe estar vacío."
        val = match.group(1).strip()
        assert val != "", "El valor de la Ficha Técnica no puede ser una cadena vacía."
        assert val != "None", "El valor de la Ficha Técnica no puede ser la cadena 'None' silenciosa."
