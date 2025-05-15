from langchain.agents import initialize_agent, AgentType
from langchain_openai import OpenAI
from stores.shopify_tools import (
    shopify_product_lookup,
    shopify_create_order,
    shopify_track_order
)

agent = initialize_agent(
    tools=[shopify_product_lookup, shopify_create_order, shopify_track_order],
    llm=OpenAI(temperature=0),
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
)
