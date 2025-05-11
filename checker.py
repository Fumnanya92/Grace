import asyncio
from stores.shopify import get_shopify_products, check_shopify_api_version

async def test_connection():
    await check_shopify_api_version()  # Check API version
    products = await get_shopify_products(force_refresh=True)
    print(f"\n✅ Total products fetched: {len(products)}")
    if products:
        print("🛍️ First product:", products[0].get("title"))

asyncio.run(test_connection())
