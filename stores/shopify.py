import httpx
import time
import logging
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz
from config import config
from asyncio import Lock
from contextlib import asynccontextmanager

# Constants
PRODUCT_CACHE_TTL = 300  # Cache time-to-live in seconds
SHOPIFY_API_VERSION = "2023-01"
FUZZY_THRESHOLD = 70  # Threshold for fuzzy matching

# Shopify credentials from Config
SHOPIFY_STORE_NAME = config.SHOPIFY["store_name"]
SHOPIFY_PASSWORD = config.SHOPIFY["password"]

# Logger setup
logger: logging.Logger = logging.getLogger("shopify_async")

# Product Cache class
class ProductCache:
    def __init__(self):
        self.cached_products: List[Dict[str, Any]] = []
        self.last_fetch_time: float = 0
        self.lock = Lock()

    async def get_cached_products(self):
        async with self.lock:
            return self.cached_products

    async def update_cache(self, products: List[Dict[str, Any]]):
        async with self.lock:
            self.cached_products = products
            self.last_fetch_time = time.time()

product_cache = ProductCache()

@asynccontextmanager
async def get_http_client():
    async with httpx.AsyncClient() as client:
        yield client

# Async product fetch
async def fetch_shopify_products(page: int = 1, limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch products from Shopify for a specific page."""
    url = f"https://{SHOPIFY_STORE_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_PASSWORD,
        "Content-Type": "application/json",
    }

    async with get_http_client() as client:
        try:
            response = await client.get(f"{url}?page={page}&limit={limit}", headers=headers)
            response.raise_for_status()
            return response.json().get("products", [])
        except httpx.RequestError as e:
            logger.error(f"Network error: {e}")
        except httpx.HTTPStatusError as e:
            logger.error(f"Shopify returned bad status {e.response.status_code}: {e.response.text}")
        return []


# Async get all products with caching
async def get_shopify_products(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Get Shopify products with caching mechanism."""
    current_time = time.time()
    cached_products = await product_cache.get_cached_products()

    if not force_refresh and current_time - product_cache.last_fetch_time < PRODUCT_CACHE_TTL and cached_products:
        logger.info("Returning cached Shopify products.")
        return cached_products

    logger.info("Fetching products from Shopify...")
    products = []
    page = 1

    while True:
        page_products = await fetch_shopify_products(page=page)
        if not page_products:
            break
        products.extend(page_products)
        page += 1

    await product_cache.update_cache(products)
    logger.info(f"Fetched {len(products)} products from Shopify.")
    return products


# Fuzzy match
async def fuzzy_match_product(user_input: str, products: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Find the best matching product using fuzzy matching."""
    user_input = user_input.lower()
    matches = []

    for product in products:
        title = product["title"].lower()
        score = fuzz.token_set_ratio(user_input, title)
        if score > FUZZY_THRESHOLD:
            matches.append((product, score))

    matches.sort(key=lambda x: x[1], reverse=True)
    logger.debug(f"Top fuzzy matches: {[s for _, s in matches[:3]]}")
    return matches[0][0] if matches else None


# Format response
def format_product_response(product: Dict[str, Any]) -> str:
    """Format a standardized product response with all key details."""
    try:
        variants = product.get("variants", [])
        if not variants:
            return "Product has no variants available."

        variant = variants[0]
        available_stock = variant.get("inventory_quantity", 0)
        price = variant.get("price", "N/A")
        product_link = f"https://{SHOPIFY_STORE_NAME}.myshopify.com/products/{product['handle']}"

        parts = [
            f"✨ {product['title']} ✨",
            f"💵 Price: {price}",
            f"📦 Availability: {'In stock' if available_stock > 0 else 'Out of stock'}",
            f"{available_stock} units available" if available_stock > 0 else "",
            f"🔗 View product: {product_link}",
        ]

        if product.get("body_html"):
            desc = BeautifulSoup(product["body_html"], "html.parser").get_text()[:200]
            parts.append(f"📝 Description: {desc}...")

        return "\n".join(filter(None, parts))
    except Exception as e:
        logger.error(f"Failed to format product: {e}")
        return "Sorry, I couldn't fetch the product details."


# Extract product name
PRODUCT_PATTERNS = {
    "have": r"do you (?:have|sell|carry|stock) (.*?)\??$",
    "need": r"(?:looking for|want|need) (.*?)[\.\?]?$",
}

def extract_product_name(message: str) -> Optional[str]:
    """Extract product name from a query."""
    import re
    for pattern in PRODUCT_PATTERNS.values():
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return message.strip()


# Determine if product inquiry
def is_product_query(message: str) -> bool:
    """Determine if a message is asking about a product."""
    keywords = ["have", "stock", "carry", "sell", "available", "product", "item", "dress", "collection"]
    return any(word in message.lower() for word in keywords)


# Async full product lookup
async def get_product_details(message: str) -> Optional[str]:
    """High-level interface to fetch and format product details."""
    if not is_product_query(message):
        return None

    try:
        products = await get_shopify_products()
        if not products:
            return "I couldn't find any products at the moment."

        product_name = extract_product_name(message)
        if not product_name:
            return "I couldn't figure out which product you're asking about."

        match = await fuzzy_match_product(product_name, products)
        if not match:
            return f"Sorry, nothing matched '{product_name}' in our shop right now."

        return format_product_response(match)

    except Exception as e:
        logger.exception(f"Error during product lookup: {e}")
        return "Oops, something went wrong while checking our product list."
