import time
import httpx
import logging
from typing import List, Dict, Any, Optional, Tuple

# Caching constants and variables
PRODUCT_CACHE_TTL = 300  # Time-to-live for cache (seconds)
cached_products: List[Dict[str, Any]] = []
last_product_fetch_time: float = 0

# Shopify API configuration (should be loaded from config or env)
SHOPIFY_API_VERSION = "2023-01"        # e.g. latest API version
SHOPIFY_STORE_NAME = "your-store-name"  # your Shopify store name (subdomain)
SHOPIFY_PASSWORD = "your-access-token"  # Shopify Admin API access token

# Logger setup
logger = logging.getLogger(__name__)

async def fetch_shopify_products(page_info: Optional[str] = None, limit: int = 50) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Fetch a single page of products from Shopify using cursor-based pagination.
    Returns a tuple: (list_of_products, next_page_info)."""
    url = f"https://{SHOPIFY_STORE_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_PASSWORD,
        "Content-Type": "application/json"
    }
    params = {"limit": limit}
    if page_info:
        # When page_info is provided, use it for the next page request
        params["page_info"] = page_info
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
    except httpx.RequestError as e:
        logger.error(f"Network error while fetching Shopify products: {e}")
        return [], None
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error while fetching Shopify products: {e.response.status_code} - {e.response.text}")
        return [], None

    data = response.json()
    products = data.get("products", [])

    # Determine if there's a next page from the response's Link header
    next_page_info: Optional[str] = None
    link_header = response.headers.get("Link")
    if link_header:
        # The Link header may contain multiple links (e.g. rel="next" and rel="previous")
        for part in link_header.split(','):
            part = part.strip()
            if 'rel="next"' in part:
                # Extract the page_info value from the next-page URL
                # e.g. <https://STORE.myshopify.com/admin/api/VERSION/products.json?page_info=XYZ&limit=50>; rel="next"
                start_index = part.find("page_info=")
                if start_index != -1:
                    start_index += len("page_info=")
                    end_index = part.find('&', start_index)
                    if end_index == -1:
                        end_index = part.find('>', start_index)
                    if end_index != -1:
                        next_page_info = part[start_index:end_index]
                    else:
                        next_page_info = part[start_index:]
                break

    return products, next_page_info

async def get_shopify_products(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Retrieve all Shopify products, using in-memory caching and cursor-based pagination."""
    global cached_products, last_product_fetch_time
    current_time = time.time()

    # Return cached products if cache is fresh and no forced refresh
    if not force_refresh and cached_products and (current_time - last_product_fetch_time < PRODUCT_CACHE_TTL):
        logger.info("Returning cached Shopify products from memory.")
        return cached_products

    logger.info("Fetching all products from Shopify using cursor-based pagination...")
    all_products: List[Dict[str, Any]] = []
    next_page_info: Optional[str] = None

    # Loop through all pages by following the cursor (page_info) from each response
    while True:
        products_page, next_page_info = await fetch_shopify_products(page_info=next_page_info)
        if not products_page:
            # If no products are returned (empty list), we've reached the end or an error occurred
            break
        all_products.extend(products_page)
        if not next_page_info:
            # No 'next' page_info in the header, so this was the last page
            break

    # Update cache and timestamp
    cached_products = all_products
    last_product_fetch_time = current_time
    logger.info(f"Fetched {len(all_products)} products from Shopify.")
    return all_products
