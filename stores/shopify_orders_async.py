"""
Async helpers for creating Draft Orders and checking Order Status
-----------------------------------------------------------------
Relies on the same _client() defined in shopify_async.py
(we import it to share token, SSL context, and rate‑limit logic).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from stores.shopify_async import (
    _client,                # re‑use singleton HTTP client
    SHOPIFY_API_VERSION,
    SHOPIFY_STORE_NAME,
    SHOPIFY_TOKEN,
    RATE_LIMIT_SLEEP,
)

logger = logging.getLogger("stores.shopify_orders_async")

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
async def _post(
    url: str,
    payload: Dict[str, Any],
) -> httpx.Response | None:
    async with _client() as cli:
        try:
            r = await cli.post(url, json=payload)
            r.raise_for_status()
            return r
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                await asyncio.sleep(RATE_LIMIT_SLEEP)
                return await _post(url, payload)  # one retry
            logger.error("Shopify POST %s failed: %s", url, exc.response.text)
        except httpx.RequestError as exc:
            logger.error("Network error: %s", exc)
    return None

async def _get(url: str) -> httpx.Response | None:
    async with _client() as cli:
        try:
            r = await cli.get(url)
            r.raise_for_status()
            return r
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                await asyncio.sleep(RATE_LIMIT_SLEEP)
                return await _get(url)
            logger.error("Shopify GET %s failed: %s", url, exc.response.text)
        except httpx.RequestError as exc:
            logger.error("Network error: %s", exc)
    return None

# ---------------------------------------------------------------------
# Draft‑order creation
# ---------------------------------------------------------------------
async def create_draft_order(
    line_items: List[Dict[str, Any]],
    customer_email: str,
) -> Optional[str]:
    """
    Make a draft order and return the *invoice/checkout URL*.
    line_items → list of {"variant_id": int, "quantity": int}
    """
    url = (
        f"https://{SHOPIFY_STORE_NAME}.myshopify.com/"
        f"admin/api/{SHOPIFY_API_VERSION}/draft_orders.json"
    )
    payload = {
        "draft_order": {
            "line_items": line_items,
            "customer": {"email": customer_email},
            "use_customer_default_address": True,
        }
    }
    resp = await _post(url, payload)
    if not resp:
        return None

    data = resp.json()
    try:
        invoice_url = data["draft_order"]["invoice_url"]
        return invoice_url
    except (KeyError, TypeError):
        logger.error("Unexpected response when creating draft order: %s", data)
        return None

# ---------------------------------------------------------------------
# Order‑status lookup
# ---------------------------------------------------------------------
async def get_order_status(order_id: str) -> str:
    """
    Fetch the fulfillment status of an order from Shopify.
    """
    url = (
        f"https://{SHOPIFY_STORE_NAME}.myshopify.com/admin/api/"
        f"{SHOPIFY_API_VERSION}/orders/{order_id}/fulfillments.json"
    )
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_TOKEN,
        "Content-Type": "application/json",
    }

    async with _client() as client:
        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        except httpx.RequestError as exc:
            logger.error("Network error fetching order status: %s", exc)
            return "Sorry, I couldn’t fetch the order status due to a network issue."
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return "Order not found. Please check the order ID and try again."
            logger.error("HTTP error fetching order status: %s", exc)
            return "Sorry, I couldn’t fetch the order status due to a server issue."

        data = resp.json()
        fulfillments = data.get("fulfillments", [])
        if not fulfillments:
            return "Your order has not been fulfilled yet."

        # Extract fulfillment details
        status = fulfillments[0].get("status", "Unknown")
        tracking_numbers = fulfillments[0].get("tracking_numbers", [])
        tracking_urls = fulfillments[0].get("tracking_urls", [])
        order_status_url = fulfillments[0].get("order_status_url", "")

        # Format the response
        tracking_info = "\n".join(
            [f"Tracking Number: {num} - [Track Here]({url})" for num, url in zip(tracking_numbers, tracking_urls)]
        )
        return f"Order Status: {status}\n{tracking_info if tracking_info else 'No tracking information available.'}\nView your order: {order_status_url}"

__all__ = ["create_draft_order", "get_order_status"]
