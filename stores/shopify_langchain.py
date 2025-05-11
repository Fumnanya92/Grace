from langchain_core.runnables import RunnableLambda
from langchain_core.runnables import RunnableMap
from stores.shopify import (
    get_shopify_products,
    get_product_details,
    format_product_response,
)
import logging

# Logger setup
logger = logging.getLogger("shopify_langchain")

# --- LangChain Runnables ---

# Step 1: Fetch all Shopify products
fetch_products_runnable = RunnableLambda(
    lambda _: get_shopify_products()
)

# Step 2: Get product details for a specific query
get_product_details_runnable = RunnableLambda(
    lambda query: get_product_details(query)
)

# Step 3: Format the product response
format_response_runnable = RunnableLambda(
    lambda product: format_product_response(product)
)

# --- LangChain Pipeline ---
ShopifyProductPipeline = (
    fetch_products_runnable
    | RunnableMap({
        "query": lambda query: query,  # Pass the query through
        "products": lambda _: get_shopify_products(),  # Fetch products
    })
    | get_product_details_runnable
    | format_response_runnable
)

# --- Example Usage ---
async def fetch_and_format_product(query: str) -> str:
    """Fetch and format a product response using the LangChain pipeline."""
    try:
        response = await ShopifyProductPipeline.ainvoke(query)
        return response
    except Exception as e:
        logger.error(f"Error in Shopify product pipeline: {e}", exc_info=True)
        return "Sorry, I couldn't retrieve the product details."