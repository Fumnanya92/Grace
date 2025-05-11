# tests/test_shopify_cursor.py
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import httpx

# import the module you just refactored
# adjust the import path to match your project structure
from stores.shopify_async import (
    fetch_shopify_products,
    get_shopify_products,
    PRODUCT_CACHE_TTL,
)

# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
FIRST_PAGE = [
    {"id": 1, "title": "Red Dress",  "variants": [{"price": "50.00"}]},
    {"id": 2, "title": "Blue Shirt", "variants": [{"price": "35.00"}]},
]
SECOND_PAGE = [
    {"id": 3, "title": "Green Skirt", "variants": [{"price": "45.00"}]},
]

def make_response(json_data, link_header: str | None, status=200):
    """Return an httpx.Response object with given JSON and headers."""
    return httpx.Response(
        status_code=status,
        json=json_data,
        headers={"Link": link_header} if link_header else {},
        request=httpx.Request("GET", "https://dummy"),
    )

# ----------------------------------------------------------------------
# 1. fetch_shopify_products: single page, no "next"
# ----------------------------------------------------------------------
@pytest.mark.asyncio
@patch("stores.shopify_async.httpx.AsyncClient")
async def test_fetch_single_page_no_next(mock_client):
    resp = make_response({"products": FIRST_PAGE}, link_header=None)
    mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=resp)

    products, next_page = await fetch_shopify_products(limit=2)

    assert products == FIRST_PAGE
    assert next_page is None
    mock_client.return_value.__aenter__.return_value.get.assert_awaited_once()

# ----------------------------------------------------------------------
# 2. fetch_shopify_products: returns next_page_info from Link header
# ----------------------------------------------------------------------
@pytest.mark.asyncio
@patch("stores.shopify_async.httpx.AsyncClient")
async def test_fetch_page_with_next(mock_client):
    link = '<https://example.myshopify.com/admin/api/2023-01/products.json?page_info=XYZ&limit=2>; rel="next"'
    resp = make_response({"products": FIRST_PAGE}, link_header=link)
    mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=resp)

    products, next_page = await fetch_shopify_products(limit=2)

    assert products == FIRST_PAGE
    assert next_page == "XYZ"

# ----------------------------------------------------------------------
# 3. get_shopify_products: paginates until no "next"
# ----------------------------------------------------------------------
@pytest.mark.asyncio
@patch("stores.shopify_async.fetch_shopify_products")
async def test_get_products_paginates(mock_fetch):
    # first call returns first page + cursor
    mock_fetch.side_effect = [
        (FIRST_PAGE, "XYZ"),
        (SECOND_PAGE, None),
    ]

    products = await get_shopify_products(force_refresh=True)

    assert len(products) == 3
    titles = [p["title"] for p in products]
    assert titles == ["Red Dress", "Blue Shirt", "Green Skirt"]
    assert mock_fetch.await_count == 2      # called twice (page‑1, page‑2)

# ----------------------------------------------------------------------
# 4. cache is used on second call (within TTL)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
@patch("stores.shopify_async.fetch_shopify_products")
async def test_cache_reuse(mock_fetch):
    # fresh fetch -> populates cache
    mock_fetch.return_value = (FIRST_PAGE, None)
    products_1 = await get_shopify_products(force_refresh=True)
    assert products_1 == FIRST_PAGE
    assert mock_fetch.await_count == 1

    # second call without refresh -> should use cache, fetch not called again
    products_2 = await get_shopify_products(force_refresh=False)
    assert products_2 == FIRST_PAGE
    assert mock_fetch.await_count == 1      # still 1 (no extra fetch)

    # wait past TTL to ensure cache expires
    await asyncio.sleep(0)
    stores.shopify_async.last_product_fetch_time -= (PRODUCT_CACHE_TTL + 1)

    # next call should trigger a new fetch
    products_3 = await get_shopify_products()
    assert mock_fetch.await_count == 2

# ----------------------------------------------------------------------
# 5. fetch_shopify_products handles HTTP error gracefully
# ----------------------------------------------------------------------
@pytest.mark.asyncio
@patch("stores.shopify_async.httpx.AsyncClient")
async def test_fetch_handles_http_error(mock_client):
    error_resp = make_response({"errors": "Bad"}, link_header=None, status=400)
    mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=error_resp)

    products, nxt = await fetch_shopify_products()
    assert products == []
    assert nxt is None
