# modules/grace_brain.py

"""
GraceBrain
----------
Central knowledge helper for Grace.

Responsibilities:
* Serve canned responses from speech_library (training_data format)
* Provide business/config/tone helpers
* Build GPT fallback prompts
* Append new Q&A pairs to speech_library.json at runtime
"""

from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from logging_config import configure_logger
from modules.utils import (
    get_canned_response,
    update_speech_library,
    INTENT_PHRASES,
)
from stores.shopify_async import get_shopify_products

logger = configure_logger("grace_brain")

# ---------------------------------------------------------------------
# Constants and File Paths
# ---------------------------------------------------------------------
CONFIG_DIR = Path("config")
FALLBACKS_FILE = CONFIG_DIR / "fallback_responses.json"


# ---------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------
def _load_json(path: Path, default: Optional[dict] = None) -> dict:
    """Read JSON file or return *default* if missing/error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("%s not found. Using default.", path.name)
        return default or {}
    except Exception as exc:
        logger.error("Failed to load %s: %s", path.name, exc)
        return default or {}


async def fetch_catalog() -> List[Dict[str, Any]]:
    """Fetch the product catalog dynamically from Shopify."""
    return await get_shopify_products()


# ---------------------------------------------------------------------
# GraceBrain Class
# ---------------------------------------------------------------------
class GraceBrain:
    def __init__(self) -> None:
        self.config = _load_json(CONFIG_DIR / "config.json", default={})
        self.tone = _load_json(CONFIG_DIR / "tone.json", default={"style": "friendly"})
        self.fallbacks = _load_json(FALLBACKS_FILE, default={"default_response": "I'm still learning 😊"})

    # -----------------------------------------------------------------
    # Canned Responses
    # -----------------------------------------------------------------
    def get_response(self, intent: str, **kwargs) -> str:
        """Return a canned response formatted with kwargs, fallback to backup JSON."""
        if resp := get_canned_response(intent):
            return resp.format(**kwargs)

        logger.warning("No response found for intent '%s'", intent)
        return self.fallbacks.get(intent, self.fallbacks.get("default_response", "[no_reply]"))

    # -----------------------------------------------------------------
    # Config Accessors
    # -----------------------------------------------------------------
    def get_config_value(self, key: str, default=None):
        """Retrieve a value from the config."""
        return self.config.get(key, default)

    def get_business_info(self) -> Dict:
        """Return business information from the config."""
        return {
            "name": self.config.get("business_name"),
            "type": self.config.get("business_type"),
            "instagram": self.config.get("instagram"),
            "shop_link": self.config.get("shop_link"),
            "currency": self.config.get("currency", "₦"),
            "delivery_time_days": self.config.get("delivery_time_days", 3),
        }

    # -----------------------------------------------------------------
    # Catalog Handling
    # -----------------------------------------------------------------
    async def get_catalog(self) -> List[Dict[str, Any]]:
        """
        Fetch the product catalog dynamically from Shopify.
        Returns a list of products.
        """
        try:
            catalog = await fetch_catalog()
            if not catalog:
                logger.warning("Catalog fetch returned an empty list.")
                return []
            return catalog
        except Exception as exc:
            logger.error("Failed to fetch catalog: %s", exc)
            return []

    def is_catalog_enabled(self) -> bool:
        """Check if the catalog is enabled."""
        return True  # Always enabled since we're fetching dynamically

    # -----------------------------------------------------------------
    # Intent Helpers
    # -----------------------------------------------------------------
    def intent_keys(self) -> List[str]:
        """Return every known intent for tagging in prompts."""
        tool_tags = {
            "shopify_product_lookup",
            "shopify_create_order",
            "shopify_track_order",
        }
        return sorted(set(INTENT_PHRASES) | set(self.fallbacks) | tool_tags)

    def extract_response_key(self, text: str) -> str:
        """Extract [[intent_key]] tag from GPT reply."""
        if match := re.search(r"\[\[(.*?)]]", text):
            return match.group(1).strip()
        return "default_response"

    # -----------------------------------------------------------------
    # GPT Prompt Builder
    # -----------------------------------------------------------------
    async def build_prompt(self, chat_history: str, user_message: str) -> str:
        """
        Build a rich GPT prompt:
        - persona/tone
        - chat history
        - product teasers
        - allowed intent tags
        """
        persona = self.tone.get(
            "fallback_persona",
            "You are Grace, a warm and helpful sales assistant for a small business.",
        )

        # Fetch catalog dynamically
        catalog = await self.get_catalog()
        catalog_intro = self._build_catalog_intro(catalog)

        keys = ", ".join(f"[[{k}]]" for k in self.intent_keys())

        return (
            f"{persona}\n"
            f"Recent conversation:\n{chat_history}\n\n"
            f"User: {user_message}\n\n"
            f"Product highlights:\n{catalog_intro}\n\n"
            "Respond conversationally, nudge toward purchase where appropriate, "
            f"and tag your reply with exactly one of the following keys: {keys}\n"
            "▪ [[shopify_product_lookup]] → call the product lookup tool\n"
            "▪ [[shopify_create_order]]  → create a draft‑order & return payment link\n"
            "▪ [[shopify_track_order]]   → check fulfilment status\n"
        )

    def _build_catalog_intro(self, catalog: List[Dict[str, Any]]) -> str:
        """Build a catalog preview for the prompt."""
        if catalog:
            return "\n".join(
                f"- {item.get('name', 'Unnamed')}: {self.get_business_info().get('currency', '₦')}{item.get('price', 'N/A')}"
                for item in catalog[:5]
            )
        logger.warning("Catalog is missing or invalid.")
        return "Our product list is currently empty."

    # -----------------------------------------------------------------
    # AI Learning at Runtime
    # -----------------------------------------------------------------
    async def update_library(self, intent: str, user_phrase: str, ai_response: str) -> None:
        """Persist new Q&A pair to speech_library and refresh cache."""
        try:
            update_speech_library(intent, user_phrase, ai_response, confidence=0.5)
        except Exception as exc:
            logger.error("Failed to update speech library: %s", exc)
