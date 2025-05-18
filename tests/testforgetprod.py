import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from stores.shopify_async import get_product_details
import asyncio

async def test_product_search():
    queries = [
        "Do you have a red Dress in stock?",
        "Show me the Jax set",
        "Bloom Dress"
    ]
    for question in queries:
        print(f"\nTesting query: {question}")
        details = await get_product_details(question)
        print("get_product_details result:", details)

if __name__ == "__main__":
    asyncio.run(test_product_search())