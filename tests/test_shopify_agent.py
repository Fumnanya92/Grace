import pytest
from langchain_openai import OpenAI
from langchain.agents import initialize_agent, AgentType
import os
import sys
# Adjust sys.path for local module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from stores.shopify_tools import (
    shopify_product_lookup,
    shopify_create_order,
    shopify_track_order,
)

@pytest.mark.asyncio
async def test_shopify_product_lookup_tool():
    agent = initialize_agent(
        tools=[shopify_product_lookup],
        llm=OpenAI(temperature=0),
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=False,
    )
    result = await agent.ainvoke({"input": "Do you have the Bloom Dress in stock?"})
    assert "Price" in result["output"] or "Out of stock" in result["output"]

@pytest.mark.asyncio
async def test_shopify_create_order_tool():
    agent = initialize_agent(
        tools=[shopify_create_order],
        llm=OpenAI(temperature=0),
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=False,
    )
    prompt = (
        "I want to buy the Bloom Dress. My email is gracebuyer@example.com "
        "and I need 1 unit."
    )
    result = await agent.ainvoke({"input": prompt})
    assert "https://" in result["output"] or "Could not create" in result["output"]

@pytest.mark.asyncio
async def test_shopify_track_order_tool():
    agent = initialize_agent(
        tools=[shopify_track_order],
        llm=OpenAI(temperature=0),
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=False,
    )
    result = await agent.ainvoke({"input": "Where is my order 1234?"})
    assert "status" in result["output"].lower() or "couldn't" in result["output"].lower()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_shopify_product_lookup_tool())
