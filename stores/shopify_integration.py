import httpx
import time
import logging
from typing import List, Dict, Any, Optional
from asyncio import Lock
from contextlib import asynccontextmanager
from fuzzywuzzy import fuzz
from config import config

# Constants
PRODUCT_CACHE_TTL = 300  # Cache time-to-live in seconds
SHOPIFY_API_VERSION = "2025-04"
FUZZY_THRESHOLD = 70  # Threshold for fuzzy matching

# Shopify credentials (loaded from config)
SHOPIFY_STORE_NAME = config.SHOPIFY["store_name"]
SHOPIFY_PASSWORD = config.SHOPIFY["password"]

# Logger setup
logger: logging.Logger = logging.getLogger("shopify_integration")

# Product Cache class
class ProductCache:
    def __init__(self):
        self.cached_products: List[Dict[str, Any]] = []
        self.last_fetch_time: float = 0
        self.lock = Lock()

    async def get_cached_products(self) -> List[Dict[str, Any]]:
        async with self.lock:
            return self.cached_products

    async def update_cache(self, products: List[Dict[str, Any]]) -> None:
        async with self.lock:
            self.cached_products = products
            self.last_fetch_time = time.time()

product_cache = ProductCache()

@asynccontextmanager
async def get_http_client():
    """Create an HTTP client with follow_redirects and timeout."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        yield client

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
            await response.raise_for_status()
            data = await response.json()
            return data.get("products", [])
        except httpx.RequestError as e:
            logger.error(f"Network error: {e}")
        except httpx.HTTPStatusError as e:
            logger.error(f"Shopify returned bad status {e.response.status_code}: {e.response.text}")
        return []

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

async def check_shopify_api_version():
    """Check if the current API version is outdated."""
    url = f"https://{SHOPIFY_STORE_NAME}.myshopify.com/admin/api/versions.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_PASSWORD,
        "Content-Type": "application/json",
    }

    async with get_http_client() as client:
        try:
            response = await client.get(url, headers=headers)
            await response.raise_for_status()
            response_data = await response.json()
            latest_version = response_data.get("versions", [])[-1].get("handle")

            if SHOPIFY_API_VERSION != latest_version:
                logger.warning(
                    f"⚠️ Your Shopify API version '{SHOPIFY_API_VERSION}' is outdated. "
                    f"The latest version is '{latest_version}'. Please update to avoid issues."
                )
            else:
                logger.info(f"✅ Your Shopify API version '{SHOPIFY_API_VERSION}' is up-to-date.")
        except httpx.RequestError as e:
            logger.error(f"Network error while checking API version: {e}")
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch API versions: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logger.exception(f"Unexpected error while checking API version: {e}")

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