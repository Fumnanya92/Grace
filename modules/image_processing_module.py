import asyncio
import cv2
import numpy as np
import aiofiles
import aiohttp
import tempfile
import logging
import os
from typing import List, Dict, Optional
from urllib.parse import urlparse
from aiobotocore.session import get_session
from modules.s3_service import S3Service
from logging_config import configure_logger
from aiohttp import BasicAuth

logger = configure_logger("image_processing_module")
logger.info("ImageProcessor initialized.")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

auth = BasicAuth(login=TWILIO_ACCOUNT_SID, password=TWILIO_AUTH_TOKEN)


class ImageProcessor:
    """Async image-matching engine for Grace."""

    def __init__(self, s3_service: S3Service):
        if not isinstance(s3_service, S3Service):
            raise ValueError("Valid S3Service instance required")

        self.s3_session = s3_service.session
        self.bucket = s3_service.bucket
        self.folder = s3_service.folder.rstrip("/") + "/"

        self.design_catalog: List[Dict] = []
        self.lock = asyncio.Lock()
        self.http_session: Optional[aiohttp.ClientSession] = None

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------
    async def initialize(self):
        """Initialize the HTTP session and load catalog features."""
        if not self.http_session:
            self.http_session = aiohttp.ClientSession()
        await self._load_catalog_features()

    async def close(self):
        """Gracefully close the HTTP and S3 sessions."""
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
        if self.s3_session:
            await self.s3_session.close()

    # ------------------------------------------------------------------
    # Catalog pre-loading
    # ------------------------------------------------------------------
    async def _load_catalog_features(self):
        """Pre-load design features dynamically."""
        try:
            async with self.s3_session.create_client("s3") as s3:
                paginator = s3.get_paginator("list_objects_v2")
                async for page in paginator.paginate(Bucket=self.bucket, Prefix=self.folder):
                    for obj in page.get("Contents", []):
                        key = obj["Key"]
                        if not key.lower().endswith((".jpg", ".jpeg", ".png")):
                            continue
                        design_id = key.split("/")[-1].rsplit(".", 1)[0]
                        design_name = design_id.replace("_", " ").title()
                        try:
                            body = await (await s3.get_object(Bucket=self.bucket, Key=key))["Body"].read()
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpeg") as tmp:
                                tmp.write(body)
                                tmp_path = tmp.name

                            features = await asyncio.to_thread(self._extract_features, tmp_path)
                            os.unlink(tmp_path)

                            if features is not None:
                                self.design_catalog.append(
                                    {
                                        "id": design_id,
                                        "name": design_name,
                                        "features": features,
                                        "norm": np.linalg.norm(features),
                                        "price": 15_000,
                                    }
                                )
                        except Exception as e:
                            logger.warning(f"Skipping {design_name}: {e}")
        except Exception as e:
            logger.error(f"Failed to load catalog features: {e}")

    # ------------------------------------------------------------------
    # Feature extraction & similarity
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_features(image_path: str) -> Optional[np.ndarray]:
        """Extract features from an image using OpenCV."""
        try:
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError("Invalid image file")
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
            cv2.normalize(hist, hist, alpha=1, beta=0, norm_type=cv2.NORM_L1)
            flat = hist.flatten().astype(np.float32)
            return flat if flat.size else None
        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            return None

    async def _find_matches(self, query: np.ndarray, top_n: int) -> List[Dict]:
        """Find the top N matches for the query features."""
        norm_q = np.linalg.norm(query)
        if norm_q == 0:
            return []
        async with self.lock:
            scored = []
            for d in self.design_catalog:
                if d["features"].shape != query.shape:
                    continue
                score = float(np.dot(query, d["features"]) / (norm_q * d["norm"] + 1e-8))
                scored.append({**d, "similarity": score})
        return sorted(scored, key=lambda x: x["similarity"], reverse=True)[:top_n]

    # ------------------------------------------------------------------
    # Image download helper
    # ------------------------------------------------------------------
    async def _download_image(self, url: str) -> bytes:
        """Download an image from a URL."""
        parsed = urlparse(url)
        # Private bucket: download via AWS signed request
        if parsed.netloc.startswith(f"{self.bucket}.s3") or parsed.netloc.endswith("amazonaws.com") and self.bucket in parsed.path:
            key = parsed.path.lstrip("/")
            async with self.s3_session.create_client("s3") as s3:
                obj = await s3.get_object(Bucket=self.bucket, Key=key)
                return await obj["Body"].read()
        # Twilio or public HTTP(S)
        async with self.http_session.get(url, auth=auth if "twilio.com" in parsed.netloc else None) as resp:
            if resp.status not in (200, 302):
                logger.error(f"Failed to download image: {resp.status} {await resp.text()}")
                raise ValueError(f"HTTP error {resp.status}")
            return await resp.read()

    # ------------------------------------------------------------------
    # Public processing pipeline
    # ------------------------------------------------------------------
    async def handle_image(self, sender: str, image_url: str) -> str:
        """Handle an incoming image, match it with the catalog, and return a response."""
        try:
            logger.info(f"Processing image from {sender}: {image_url}")
            if not await self._validate_media_url(image_url):
                return "The image URL is invalid or inaccessible. Please try again."

            try:
                img_bytes = await self._download_image(image_url)
            except Exception as e:
                logger.error(f"Download failed: {e}")
                return "The image URL is invalid or inaccessible. Please try again."

            # Write to temp for OpenCV
            tmp = await aiofiles.tempfile.NamedTemporaryFile(suffix=".jpeg")
            await tmp.write(img_bytes)
            await tmp.flush()
            query = await asyncio.to_thread(self._extract_features, tmp.name)
            await tmp.close()
            if query is None:
                return "Sorry, I couldn't process that image. Could you send a clearer one?"

            matches = await self._find_matches(query, top_n=3)
            if not matches:
                return (
                    "Sorry, I couldn't find any matching designs. "
                    "Please try again with a clearer image."
                )

            lines = ["Here are the closest matches to your design:"]
            for m in matches:
                presigned = await self._get_design_url(m["id"])
                lines.append(
                    f"{m['name']} (Price: ₦{m['price']}, Similarity: {m['similarity']:.2f}): {presigned}"
                )
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error handling image from {sender}: {e}", exc_info=True)
            return "Sorry, something went wrong while processing your image. Please try again later."

    async def load_external_catalog(self, products: list[dict]):
        """
        Load product features from an external product list (e.g., Shopify API).
        Each product dict must have: id, name, image_url, price, etc.
        """
        for product in products:
            if not product:
                logger.warning("Skipping product: product is None")
                continue
            image_url = product.get("image_url")
            if not image_url:
                logger.warning(f"Skipping {product.get('name', 'unknown')}: missing image_url")
                continue
            try:
                img_bytes = await self._download_image(image_url)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpeg") as tmp:
                    tmp.write(img_bytes)
                    tmp_path = tmp.name
                features = await asyncio.to_thread(self._extract_features, tmp_path)
                os.unlink(tmp_path)
                if features is not None:
                    self.design_catalog.append({
                        "id": product.get("id"),
                        "name": product.get("name"),
                        "features": features,
                        "norm": np.linalg.norm(features),
                        "price": product.get("price"),
                        "image_url": image_url,
                        "meta": product,  # Store all metadata for future use
                    })
            except Exception as e:
                logger.warning(f"Skipping {product.get('name', 'unknown')}: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _validate_media_url(self, url: str) -> bool:
        """Validate that the media URL is accessible."""
        if not self.http_session:
            raise RuntimeError("HTTP session is not initialized. Call `initialize()` before using this method.")

        parsed = urlparse(url)
        # Trust our own private bucket
        if parsed.netloc.startswith(f"{self.bucket}.s3") or (self.bucket in parsed.path and parsed.netloc.endswith("amazonaws.com")):
            return True
        try:
            async with self.http_session.head(url, auth=auth if "twilio.com" in parsed.netloc else None) as resp:
                return resp.status in (200, 302, 403)  # Allow 403 for private assets
        except Exception as e:
            logger.error(f"Failed to validate media URL {url}: {e}")
            return False

    async def _get_design_url(self, design_id: str) -> Optional[str]:
        """Generate a secure temporary URL for a design."""
        try:
            async with self.s3_session.create_client("s3") as s3:
                return await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket, "Key": f"{self.folder}{design_id}.jpeg"},
                    ExpiresIn=1800,
                )
        except Exception as e:
            logger.error(f"URL generation failed: {e}")
            return None