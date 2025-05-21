from __future__ import annotations

import asyncio
import logging
import re
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Tuple, AsyncGenerator
from urllib.parse import parse_qs, urlsplit

import httpx
import certifi
import truststore
import ssl
from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz

from config import config  # central secrets

PRODUCT_CACHE_TTL = 300          # seconds
FUZZY_THRESHOLD   = 60           # fuzzywuzzy score
RATE_LIMIT_SLEEP  = 0.6          # Shopify allows 2 rps

SHOPIFY_API_VERSION = config.SHOPIFY.get("api_version", "2025-04")
SHOPIFY_STORE_NAME  = config.SHOPIFY["store_name"]
SHOPIFY_TOKEN       = config.SHOPIFY["password"]  # Use 'password' as defined in config

logger = logging.getLogger("stores.shopify_async")

_cached_products: List[Dict[str, Any]] = []
_last_fetch_time: float = 0.0

_async_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def _client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Yield a singleton AsyncClient with redirects + timeout."""
    global _async_client
    if _async_client is None or _async_client.is_closed:
        # Use truststore for SSL verification
        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        _async_client = httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            verify=ctx  # Use the truststore SSL context
        )
    try:
        yield _async_client
    finally:
        pass


async def _fetch_page(
    client: httpx.AsyncClient,
    page_info: str | None = None,
    limit: int = 50,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Fetch one page of products. Returns (products, next_page_info_or_None).
    """
    url = (
        f"https://{SHOPIFY_STORE_NAME}.myshopify.com/admin/api/"
        f"{SHOPIFY_API_VERSION}/products.json"
    )
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_TOKEN,
        "Content-Type": "application/json",
    }
    params = {"limit": limit}
    if page_info:
        params["page_info"] = page_info

    try:
        resp = await client.get(url, headers=headers, params=params, follow_redirects=True)
        resp.raise_for_status()
    except httpx.RequestError as exc:
        logger.error("Network error fetching Shopify products: %s", exc)
        return [], None
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code == 429:  # Handle rate-limiting
            retry = int(exc.response.headers.get("Retry-After", "1"))
            logger.warning("Rate-limited by Shopify (sleep %ss)…", retry)
            await asyncio.sleep(retry)
            return await _fetch_page(client, page_info, limit)

        logger.error("HTTP %s from Shopify: %s", code, exc.response.text)
        return [], None

    data = resp.json()
    products = data.get("products", [])

    # Parse Link header for next page_info
    next_info: str | None = None
    link_header = resp.headers.get("Link")
    if link_header:
        for part in link_header.split(","):
            part = part.strip()
            if 'rel="next"' in part:
                url_part = part.split(";")[0].lstrip("<").rstrip(">")
                next_info_qs = parse_qs(urlsplit(url_part).query).get("page_info")
                if next_info_qs:
                    next_info = next_info_qs[0]
                break

    return products, next_info

