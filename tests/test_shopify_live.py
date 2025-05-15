import os
import pytest
from langchain_openai import OpenAI
from langchain.agents import initialize_agent, AgentType

# Adjust sys.path for local module imports
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the tool
from stores.shopify_langchain import shopify_product_lookup as shopify_tool


@pytest.mark.asyncio
async def test_shopify_product_lookup_via_agent() -> None:
    """Test that the async Shopify tool works correctly via LangChain agent."""
    llm = OpenAI(temperature=0)
    agent = initialize_agent(
        tools=[shopify_tool],
        llm=llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=False,
    )

    product_name = os.getenv("REAL_PRODUCT_TITLE", "Bloom Dress")
    query = f"Do you have {product_name} in stock?"

    try:
        # Run the agent (invoke expects a dict input)
        result = await agent.ainvoke({"input": query})
        answer = result.get("output", "")
    except Exception as e:
        pytest.fail(f"Agent invocation failed: {e}")

    # Validation
    assert isinstance(answer, str) and answer.strip(), f"No reply from agent: {answer}"
    lowered = answer.lower()
    assert "price" in lowered, "Missing price info in agent response"
    assert "stock" in lowered or "out of stock" in lowered, "Missing stock info in agent response"
