"""
LIVE integration test.

Runs ONLY if *all* of these environment variables are set:

  • SHOPIFY_STORE_NAME
  • SHOPIFY_PASSWORD        (a valid Admin‑API access token)
  • OPENAI_API_KEY

It spins‑up a minimal Zero‑Shot‑ReAct agent with the single
`shopify_product_lookup` tool and asks for a **REAL** product title.
Adjust `REAL_PRODUCT_TITLE` below so it exists in *your* shop.
"""

from __future__ import annotations

import os
import sys
import pytest
from dotenv import load_dotenv

load_dotenv()  # make sure .env is parsed before we test anything

# ---------------------------------------------------------------------------
# Guard‑rails – skip the whole file when creds are missing
# ---------------------------------------------------------------------------
needed = ("SHOPIFY_STORE_NAME", "SHOPIFY_PASSWORD", "OPENAI_API_KEY")
if any(not os.getenv(v) or os.getenv(v).startswith("your-") for v in needed):
    pytest.skip("🔒  Live Shopify / OpenAI credentials not configured", allow_module_level=True)

# ---------------------------------------------------------------------------
# Imports *after* the skip‑logic so CI doesn't pull heavy deps unnecessarily
# ---------------------------------------------------------------------------
from langchain_openai import OpenAI
from langchain.agents import initialize_agent, AgentType

# Add project root so `stores.*` resolves
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from stores.shopify_langchain import shopify_tool  # noqa: E402  pylint: disable=wrong-import-position


@pytest.mark.asyncio
async def test_shopify_product_lookup_via_agent() -> None:
    # Build an agent with exactly one tool
    llm = OpenAI(temperature=0)
    agent = initialize_agent(
        tools=[shopify_tool],
        llm=llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=False,
    )

    # Fire a question that must exist in your store
    REAL_PRODUCT_TITLE = "Bloom Dress"  # Adjust to match your catalog
    question = f"Do you have {REAL_PRODUCT_TITLE} in stock?"

    # Use invoke instead of run
    answer: str = await agent.invoke(question)

    # Sanity-check the reply
    assert isinstance(answer, str) and answer, "No reply from agent"
    lowered = answer.lower()
    assert ("price" in lowered) and (
        "stock" in lowered or "out of stock" in lowered
    ), f"Unexpected reply: {answer}"
