import pytest
from unittest.mock import AsyncMock, patch
import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from stores.shopify import (
    fetch_shopify_products,
    get_shopify_products,
    fuzzy_match_product,
    format_product_response,
    extract_product_name,
    is_product_query,
    get_product_details,
)

# Mock data
mock_products = [
    {
        "title": "Red Dress",
        "handle": "red-dress",
        "variants": [{"price": "50.00", "inventory_quantity": 10}],
        "body_html": "<p>A beautiful red dress for any occasion.</p>",
    },
    {
        "title": "Blue Shirt",
        "handle": "blue-shirt",
        "variants": [{"price": "30.00", "inventory_quantity": 5}],
        "body_html": "<p>A stylish blue shirt for casual wear.</p>",
    },
]

# Test fetch_shopify_products
@pytest.mark.asyncio
@patch("stores.shopify.httpx.AsyncClient")
async def test_fetch_shopify_products(mock_client):
    """Test fetching products from Shopify."""
    # Mock the response object
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value={"products": mock_products})
    mock_response.raise_for_status = AsyncMock()

    # Mock the AsyncClient context manager
    mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

    # Call the function
    products = await fetch_shopify_products(page=1, limit=2)

    # Assertions
    assert len(products) == 2
    assert products[0]["title"] == "Red Dress"
    assert products[1]["title"] == "Blue Shirt"


# Test get_shopify_products with caching
@pytest.mark.asyncio
@patch("stores.shopify.fetch_shopify_products", new_callable=AsyncMock)
async def test_get_shopify_products(mock_fetch):
    """Test fetching products with caching."""
    mock_fetch.return_value = mock_products

    # First call (fetches from API)
    products = await get_shopify_products(force_refresh=True)
    assert len(products) == 2
    assert products[0]["title"] == "Red Dress"

    # Second call (uses cache)
    products_cached = await get_shopify_products(force_refresh=False)
    assert len(products_cached) == 2
    assert products_cached[0]["title"] == "Red Dress"


# Test fuzzy_match_product
@pytest.mark.asyncio
async def test_fuzzy_match_product():
    """Test fuzzy matching of product names."""
    match = await fuzzy_match_product("red dress", mock_products)
    assert match is not None
    assert match["title"] == "Red Dress"

    no_match = await fuzzy_match_product("green pants", mock_products)
    assert no_match is None


# Test format_product_response
def test_format_product_response():
    """Test formatting of product details."""
    response = format_product_response(mock_products[0])
    assert "Red Dress" in response
    assert "Price: 50.00" in response
    assert "In stock" in response
    assert "10 units available" in response


# Test extract_product_name
def test_extract_product_name():
    """Test extraction of product names from user queries."""
    assert extract_product_name("Do you have a red dress?") == "red dress"
    assert extract_product_name("I'm looking for a blue shirt.") == "blue shirt"
    assert extract_product_name("What about a green skirt?") == "green skirt"


# Test is_product_query
def test_is_product_query():
    """Test detection of product-related queries."""
    assert is_product_query("Do you have a red dress?") is True
    assert is_product_query("What are your business hours?") is False


# Test get_product_details
@pytest.mark.asyncio
@patch("stores.shopify.get_shopify_products", new_callable=AsyncMock)
async def test_get_product_details(mock_get_products):
    """Test high-level product lookup."""
    mock_get_products.return_value = mock_products

    # Valid product query
    response = await get_product_details("Do you have a red dress?")
    assert "Red Dress" in response
    assert "Price: 50.00" in response

    # Invalid product query
    response = await get_product_details("Do you have a green skirt?")
    assert "Couldn't find any product similar to 'green skirt'." in response

    # Non-product query
    response = await get_product_details("What are your business hours?")
    assert response is None