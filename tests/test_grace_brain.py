import pytest
from modules.grace_brain import GraceBrain

@pytest.mark.asyncio
async def test_get_response_valid_key():
    response = await GraceBrain.get_response("greetings")
    assert response in GraceBrain.WHOLESALE_RESPONSES["greetings"]

@pytest.mark.asyncio
async def test_get_response_invalid_key():
    response = await GraceBrain.get_response("invalid_key")
    assert response in GraceBrain.WHOLESALE_RESPONSES["default_response"]

def test_generate_package_details():
    response = GraceBrain._generate_package_details()
    assert "PREMIUM PACKAGE" in response