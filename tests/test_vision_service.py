import pytest
from unittest.mock import patch, MagicMock
from app.services.vision_service import VisionService

def test_vision_service_initialization():
    """
    Tests that VisionService initializes with the model ID set to gemini-2.5-flash.
    """
    mock_db = MagicMock()
    mock_db.project = "test-project-123"
    
    mock_genai_client = MagicMock()
    
    with patch("app.services.vision_service.genai.Client", return_value=mock_genai_client) as mock_client_class:
        service = VisionService(db=mock_db)
        
        # 1. Assert that service._model_id is gemini-2.5-flash
        assert service._model_id == "gemini-2.5-flash"
        
        # 2. Assert client initialization args
        mock_client_class.assert_called_once_with(
            vertexai=True,
            project="test-project-123",
            location="us-central1"
        )

@pytest.mark.asyncio
async def test_vision_service_null_payload_error():
    """
    Tests that VisionService raises a ValueError and logs with traceback
    when the GenAI API returns an empty or null response.
    """
    mock_db = MagicMock()
    mock_db.project = "test-project-123"
    
    mock_genai_client = MagicMock()
    # Mock the generate_content call to return a response with None text
    mock_response = MagicMock()
    mock_response.text = None
    mock_genai_client.models.generate_content.return_value = mock_response
    
    with patch("app.services.vision_service.genai.Client", return_value=mock_genai_client), \
         patch("app.services.vision_service.logger.exception") as mock_log_exception:
        
        service = VisionService(db=mock_db)
        
        # Call analyze_image with dummy data and expect ValueError due to null payload
        with pytest.raises(ValueError) as exc_info:
            await service.analyze_image(
                image_bytes=b"dummy_bytes",
                mime_type="image/jpeg",
                phone="573000000000",
                caption="test"
            )
        
        # Assertions
        assert "empty response or nulo payload" in str(exc_info.value)
        # Check that logger.exception was called, confirming traceback injection (Zero-Silent-Failures)
        mock_log_exception.assert_called_once()
        args, kwargs = mock_log_exception.call_args
        assert "Error analyzing image" in args[0]
