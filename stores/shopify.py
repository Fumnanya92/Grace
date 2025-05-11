import requests
import time
import logging
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz

# Constants
PRODUCT_CACHE_TTL = 300  # Cache time-to-live in seconds
SHOPIFY_API_VERSION = "2023-01"

# Globals for caching
cached_products: List[Dict[str, Any]] = []
last_product_fetch_time: float = 0

# Shopify credentials (loaded from environment variables)
SHOPIFY_STORE_NAME = "your-store-name"
SHOPIFY_PASSWORD = "your-password"

# Logger setup
logger = logging.getLogger(__name__)


def fetch_shopify_products(page: int = 1, limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch products from Shopify for a specific page."""
    url = f"https://{SHOPIFY_STORE_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_PASSWORD,
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(f"{url}?page={page}&limit={limit}", headers=headers)
        response.raise_for_status()
        return response.json().get("products", [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching products from Shopify: {e}")
        return []


def get_shopify_products(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Get Shopify products with caching mechanism."""
    global last_product_fetch_time, cached_products

    current_time = time.time()

    # Use cached products if valid
    if not force_refresh and current_time - last_product_fetch_time < PRODUCT_CACHE_TTL and cached_products:
        logger.info("Returning cached Shopify products.")
        return cached_products

    logger.info("Fetching products from Shopify...")
    products = []
    page = 1

    while True:
        page_products = fetch_shopify_products(page=page)
        if not page_products:
            break
        products.extend(page_products)
        page += 1

    # Update cache
    cached_products = products
    last_product_fetch_time = current_time
    logger.info(f"Fetched {len(products)} products from Shopify.")
    return products


def get_product_details(product_query: str) -> Optional[Dict[str, Any]]:
    """Get detailed product information from Shopify, including availability."""
    products = get_shopify_products()
    if not products:
        logger.warning("No products found in Shopify.")
        return None

    # Exact match
    for product in products:
        if product_query.lower() == product["title"].lower():
            logger.info(f"Exact match found for product: {product_query}")
            return product

    # Fuzzy match
    matched_product = fuzzy_match_product(product_query, products)
    if matched_product:
        logger.info(f"Fuzzy match found for product: {product_query}")
    else:
        logger.warning(f"No match found for product: {product_query}")
    return matched_product


def format_product_response(product: Dict[str, Any]) -> str:
    """Format a standardized product response with all key details."""
    try:
        available_stock = product["variants"][0].get("inventory_quantity", 0)
        price = product["variants"][0].get("price", "Price not available")
        product_link = f"https://{SHOPIFY_STORE_NAME}.myshopify.com/products/{product['handle']}"

        response = [
            f"✨ {product['title']} ✨",
            f"💵 Price: {price}",
            f"📦 Availability: {'In stock' if available_stock > 0 else 'Out of stock'}",
            f"{available_stock} units available" if available_stock > 0 else "",
            f"🔗 View product: {product_link}",
        ]

        # Add product description if available
        if product.get("body_html"):
            description = BeautifulSoup(product["body_html"], "html.parser").get_text()[:200]
            response.append(f"\n📝 Description: {description}...")

        return "\n".join(filter(None, response))
    except Exception as e:
        logger.error(f"Error formatting product response: {e}")
        return "Sorry, I couldn't retrieve the product details."


def is_product_query(message: str) -> bool:
    """Determine if a message is asking about a product."""
    product_keywords = [
        "have", "stock", "carry", "sell", "available",
        "product", "item", "dress", "collection",
    ]

    # Check for direct questions
    if any(word in message.lower() for word in product_keywords):
        return True

    # Check for "Do you have X?" pattern
    if re.search(r"do you (have|sell|carry|stock)", message, re.IGNORECASE):
        return True

    return False


def extract_product_name(message: str) -> Optional[str]:
    """Extract product name from a query."""
    # Handle "Do you have X?" pattern
    match = re.search(r"do you (?:have|sell|carry|stock) (.*?)\??$", message, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Handle "I'm looking for X"
    match = re.search(r"(?:looking for|want|need) (.*?)[\.\?]?$", message, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Handle direct product mentions
    product_words = ["dress", "top", "skirt", "item", "product"]
    if any(word in message.lower() for word in product_words):
        return message  # Return the whole message for fuzzy matching

    return None


def fuzzy_match_product(user_input: str, products: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Find the best matching product using fuzzy matching."""
    user_input = user_input.lower()
    matches = []

    for product in products:
        title = product["title"].lower()
        score = fuzz.token_set_ratio(user_input, title)
        if score > 70:  # Threshold for a good match
            matches.append((product, score))

    matches.sort(key=lambda x: x[1], reverse=True)
    return matches[0][0] if matches else None


def get_order_status(order_id: str) -> str:
    """Retrieve the status of an order from Shopify."""
    shopify_url = f"https://{SHOPIFY_STORE_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/orders/{order_id}.json"
    headers = {"X-Shopify-Access-Token": SHOPIFY_PASSWORD}

    try:
        response = requests.get(shopify_url, headers=headers)
        response.raise_for_status()

        order_data = response.json().get("order", {})
        status = order_data.get("fulfillment_status")
        return "Not fulfilled yet" if status is None else status
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching order status: {e}")
        return "Unable to retrieve order status. Please try again later."


def track_order(order_id: str) -> str:
    """Track the status of an order."""
    order_status = get_order_status(order_id)
    return f"Your order is currently: {order_status}"