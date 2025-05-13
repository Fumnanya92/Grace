"""
LangChain tool that answers *one* question:
↳ “What’s the price / stock / availability of a product in our Shopify store?”

• It accepts a **single string** (the user query) – so it’s compatible with
  Zero‑Shot‑ReAct / MRKL agents.
• Internally it calls the async helper `get_product_details` and blocks until
  the coroutine finishes.
"""

from __future__ import annotations

import asyncio
import logging
from langchain.tools import Tool

from stores.shopify_async import (
    get_product_details,   # ↩ async ‑ returns a ready–to–send string
    is_product_query,
)

logger = logging.getLogger("shopify_langchain")

# ---------------------------------------------------------------------------#
# blocking wrapper – agent tools must be *sync* functions
# ---------------------------------------------------------------------------#
async def _blocking_product_lookup(query: str) -> str:
    """
    Synchronous wrapper that:

      1. Ignores queries that clearly aren’t about products (returns "")
      2. Runs the async look‑up coroutine in a fresh event‑loop
         (or re‑uses the current one if already running)
      3. Propagates a short, safe error message on failure
    """
    if not is_product_query(query):
        logger.info("Not a product question → let the agent keep thinking")
        return ""                       # let the agent continue reasoning

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        return loop.run_until_complete(get_product_details(query))
    except Exception as exc:            # noqa: BLE001
        logger.exception("Shopify lookup failed: %s", exc)
        return "Sorry, I couldn't retrieve live product information."

# ---------------------------------------------------------------------------#
# LangChain Tool definition
# ---------------------------------------------------------------------------#
shopify_tool = Tool(
    name="shopify_product_lookup",
    description=(
        "Look up price, stock, or availability of a product in the Shopify "
        "store when the user asks about an item (e.g. 'Do you have the Bloom "
        "Dress in stock?')."
    ),
    func=_blocking_product_lookup,   # sync callable → required by Zero‑Shot agent
    return_direct=True,              # agent will surface the string as‑is
)

__all__ = ["shopify_tool"]
