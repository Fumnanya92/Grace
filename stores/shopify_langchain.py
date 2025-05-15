import logging
from langchain_community.tools import tool
from stores.shopify_async import get_product_details, is_product_query

logger = logging.getLogger("shopify_langchain")

@tool  # Uses function name and docstring for metadata
async def shopify_product_lookup(query: str) -> str:
    """Look up price, stock, or availability of a product in the Shopify store."""
    if not is_product_query(query):
        logger.info("Message is not a product inquiry: %s", query)
        return ""
    try:
        reply = await get_product_details(query)
        logger.info("Product lookup successful for query: %s", query)
        return reply
    except Exception as exc:
        logger.exception("Shopify product lookup failed for query '%s': %s", query, exc)
        return "Sorry, I couldn't retrieve live product information."

# Example: Inspecting tool metadata
print(shopify_product_lookup.name)        # "shopify_product_lookup"
print(shopify_product_lookup.description) # "Look up price, stock, or availability of a product in the Shopify store."
print(shopify_product_lookup.args)        # JSON schema of the arguments
