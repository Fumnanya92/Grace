"""
LangChain tools that wrap the new order‑helpers.
All tools are single‑input → compatible with ZeroShot‑ReAct agent.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional

from langchain.tools import tool
from stores.shopify_orders_async import create_draft_order, get_order_status
from stores.shopify_async import format_product_response, get_product_details

logger = logging.getLogger("shopify_tools")

# ---------- tool: look up product details (kept for completeness) ----------
@tool   # name defaults to function name
async def shopify_product_lookup(question: str) -> str:
    """Price / availability of a product in the Shopify store."""
    try:
        return await get_product_details(question)
    except Exception as exc:
        logger.exception("Shopify lookup failed: %s", exc)
        return "Sorry, I couldn't retrieve live product information."

# ---------- tool: create draft order --------------------------------------
@tool
async def shopify_create_order(args: Dict[str, Any]) -> str:
    """
    Create a draft order and return a payment link.

    Expected JSON args:
      { "variant_id": 123456789, "quantity": 2, "email": "user@example.com" }
    """
    try:
        invoice = await create_draft_order(
            line_items=[{"variant_id": args["variant_id"], "quantity": args.get("quantity", 1)}],
            customer_email=args["email"],
        )
        return invoice or "Could not create the order – please try again."
    except Exception as exc:
        logger.exception("Draft‑order error: %s", exc)
        return "Sorry, I couldn't create the order."

# ---------- tool: order tracking ------------------------------------------
@tool
async def shopify_track_order(order_id: str) -> str:
    """Return the fulfilment status of a Shopify order."""
    try:
        return await get_order_status(order_id)
    except Exception as exc:
        logger.exception("Order‑status error: %s", exc)
        return "Sorry, I couldn't retrieve that order."
