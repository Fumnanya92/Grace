"""
LangChain tool to query live Shopify product information.

This module defines a LangChain tool `shopify_product_lookup` that:
1. Detects if a user query is about a product.
2. If yes, retrieves matching product details from the Shopify store (using the live API).
3. Returns a formatted text response with the product's price, stock, and availability, or an empty string if no product was found or the query is not about a product.

This tool can be used with a LangChain agent (e.g. a zero-shot-react-description agent) to answer questions about product availability.
"""
import logging
from langchain.tools import tool
from stores.shopify import get_product_details, is_product_query, format_product_response

# Logger setup
logger = logging.getLogger("shopify_langchain")

@tool("shopify_product_lookup", description="Look up price, stock, or availability of a product in the Shopify store.")
def shopify_tool(query: str) -> str:
    """Look up price, stock, or availability of a product in the Shopify store."""
    # If the query does not appear to be about a product, return no result (allow agent to continue reasoning).
    if not is_product_query(query):
        logger.info("Query is not a product inquiry: %s", query)
        return ""
    try:
        product = get_product_details(query)
        if not product:
            logger.info("No product found for query: %s", query)
            return "Sorry, I couldn't find that product."
        # If a product is found, format the product details into a response string.
        response = format_product_response(product)
        logger.info("Product lookup successful for query: %s", query)
        return response
    except Exception as exc:
        # Log the exception and return a safe error message.
        logger.exception("Shopify product lookup failed for query '%s': %s", query, exc)
        return "Sorry, I couldn't retrieve live product information."
