# Re-run after kernel reset to restore environment and perform the async Shopify refactor.

import httpx
import time
import logging
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz
import os
from dotenv import load_dotenv

load_dotenv()

# Constants
PRODUCT_CACHE_TTL = 300  # 5 minutes
SHOPIFY_API_VERSION = "2023-01"

# Environment variables
SHOPIFY_STORE_NAME = os.getenv("SHOPIFY_STORE_NAME", "demo-store")
SHOPIFY_PASSWORD = os.getenv("SHOPIFY_PASSWORD", "demo-password")

# Globals for caching
cached_products: List[Dict[str, Any]] = []
last_product_fetch_time: float = 0

# Logger
logger = logging.getLogger("shopify_async")

# Async product fetch
async def fetch_shopify_products(page: int = 1, limit: int = 50) -> List[Dict[str, Any]]:
    url = f"https://{SHOPIFY_STORE_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_PASSWORD,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{url}?page={page}&limit={limit}", headers=headers)
            response.raise_for_status()
            return response.json().get("products", [])
        except httpx.HTTPError as e:
            logger.error(f"Error fetching products from Shopify: {e}")
            return []

# Async get all products with caching
async def get_shopify_products(force_refresh: bool = False) -> List[Dict[str, Any]]:
    global last_product_fetch_time, cached_products

    current_time = time.time()
    if not force_refresh and current_time - last_product_fetch_time < PRODUCT_CACHE_TTL and cached_products:
        logger.info("Returning cached Shopify products.")
        return cached_products

    logger.info("Fetching Shopify products...")
    products = []
    page = 1

    while True:
        page_products = await fetch_shopify_products(page=page)
        if not page_products:
            break
        products.extend(page_products)
        page += 1

    cached_products = products
    last_product_fetch_time = current_time
    logger.info(f"Fetched {len(products)} products from Shopify.")
    return products

# Fuzzy match
async def fuzzy_match_product(user_input: str, products: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    user_input = user_input.lower()
    matches = []

    for product in products:
        title = product["title"].lower()
        score = fuzz.token_set_ratio(user_input, title)
        if score > 70:
            matches.append((product, score))

    matches.sort(key=lambda x: x[1], reverse=True)
    return matches[0][0] if matches else None

# Format response
def format_product_response(product: Dict[str, Any]) -> str:
    try:
        available_stock = product["variants"][0].get("inventory_quantity", 0)
        price = product["variants"][0].get("price", "N/A")
        product_link = f"https://{SHOPIFY_STORE_NAME}.myshopify.com/products/{product['handle']}"

        parts = [
            f"✨ {product['title']} ✨",
            f"💵 Price: {price}",
            f"📦 Availability: {'In stock' if available_stock > 0 else 'Out of stock'}",
            f"{available_stock} units available" if available_stock > 0 else "",
            f"🔗 View product: {product_link}"
        ]

        if product.get("body_html"):
            desc = BeautifulSoup(product["body_html"], "html.parser").get_text()[:200]
            parts.append(f"📝 Description: {desc}...")

        return "\n".join(filter(None, parts))
    except Exception as e:
        logger.error(f"Failed to format product: {e}")
        return "Sorry, I couldn't fetch the product details."

# Extract name
def extract_product_name(message: str) -> Optional[str]:
    import re
    match = re.search(r"do you (?:have|sell|carry|stock) (.*?)\??$", message, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    match = re.search(r"(?:looking for|want|need) (.*?)[\.\?]?$", message, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return message.strip()

# Determine if product inquiry
def is_product_query(message: str) -> bool:
    keywords = ["have", "stock", "carry", "sell", "available", "product", "item", "dress", "collection"]
    return any(word in message.lower() for word in keywords)

# Async full product lookup
async def get_product_details(message: str) -> Optional[str]:
    if not is_product_query(message):
        return None

    products = await get_shopify_products()
    if not products:
        return "No products found."

    product_name = extract_product_name(message)
    if not product_name:
        return "Could not determine which product you meant."

    match = await fuzzy_match_product(product_name, products)
    if not match:
        return f"Couldn't find any product similar to '{product_name}'."

    return format_product_response(match)
