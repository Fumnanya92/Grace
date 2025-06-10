import sys
import os
import pytest
from unittest.mock import AsyncMock, patch

# Add the project root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.bot_responses import BotResponses
from modules.grace_brain import GraceBrain
from modules.utils import detect_picture_request, cached_list_images

@pytest.fixture
def bot_responses():
    """Fixture to initialize the BotResponses class."""
    return BotResponses()

@pytest.mark.asyncio
async def test_handle_text_message_greeting(bot_responses):
    """Test handling a greeting message."""
    with patch("modules.intent_recognition_module.recognize_intent", return_value=["greeting"]), \
         patch.object(GraceBrain, "get_response", new_callable=AsyncMock) as mock_get_response:
        mock_get_response.return_value = "Hello love! Ready to create your perfect Ankara collection?"

        response = await bot_responses.handle_text_message("test_sender", "Hi there!", [])
        assert response == "Hello love! Ready to create your perfect Ankara collection?"
        mock_get_response.assert_called_once_with("greetings")

@pytest.mark.asyncio
async def test_handle_text_message_payment(bot_responses):
    """Test handling a payment-related message."""
    with patch("modules.intent_recognition_module.recognize_intent", return_value=["payment"]), \
         patch.object(GraceBrain, "get_response", new_callable=AsyncMock) as mock_get_response:
        mock_get_response.return_value = "Payment Verified! Your deposit is confirmed love!"

        response = await bot_responses.handle_text_message("test_sender", "I sent the payment.", [])
        assert response == "Payment Verified! Your deposit is confirmed love!"
        mock_get_response.assert_called_once_with("payment_confirmed")

@pytest.mark.asyncio
async def test_handle_text_message_product_inquiry(bot_responses):
    """Test handling a product inquiry message."""
    with patch("modules.intent_recognition_module.recognize_intent", return_value=["product_inquiry"]), \
         patch("modules.utils.cached_list_images", new_callable=AsyncMock) as mock_cached_list_images, \
         patch.object(GraceBrain, "get_response", new_callable=AsyncMock) as mock_get_response:
        mock_cached_list_images.return_value = [
            {"url": "http://example.com/image1.jpg"},
            {"url": "http://example.com/image2.jpg"}
        ]
        mock_get_response.side_effect = ["Here are some of our best-selling designs:", ""]

        response = await bot_responses.handle_text_message("test_sender", "Show me your designs.", [])
        assert response == "Here are some of our best-selling designs:\nhttp://example.com/image1.jpg\nhttp://example.com/image2.jpg"

@pytest.mark.asyncio
async def test_handle_text_message_picture_request(bot_responses):
    """Test handling a picture request."""
    with patch("modules.utils.detect_picture_request", new_callable=AsyncMock) as mock_detect_picture_request, \
         patch("modules.utils.cached_list_images", new_callable=AsyncMock) as mock_cached_list_images:
        mock_detect_picture_request.return_value = True
        mock_cached_list_images.return_value = [{"url": "http://example.com/image1.jpg"}]

        response = await bot_responses.handle_text_message("test_sender", "Can I see pictures?", [])
        assert response == "Here are some of our best-selling designs:\nhttp://example.com/image1.jpg"

@pytest.mark.asyncio
async def test_handle_text_message_fallback(bot_responses):
    """Test fallback response when no intent matches."""
    with patch("modules.intent_recognition_module.recognize_intent", return_value=[]), \
         patch.object(BotResponses, "generate_grace_response", new_callable=AsyncMock) as mock_generate_grace_response:
        mock_generate_grace_response.return_value = "Hey love! How can I assist with your wholesale order today?"

        response = await bot_responses.handle_text_message("test_sender", "Random message", [])
        assert response == "Hey love! How can I assist with your wholesale order today?"
        mock_generate_grace_response.assert_called_once()

@pytest.mark.asyncio
async def test_process_intents(bot_responses):
    """Test processing intents with valid handlers."""
    with patch.object(BotResponses, "handle_greeting", new_callable=AsyncMock) as mock_handle_greeting:
        mock_handle_greeting.return_value = "Hello love!"

        response = await bot_responses.process_intents(["greeting"], "Hi there!", [])
        assert response == "Hello love!"
        mock_handle_greeting.assert_called_once_with("Hi there!", [])

@pytest.mark.asyncio
async def test_process_intents_no_match(bot_responses):
    """Test processing intents with no matching handlers."""
    response = await bot_responses.process_intents(["unknown_intent"], "Unknown message", [])
    assert response is None


@pytest.mark.asyncio
async def test_handle_text_message_track_order(bot_responses):
    """Test order tracking message with valid order ID."""
    with patch("modules.intent_recognition_module.recognize_intent", return_value=["shopify_track_order"]), \
         patch("modules.bot_responses.shopify_track_order.ainvoke", new_callable=AsyncMock) as mock_track:
        mock_track.return_value = "Shipped"
        response = await bot_responses.handle_text_message("sender", "Where is my order 5678?", [])
        mock_track.assert_awaited_once_with("5678")
        assert response == "Shipped"


@pytest.mark.asyncio
async def test_handle_text_message_track_order_no_id(bot_responses):
    """Test order tracking when no ID is present."""
    with patch("modules.intent_recognition_module.recognize_intent", return_value=["shopify_track_order"]):
        response = await bot_responses.handle_text_message("sender", "Where is my order?", [])
        assert "couldn't find an order id".lower() in response.lower()