async def get_shopify_products(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Return a **copy** of the full product list.

    Uses cursor‑based pagination under the hood and respects an in‑memory TTL
    cache to avoid hitting Shopify unnecessarily.
    """
    global _cached_products, _last_fetch_time

    now = time.time()
    fresh = (now - _last_fetch_time) < PRODUCT_CACHE_TTL
    if (not force_refresh) and fresh and _cached_products:
        logger.info("Returning %d cached products.", len(_cached_products))
        return _cached_products.copy()

    logger.info("Fetching products from Shopify…")
    products: List[Dict[str, Any]] = []
    next_cursor: str | None = None

    async with _client() as cli:
        while True:
            page, next_cursor = await _fetch_page(cli, page_info=next_cursor)
            if not page:
                break
            products.extend(page)
            if not next_cursor:
                break
            await asyncio.sleep(RATE_LIMIT_SLEEP)   # stay under 2 rps

    _cached_products = products
    _last_fetch_time = now
    logger.info("Fetched %d total products.", len(products))
    return products.copy()  # return defensive copy


def _fuzzy_match_product(name: str, products: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Improved fuzzy matching: match against title and handle, fallback to substring.
    """
    name = name.lower().strip()
    best: Tuple[int, Dict[str, Any]] | None = None
    for p in products:
        title = p["title"].lower()
        handle = p.get("handle", "").replace("-", " ").lower()
        score_title = fuzz.token_set_ratio(name, title)
        score_handle = fuzz.token_set_ratio(name, handle)
        logger.debug(f"Fuzzy score for '{name}' vs '{title}': {score_title}, handle: {score_handle}")
        score = max(score_title, score_handle)
        if score >= FUZZY_THRESHOLD and (best is None or score > best[0]):
            best = (score, p)
    # Fallback: substring match if no fuzzy match
    if not best:
        for p in products:
            if name in p["title"].lower() or name in p.get("handle", "").replace("-", " ").lower():
                return p
    # Fallback: partial word match
    if not best:
        for p in products:
            if any(word in p["title"].lower() for word in name.split()):
                return p
    return best[1] if best else None


def _format_product(p: Dict[str, Any]) -> str:
    """
    Format product details, including image URL if available.
    """
    image_url = None
    if p.get("images"):
        image_url = p["images"][0].get("src")
    variants = p.get("variants", [])
    price = variants[0].get("price", "N/A") if variants else "N/A"
    stock = variants[0].get("inventory_quantity", 0) if variants else 0
    link  = f"https://{SHOPIFY_STORE_NAME}.myshopify.com/products/{p['handle']}"
    body  = BeautifulSoup(p.get("body_html", ""), "html.parser").get_text()[:200]
    parts = []
    if image_url:
        parts.append(image_url)
    parts += [
        f"✨ {p['title']} ✨",
        f"💵 Price: {price}",
        f"📦 {'In stock' if stock > 0 else 'Out of stock'} ({stock})",
        f"🔗 {link}",
        f"📝 {body}…" if body else "",
    ]
    return "\n".join(filter(None, parts))


def format_product_response(product: dict) -> str:
    """
    Format product details into a human-readable string.
    """
    image_url = product.get("image_url")
    lines = []
    if image_url:
        lines.append(image_url)
    return "\n".join(lines)


def is_product_query(message: str) -> bool:
    """
    Robustly determine if a message is a product query using keywords, regex, and fuzzy matching.
    """
    message = message.lower().strip()
    # Direct keyword check
    kws = [
        "have", "stock", "carry", "sell", "price", "available", "product", "dress", "shirt",
        "show", "set", "piece", "outfit", "want", "get", "buy"
    ]
    if any(k in message for k in kws):
        return True

    # Regex for common product query patterns
    patterns = [
        r"\bdo you have\b",
        r"\bshow me\b",
        r"\bi want\b",
        r"\bcan i get\b",
        r"\bhave you got\b",
        r"\bwhat(?:'s| is) the price\b",
        r"\bhow much\b",
        r"\bavailable\b",
        r"\bin stock\b",
    ]
    if any(re.search(pat, message) for pat in patterns):
        return True

    # Fuzzy match: if message is close to any keyword (score >= 80)
    for k in kws:
        if fuzz.partial_ratio(message, k) >= 80:
            return True

    return False


def _extract_query_name(question: str) -> str:
    """
    Extract the product name from the question, removing common prefixes and polite words,
    but do NOT remove single-letter words like 'a' or 'an' that may be part of product names.
    """
    question = question.lower()
    # Remove common leading phrases
    for prefix in ["do you have", "show me", "i want", "can i get", "have you got"]:
        if question.startswith(prefix):
            question = question[len(prefix):]
    # Remove only truly unnecessary words
    for word in ["in stock", "please", "the"]:
        question = question.replace(word, "")
    return question.strip()


async def get_product_details(question: str) -> str:
    """
    Fetch product details based on the question and return a human-readable answer.
    """
    logger.info("Received question: %s", question)

    # Check if the question is a valid product query
    if not is_product_query(question):
        logger.warning("The question does not look like a product-related query.")
        return "That doesn’t look like a product question."

    # Fetch all products
    try:
        prods = await get_shopify_products()
        logger.info("Fetched %d products from Shopify.", len(prods))
    except Exception as e:
        logger.error("Error fetching products from Shopify: %s", e)
        return "Sorry, I can’t reach the store right now."

    # Extract the product name from the question
    query_name = _extract_query_name(question)
    logger.info("Extracted query name: %s", query_name)

    # Perform a fuzzy match to find the product
    match = _fuzzy_match_product(query_name, prods)
    if not match:
        logger.warning("No matching product found for query: %s", query_name)
        return f"Couldn’t find anything similar to “{query_name}”."

    # Format and return the product details (with image URL if available)
    formatted_product = _format_product(match)
    logger.info("Formatted product details: %s", formatted_product)
    return formatted_product


async def get_products_for_image_matching() -> list[dict]:
    """
    Return products as a list of dicts with id, name, image_url, price, etc.
    Suitable for image matching/catalog loading.
    """
    products = await get_shopify_products()
    result = []
    for p in products:
        image_url = None
        if p.get("images"):
            image_url = p["images"][0].get("src")
        result.append({
            "id": p.get("id"),
            "name": p.get("title"),
            "image_url": image_url,
            "price": p.get("variants", [{}])[0].get("price"),
            "meta": p,
        })
    return result


__all__ = [
    "get_shopify_products",
    "get_product_details",
    "is_product_query",
    "format_product_response",
]
