import pytest
from unittest.mock import AsyncMock, patch
from stores.shopify_integration import (
    fetch_shopify_products,
    get_shopify_products,
    check_shopify_api_version,
    fuzzy_match_product,
    product_cache,
)

# Mock data
mock_products = [
    {"title": "Red Dress", "handle": "red-dress", "variants": [{"price": "50.00", "inventory_quantity": 10}]},
    {"title": "Blue Shirt", "handle": "blue-shirt", "variants": [{"price": "30.00", "inventory_quantity": 5}]},
    {"title": "Green Pants", "handle": "green-pants", "variants": [{"price": "40.00", "inventory_quantity": 0}]},
]

@pytest.mark.asyncio
@patch("stores.shopify_integration.get_http_client")
async def test_fetch_shopify_products(mock_http_client):
    """Test fetching products from Shopify."""
    # Mock HTTP response
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value={"products": mock_products})
    mock_response.raise_for_status = AsyncMock(return_value=None)
    mock_http_client.return_value.__aenter__.return_value.get.return_value = mock_response

    # Call the function
    products = await fetch_shopify_products(page=1, limit=2)

    # Assertions
    assert len(products) == 3
    assert products[0]["title"] == "Red Dress"
    assert products[1]["title"] == "Blue Shirt"

@pytest.mark.asyncio
@patch("stores.shopify_integration.fetch_shopify_products", new_callable=AsyncMock)
async def test_get_shopify_products(mock_fetch_shopify_products):
    """Test getting Shopify products with caching."""
    # Mock the fetch function
    mock_fetch_shopify_products.return_value = mock_products

    # First call (fetches from API)
    products = await get_shopify_products(force_refresh=True)
    assert len(products) == 3
    assert products[0]["title"] == "Red Dress"

    # Update cache and test cached response
    await product_cache.update_cache(mock_products)
    cached_products = await get_shopify_products(force_refresh=False)
    assert len(cached_products) == 3
    assert cached_products[1]["title"] == "Blue Shirt"

@pytest.mark.asyncio
@patch("stores.shopify_integration.get_http_client")
async def test_check_shopify_api_version(mock_http_client):
    """Test checking Shopify API version."""
    # Mock HTTP response
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value={"versions": [{"handle": "2025-04"}, {"handle": "2024-10"}]})
    mock_response.raise_for_status = AsyncMock(return_value=None)
    mock_http_client.return_value.__aenter__.return_value.get.return_value = mock_response

    # Call the function
    with patch("stores.shopify_integration.SHOPIFY_API_VERSION", "2024-10"):
        await check_shopify_api_version()

    # Assertions
    mock_response.json.assert_called_once()

@pytest.mark.asyncio
async def test_fuzzy_match_product():
    """Test fuzzy matching of products."""
    # Call the function
    match = await fuzzy_match_product("red dress", mock_products)

    # Assertions
    assert match is not None
    assert match["title"] == "Red Dress"

    # Test no match
    no_match = await fuzzy_match_product("yellow jacket", mock_products)
    assert no_match is None