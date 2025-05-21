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
        # --- Simple assertion: result should mention the product or not be empty ---
        assert details and ("Dress" in details or "set" in details or "couldn't find" in details.lower())

# --- New test: check that image URL is included in product details ---
async def test_product_image_in_details():
    question = "Bloom Dress"
    details = await get_product_details(question)
    print("\nTesting image URL in details for:", question)
    print("get_product_details result:", details)
    # Check for a likely image URL in the result
    import re
    match = re.search(r'https?://\S+\.(jpg|jpeg|png|gif)', details)
    assert match, "No image URL found in product details!"

if __name__ == "__main__":
    asyncio.run(test_product_search())
    asyncio.run(test_product_image_in_details())