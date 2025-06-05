import asyncio
from asyncio import Semaphore
import cv2
import numpy as np
import aiohttp
import tempfile
import logging
import os
from typing import List, Dict, Optional, Union
from urllib.parse import urlparse
from modules.s3_service import S3Service
from logging_config import configure_logger
from aiohttp import BasicAuth
import faiss  # FAISS for fast nearest-neighbor searches

logger = configure_logger("image_processing_module")
logger.info("ImageProcessor initialized.")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
THUMBNAIL_SIZE = os.getenv("THUMBNAIL_SIZE", "200x200")  # Default to 200x200
CONCURRENT_TASKS = int(os.getenv("CONCURRENT_TASKS", 5))  # Default to 5 concurrent tasks

auth = BasicAuth(login=TWILIO_ACCOUNT_SID, password=TWILIO_AUTH_TOKEN)


class ImageProcessor:
    """Async image-matching engine for Grace."""

    def __init__(self, s3_service: S3Service):
        if not isinstance(s3_service, S3Service):
            raise ValueError("Valid S3Service instance required")

        # S3 and catalog attributes
        self.s3_session = s3_service.session
        self.bucket = s3_service.bucket
        self.folder = s3_service.folder.rstrip("/") + "/"
        self.design_catalog: List[Dict] = []

        # Async and HTTP session management
        self.lock = asyncio.Lock()
        self.http_session: Optional[aiohttp.ClientSession] = None

        # FAISS-related attributes
        self.faiss_index = None
        self._metadata_list = []

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------
    async def initialize(self):
        """Initialize the HTTP session and load catalog features."""
        if not self.http_session:
            self.http_session = aiohttp.ClientSession()

        # Try loading from cache first
        if not self._load_cached_features():
            # No cache found → load everything from S3
            await self._load_catalog_features()
            self._cache_features()

    async def close(self):
        """Gracefully close the HTTP session."""
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
            self.http_session = None
            logger.info("aiohttp ClientSession closed.")

    # ------------------------------------------------------------------
    # Catalog pre-loading
    # ------------------------------------------------------------------
    async def _load_catalog_features(self):
        """Pre-load design features dynamically from S3."""
        try:
            async with self.s3_session.create_client("s3") as s3:
                paginator = s3.get_paginator("list_objects_v2")
                async for page in paginator.paginate(Bucket=self.bucket, Prefix=self.folder):
                    tasks = []
                    for obj in page.get("Contents", []):
                        key = obj["Key"]
                        if not key.lower().endswith((".jpg", ".jpeg", ".png")):
                            continue
                        tasks.append(self._process_s3_object(s3, key))
                    # Run up to len(tasks) in parallel (one task per key)
                    await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Failed to load catalog features: {e}")

    async def _process_s3_object(self, s3, key: str):
        """Process a single S3 object and extract its features."""
        design_id = key.split("/")[-1].rsplit(".", 1)[0]
        design_name = design_id.replace("_", " ").title()
        logger.info(f"[S3] Processing: {design_name}")

        try:
            body = await (await s3.get_object(Bucket=self.bucket, Key=key))["Body"].read()
            features = await self._extract_features_from_bytes(body)
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

    # ------------------------------------------------------------------
    # Feature extraction
    # ------------------------------------------------------------------
    async def _extract_features_from_bytes(self, img_bytes: bytes) -> Optional[np.ndarray]:
        """Extract features from image bytes."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpeg") as tmp:
            tmp.write(img_bytes)
            tmp_path = tmp.name

        try:
            return await asyncio.to_thread(self._extract_features, tmp_path)
        finally:
            os.unlink(tmp_path)

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
            return hist.flatten().astype(np.float32)
        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            return None

    # ------------------------------------------------------------------
    # FAISS index management
    # ------------------------------------------------------------------
    def _build_faiss_index(self):
        """Build a FAISS index over all feature vectors in the catalog."""
        if not self.design_catalog:
            logger.warning("No designs to index. FAISS index not built.")
            self.faiss_index = None
            return

        feats = np.stack([d["features"] for d in self.design_catalog], axis=0).astype(np.float32)
        faiss.normalize_L2(feats)

        d = feats.shape[1]
        index = faiss.IndexFlatIP(d)
        index.add(feats)

        self.faiss_index = index
        self._metadata_list = self.design_catalog.copy()
        logger.info(f"FAISS index built with {len(self.design_catalog)} entries.")

    # ------------------------------------------------------------------
    # Public processing pipeline
    # ------------------------------------------------------------------
    async def handle_image(self, sender: str, image_urls: Union[str, List[str]]) -> str:
        """Handle one or more incoming images, match them with the catalog, and return a response."""
        if isinstance(image_urls, str):
            image_urls = [image_urls]

        async def process_one_image(image_url):
            try:
                logger.info(f"Processing image from {sender}: {image_url}")
                if not await self._validate_media_url(image_url):
                    return f"The image URL {image_url} is invalid or inaccessible. Please try again."

                img_bytes = await self._download_image(image_url)
                query = await self._extract_features_from_bytes(img_bytes)

                if query is None:
                    return f"Sorry, I couldn't process the image {image_url}. Could you send a clearer one?"

                q = query.astype(np.float32).reshape(1, -1)
                faiss.normalize_L2(q)

                if self.faiss_index is None:
                    return "Sorry, the catalog isn't ready yet. Please try again shortly."

                k = 3
                distances, indices = self.faiss_index.search(q, k)

                matches = []
                for sim, idx in zip(distances[0], indices[0]):
                    if idx < 0 or idx >= len(self._metadata_list):
                        continue
                    entry = self._metadata_list[idx]
                    matches.append(
                        {
                            "id": entry["id"],
                            "name": entry["name"],
                            "price": entry["price"],
                            "similarity": float(sim),
                            "image_url": entry.get("image_url"),  # Use Shopify image URL
                        }
                    )

                if not matches:
                    return f"Sorry, I couldn't find any matching designs for {image_url}."

                lines = ["Here are the closest matches to your design:"]
                for m in matches:
                    shopify_url = m["image_url"]
                    lines.append(
                        f"{m['name']} (Price: ₦{m['price']}, Similarity: {m['similarity']:.2f}): {shopify_url}"
                    )
                return "\n".join(lines)
            except Exception as e:
                logger.error(f"Error handling image {image_url} from {sender}: {e}", exc_info=True)
                return f"Sorry, something went wrong while processing {image_url}. Please try again later."

        tasks = [process_one_image(url) for url in image_urls]
        results = await asyncio.gather(*tasks)
        return "\n\n".join(results)

    async def load_external_catalog(self, products: list[dict]):
        """Load product features from an external product list (e.g., Shopify API)."""
        sem = Semaphore(CONCURRENT_TASKS)  # Limit concurrency
        total = len(products)

        async def process_one(idx, product):
            name = product.get("name", "<unknown>")
            image_url = self._to_thumbnail_url(product.get("image_url"))
            if not await self._validate_thumbnail(image_url):
                image_url = product.get("image_url")
            if not image_url:
                logger.warning(f"Skipping {name}: missing image_url")
                return

            async with sem:
                logger.info(f"[Shopify] Processing {idx}/{total}: {name}")
                try:
                    img_bytes = await self._download_image(image_url)
                    features = await self._extract_features_from_bytes(img_bytes)
                    if features is not None:
                        self.design_catalog.append(
                            {
                                "id": product["id"],
                                "name": name,
                                "features": features,
                                "norm": np.linalg.norm(features),
                                "price": product.get("price"),
                                "image_url": image_url,  # Save Shopify image URL
                                "meta": product,
                            }
                        )
                except Exception as e:
                    logger.warning(f"Skipping {name}: {e}")

        tasks = [process_one(i + 1, product) for i, product in enumerate(products)]
        await asyncio.gather(*tasks)
        self._build_faiss_index()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _validate_media_url(self, url: str) -> bool:
        """Validate that the media URL is accessible."""
        if not self.http_session:
            raise RuntimeError("HTTP session is not initialized. Call `initialize()` before using this method.")

        parsed = urlparse(url)
        # Trust our own private bucket
        if parsed.netloc.startswith(f"{self.bucket}.s3") or (
            self.bucket in parsed.path and parsed.netloc.endswith("amazonaws.com")
        ):
            return True

        try:
            async with self.http_session.head(
                url, auth=auth if "twilio.com" in parsed.netloc else None
            ) as resp:
                return resp.status in (200, 302, 403)  # Allow 403 for private assets
        except Exception as e:
            logger.error(f"Failed to validate media URL {url}: {e}")
            return False

    async def _validate_thumbnail(self, url: str) -> bool:
        """Check if a thumbnail exists for the given URL."""
        if not url:
            return False
        try:
            async with self.http_session.head(url) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"Thumbnail validation failed for {url}: {e}")
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

    async def _download_image(self, url: str) -> bytes:
        """Download an image from a URL."""
        parsed = urlparse(url)
        # If it’s our S3 bucket, fetch from S3 directly
        if parsed.netloc.startswith(f"{self.bucket}.s3") or (
            self.bucket in parsed.path and parsed.netloc.endswith("amazonaws.com")
        ):
            key = parsed.path.lstrip("/")
            async with self.s3_session.create_client("s3") as s3:
                obj = await s3.get_object(Bucket=self.bucket, Key=key)
                return await obj["Body"].read()

        # Otherwise, download over HTTP(S)
        async with self.http_session.get(
            url, auth=auth if "twilio.com" in parsed.netloc else None
        ) as resp:
            if resp.status not in (200, 302):
                logger.error(f"Failed to download image: {resp.status} {await resp.text()}")
                raise ValueError(f"HTTP error {resp.status}")
            return await resp.read()

    def _cache_features(self):
        """Save feature vectors and metadata to disk."""
        np.save("features.npy", np.stack([d["features"] for d in self.design_catalog]))
        np.save("metadata.npy", np.array(self.design_catalog, dtype=object))

    def _load_cached_features(self):
        """Load feature vectors and metadata from disk."""
        if os.path.exists("features.npy") and os.path.exists("metadata.npy"):
            features = np.load("features.npy")
            metadata = np.load("metadata.npy", allow_pickle=True)
            self.design_catalog = metadata.tolist()
            self._build_faiss_index()
            return True
        return False

    def _to_thumbnail_url(self, shopify_url: str, size: str = THUMBNAIL_SIZE) -> str:
        """Convert a Shopify image URL to use a smaller thumbnail size."""
        if not shopify_url:
            return shopify_url
        parts = shopify_url.split("?")
        base, params = parts[0], ("?" + parts[1] if len(parts) > 1 else "")
        lower = base.lower()
        if lower.endswith(".jpg"):
            return base[:-4] + f"_{size}.jpg" + params
        if lower.endswith(".jpeg"):
            return base[:-5] + f"_{size}.jpeg" + params
        if lower.endswith(".png"):
            return base[:-4] + f"_{size}.png" + params
        return shopify_url
