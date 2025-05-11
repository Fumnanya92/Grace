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
from typing import Dict, List, Optional

from logging_config import configure_logger
from modules.utils import (
    get_canned_response,
    update_speech_library,
    INTENT_PHRASES,
)

logger = configure_logger("grace_brain")

# ---------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------
CONFIG_DIR = Path("config")
FALLBACKS_FILE = CONFIG_DIR / "fallback_responses.json"


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


class GraceBrain:
    def __init__(self) -> None:
        self.config = _load_json(CONFIG_DIR / "config.json", default={})
        self.tone = _load_json(CONFIG_DIR / "tone.json", default={"style": "friendly"})
        self.catalog: List[Dict] = _load_json(CONFIG_DIR / "catalog.json", default=[])
        self.fallbacks = _load_json(FALLBACKS_FILE, default={"default_response": "I'm still learning 😊"})

    # -----------------------------------------------------------------
    # ==== Canned Responses ===========================================
    # -----------------------------------------------------------------
    def get_response(self, intent: str, **kwargs) -> str:
        """Return a canned response formatted with kwargs, fallback to backup JSON."""
        if resp := get_canned_response(intent):
            return resp.format(**kwargs)

        logger.warning("No response found for intent '%s'", intent)
        return self.fallbacks.get(intent, self.fallbacks.get("default_response", "[no_reply]"))

    # -----------------------------------------------------------------
    # ==== Config Accessors ===========================================
    # -----------------------------------------------------------------
    def get_catalog(self) -> List[Dict]:
        return self.catalog

    def get_config_value(self, key: str, default=None):
        return self.config.get(key, default)

    def get_business_hours(self) -> Dict[str, str]:
        return self.config.get("business_hours", {"start": "09:00", "end": "17:00"})

    def get_payment_details(self) -> Dict[str, str]:
        return self.config.get("payment_details", {})

    def is_catalog_enabled(self) -> bool:
        return self.config.get("catalog_enabled", bool(self.catalog))

    def get_business_info(self) -> Dict:
        return {
            "name": self.config.get("business_name"),
            "type": self.config.get("business_type"),
            "instagram": self.config.get("instagram"),
            "shop_link": self.config.get("shop_link"),
            "currency": self.config.get("currency", "₦"),
            "delivery_time_days": self.config.get("delivery_time_days", 3),
        }

    # -----------------------------------------------------------------
    # ==== Intent Helpers =============================================
    # -----------------------------------------------------------------
    def intent_keys(self) -> List[str]:
        """Return every known intent for tagging in prompts."""
        return sorted(set(INTENT_PHRASES) | set(self.fallbacks))

    def extract_response_key(self, text: str) -> str:
        """Extract [[intent_key]] tag from GPT reply."""
        if match := re.search(r"\[\[(.*?)]]", text):
            return match.group(1).strip()
        return "default_response"

    # -----------------------------------------------------------------
    # ==== GPT Prompt Builder =========================================
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

        # Handle catalog preview
        if isinstance(self.catalog, list) and self.catalog:
            catalog_intro = "\n".join(
                f"- {item.get('name', 'Unnamed')}: {self.get_business_info()['currency']}{item.get('price', 'N/A')}"
                for item in self.catalog[:5]
            )
        else:
            logger.warning("Catalog is missing or invalid.")
            catalog_intro = "Our product list is currently empty."

        keys = ", ".join(f"[[{k}]]" for k in self.intent_keys())

        return (
            f"{persona}\n"
            f"Recent conversation:\n{chat_history}\n\n"
            f"User: {user_message}\n\n"
            f"Product highlights:\n{catalog_intro}\n\n"
            "Respond conversationally, nudge toward purchase where appropriate, "
            f"and tag your reply with exactly one of the following keys: {keys}\n"
        )

    # -----------------------------------------------------------------
    # ==== AI Learning at Runtime =====================================
    # -----------------------------------------------------------------
    async def update_library(self, intent: str, user_phrase: str, ai_response: str) -> None:
        """Persist new Q&A pair to speech_library and refresh cache."""
        try:
            update_speech_library(intent, user_phrase, ai_response, confidence=0.5)
        except Exception as exc:
            logger.error("Failed to update speech library: %s", exc)
