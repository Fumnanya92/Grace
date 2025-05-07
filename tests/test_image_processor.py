import unittest
import asyncio
import os
from modules.image_processing_module import ImageProcessor
from modules.s3_service import S3Service
from dotenv import load_dotenv
import cv2
import numpy as np


class TestImageProcessorWithS3(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        """Set up the S3 service and processor."""
        load_dotenv()
        bucket = os.getenv("S3_BUCKET_NAME")
        folder = os.getenv("S3_WHOLESALE_PIC")

        if not bucket or not folder:
            raise ValueError("S3_BUCKET_NAME and S3_WHOLESALE_PIC must be set in the environment variables.")

        cls.s3_service = S3Service()
        cls.s3_service.bucket = bucket
        cls.s3_service.folder = folder

        cls.processor = ImageProcessor(cls.s3_service)

    async def asyncSetUp(self):
        """Initialize the processor."""
        await self.processor.initialize()

    async def asyncTearDown(self):
        """Clean up resources."""
        await self.processor.close()

    async def test_load_catalog_features(self):
        """Test loading catalog features from the real S3 bucket."""
        self.assertGreater(len(self.processor.design_catalog), 0, "Catalog should not be empty.")
        for design in self.processor.design_catalog:
            self.assertIn("id", design)
            self.assertIn("features", design)
            self.assertIn("norm", design)
            self.assertGreater(design["norm"], 0)

    async def test_handle_image_dynamic_matching(self):
        """Test handle_image dynamically with images from the S3 bucket."""
        self.assertGreater(len(self.processor.design_catalog), 0, "Catalog should not be empty.")

        # Dynamically pick an image from the catalog
        test_image = self.processor.design_catalog[0]  # Pick the first image in the catalog
        test_image_id = test_image["id"]
        test_image_url = await self.processor._presign(test_image_id)

        # Process the image
        response = await self.processor.handle_image("sender", test_image_url)

        # Validate the response
        print(response)
        self.assertIn("Here are the closest matches to your design:", response)
        self.assertIn(test_image["name"], response)

    async def test_handle_image_no_matches(self):
        """Test handle_image with an image that has no matches in the catalog."""
        # Create a noise image entirely in memory
        noise = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        _, noise_image = cv2.imencode(".jpg", noise)

        # Extract features from the noise image
        query_features = await asyncio.to_thread(self.processor._extract_features, noise_image)

        # Ensure the noise image does not match any catalog image
        matches = await self.processor._find_matches(query_features, top_n=3)
        self.assertEqual(len(matches), 0, "Noise image should not match any catalog image.")

    async def test_exact_match_dynamic(self):
        """Test handle_image with an image that exactly matches a catalog entry."""
        self.assertGreater(len(self.processor.design_catalog), 0, "Catalog should not be empty.")

        # Dynamically pick an image from the catalog
        test_image = self.processor.design_catalog[0]  # Pick the first image in the catalog
        test_image_id = test_image["id"]
        test_image_url = await self.processor._presign(test_image_id)

        # Process the image
        response = await self.processor.handle_image("sender", test_image_url)

        # Validate the response
        print(response)
        self.assertIn("Here are the closest matches to your design:", response)
        self.assertRegex(response, r"Similarity:\s+0\.9[0-9]")  # ≥ 0.90 is good enough

    async def test_match_screenshot_with_catalog(self):
        """Test matching a screenshot with images in the S3 catalog."""
        self.assertGreater(len(self.processor.design_catalog), 0, "Catalog should not be empty.")

        # Simulate a customer-provided screenshot URL
        screenshot_url = "https://salescabal.s3.eu-west-3.amazonaws.com/stores/187378/products/221f7e6aecba07ad3e6c605056bc7c02e5cce3e4.jpeg"

        # Process the screenshot
        response = await self.processor.handle_image("customer", screenshot_url)

        # Validate the response
        print(response)
        self.assertIn("Here are the closest matches to your design:", response)

        # Ensure at least one match is returned
        matches = response.split("\n")[1:]  # Skip the first line (header)
        self.assertGreater(len(matches), 0, "No matches were found for the screenshot.")

        # Validate that the matched image names are in the catalog
        matched_names = [line.split(" (")[0] for line in matches]
        catalog_names = [design["name"] for design in self.processor.design_catalog]
        for name in matched_names:
            self.assertIn(name, catalog_names, f"Matched name '{name}' not found in catalog.")


if __name__ == "__main__":
    unittest.main()