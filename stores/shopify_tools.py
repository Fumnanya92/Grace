"""
LangChain tools for product lookup, order creation, and tracking.

Each tool is:
✓ Single-input (str or dict)
✓ Async-compatible
✓ Ready for ZeroShotReAct agent or OpenAI function calling
"""

from __future__ import annotations
import logging
from typing import Dict, Any
from langchain.tools import tool

from stores.shopify_async import get_product_details
from stores.shopify_orders_async import create_draft_order, get_order_status

logger = logging.getLogger("shopify_tools")

# ------------------- 🛍️ Product Lookup Tool -------------------
@tool
async def shopify_product_lookup(question: str) -> str:
    """
    Look up price and availability of a product in the Shopify store.

    Args:
        question: Natural language like "Do you have a red dress?"
    Returns:
        Formatted string with title, price, stock, and product link.
    """
    try:
        return await get_product_details(question)
    except Exception as exc:
        logger.exception("Shopify product lookup failed: %s", exc)
        return "Sorry, I couldn't retrieve live product information."

# ------------------- 🧾 Draft Order Tool -------------------
@tool
async def shopify_create_order(args: Dict[str, Any]) -> str:
    """
    Create a draft Shopify order and return a checkout link.

    Args:
        {
          "variant_id": 123456789,
          "quantity": 2,
          "email": "user@example.com"
        }

    Returns:
        A payment link or an error message.
    """
    try:
        invoice = await create_draft_order(
            line_items=[{
                "variant_id": args["variant_id"],
                "quantity": args.get("quantity", 1)
            }],
            customer_email=args["email"]
        )
        return invoice or "Could not create the order – please try again."
    except Exception as exc:
        logger.exception("Draft order creation failed: %s", exc)
        return "Sorry, I couldn't create the order."

# ------------------- 🚚 Order Tracking Tool -------------------
@tool
async def shopify_track_order(order_id: str) -> str:
    """
    Track the fulfillment status of an order.

    Args:
        order_id: Order ID or reference number

    Returns:
        Fulfillment status or an error fallback.
    """
    try:
        return await get_order_status(order_id)
    except Exception as exc:
        logger.exception("Order status check failed: %s", exc)
        return "Sorry, I couldn't retrieve that order."
