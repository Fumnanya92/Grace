import asyncio
from stores.shopify_async import get_products_for_image_matching
from modules.image_processing_module import ImageProcessor
from modules.s3_service import S3Service

async def main():
    # 1) Initialize S3Service & ImageProcessor
    s3 = S3Service()
    ip = ImageProcessor(s3)
    await ip.initialize()
    print(f"[TEST] Loaded {len(ip.design_catalog)} designs from S3.")

    try:
        # 2) Fetch all Shopify products
        all_shopify = await get_products_for_image_matching()
        subset = all_shopify  # Load the entire catalog
        print(f"[TEST] Retrieved {len(all_shopify)} products from Shopify.")

        # 3) Load all products into the catalog (you'll see progress printed)
        await ip.load_external_catalog(subset)
        print(f"[TEST] Combined catalog size is now {len(ip.design_catalog)} total entries.")

        # 4) Pick the first sample with a valid image_url
        sample = next((p for p in subset if p.get("image_url")), None)
        if not sample:
            print("[TEST] No Shopify image URL found to test with.")
            return

        print(f"[TEST] Using sample product '{sample['name']}' with image_url:\n       {sample['image_url']}")

        # 5) Run handle_image on that sample image
        reply = await ip.handle_image("unit-test", sample["image_url"])
        print("\n[TEST] handle_image reply:\n" + "-" * 40)
        print(reply)
        print("-" * 40)

        # 6) Sanity check
        if sample["name"].lower() in reply.lower():
            print("[TEST] SUCCESS: sample product name found in reply.")
        else:
            print("[TEST] FAILURE: sample product name NOT found in reply.")
    finally:
        await ip.close()
        print("[TEST] ImageProcessor closed successfully.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[TEST] Script interrupted. Exiting gracefully.")
