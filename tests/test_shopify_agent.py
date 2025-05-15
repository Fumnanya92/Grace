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
    """Test product lookup tool via LangChain agent."""
    agent = initialize_agent(
        tools=[shopify_product_lookup],
        llm=OpenAI(temperature=0),
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
    )
    question = "Do you have a red dress in stock?"
    result = await agent.ainvoke({"input": question})
    print("Agent output:", result["output"])  # <-- Add this line
    assert isinstance(result["output"], str) and "Price" in result["output"], f"Unexpected response: {result['output']}"

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_shopify_product_lookup_tool())
