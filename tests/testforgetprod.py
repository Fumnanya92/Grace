import os
import sys

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from stores.shopify_async import get_product_details
import asyncio

async def test_get_product_details():
    question = "Do you have a red Dress in stock?"
    result = await get_product_details(question)
    print(result)

asyncio.run(test_get_product_details())