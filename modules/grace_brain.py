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
import random
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

from logging_config import configure_logger
logger = configure_logger("grace_brain")

from modules.utils import (
    get_canned_response,
    update_speech_library,
    INTENT_PHRASES,
)
from stores.shopify_async import get_products_for_image_matching

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
    """Fetch the product catalog dynamically from Shopify, adapted for prompts."""
    return await get_products_for_image_matching()

def resolve_reference(user_message: str, chat_history: list) -> str:
    """
    Replace ambiguous references like 'it', 'this', 'that' in user_message
    with the last mentioned product/service/item in chat_history.
    """
    if re.search(r"\b(it|this|that)\b", user_message, re.I):
        for turn in reversed(chat_history):
            # Look for product/service/item/plan/course/package in user or bot messages
            match = re.search(
                r"\b([A-Za-z0-9 \-]+(dress|set|shirt|service|product|item|plan|course|package))\b",
                turn.get('user_message', ''), re.I)
            if match:
                return re.sub(r"\b(it|this|that)\b", match.group(0), user_message, flags=re.I)
            match = re.search(
                r"\b([A-Za-z0-9 \-]+(dress|set|shirt|service|product|item|plan|course|package))\b",
                turn.get('bot_reply', ''), re.I)
            if match:
                return re.sub(r"\b(it|this|that)\b", match.group(0), user_message, flags=re.I)
    return user_message

# ---------------------------------------------------------------------
# GraceBrain Class
# ---------------------------------------------------------------------
class GraceBrain:
    def __init__(self) -> None:
        self.config = _load_json(CONFIG_DIR / "config.json", default={})
        self.tone = _load_json(CONFIG_DIR / "tone.json", default={"style": "friendly"})
        self.fallbacks = _load_json(FALLBACKS_FILE, default={"default_response": "I'm still learning 😊"})
        # Load system prompt once at startup
        prompt_versions = [
            "config/system_prompt.txt",
            "config/system_prompt_v2.txt"
        ]
        chosen_prompt = random.choice(prompt_versions)
        with open(chosen_prompt, "r", encoding="utf-8") as f:
            self.system_prompt = f.read()
        logger.info(f"Using prompt: {chosen_prompt}")
        # Load policies at startup
        self.policies_content = self._load_policies()
        self.prompt_version = chosen_prompt

    # -----------------------------------------------------------------
    # Canned Responses
    # -----------------------------------------------------------------
    def get_response(self, intent: str, **kwargs) -> str:
        """Return a canned response formatted with kwargs, fallback to backup JSON."""
        resp = get_canned_response(intent)
        if resp:
            return resp.format(**kwargs)
        logger.warning("No response found for intent '%s'", intent)
        return self.fallbacks.get(intent, self.fallbacks.get("default_response", "[no_reply]"))

    # -----------------------------------------------------------------
    # Config Accessors
    # -----------------------------------------------------------------
    def get_config_value(self, key: str, default=None):
        """Retrieve a value from the config."""
        return self.config.get(key, default)

    def get_full_config(self) -> dict:
        """Return the entire config.json as a dict."""
        return self.config

    def get_business_info(self) -> Dict:
        """Return business information from the config."""
        return self.config

    def reload_config(self):
        """Reload config.json at runtime if needed."""
        self.config = _load_json(CONFIG_DIR / "config.json", default={})

    def _build_business_info(self) -> str:
        """Dynamically build business info string from config.json."""
        exclude = {"intent_keys", "catalog_enabled", "catalog", "fallbacks", "tone"}  # Add any keys you want to skip
        lines = []
        for key, value in self.config.items():
            if key in exclude:
                continue
            if isinstance(value, dict):
                for subkey, subval in value.items():
                    lines.append(f"{key.replace('_', ' ').title()} {subkey.title()}: {subval}")
            elif isinstance(value, list):
                continue  # Skip lists for brevity, or format as needed
            else:
                lines.append(f"{key.replace('_', ' ').title()}: {value}")
        return "\n".join(lines)

    # -----------------------------------------------------------------
    # Catalog Handling
    # -----------------------------------------------------------------
    async def get_catalog(self) -> List[Dict[str, Any]]:
        """Fetch the product catalog dynamically from Shopify."""
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
        return sorted(set(INTENT_PHRASES) | set(self.fallbacks))

    def extract_response_key(self, text: str) -> str:
        """Extract [[intent_key]] tag from GPT reply."""
        match = re.search(r"\[\[(.*?)]]", text)
        if match:
            return match.group(1).strip()
        return "default_response"

    # -----------------------------------------------------------------
    # GPT Prompt Builder
    # -----------------------------------------------------------------
    async def build_prompt(self, chat_history: str, user_message: str) -> str:
        catalog = await self.get_catalog()
        # Use config for catalog keywords, fallback to generic ones
        catalog_keywords = self.config.get("catalog_keywords", ["show", "price", "catalog", "product", "service", "item"])
        show_catalog = any(k in user_message.lower() for k in catalog_keywords)
        catalog_intro = self._build_catalog_intro(catalog) if show_catalog else ""
        keys = ", ".join(f"[[{k}]]" for k in self.intent_keys())
        business_info = self._build_business_info()
        business_name = self.config.get("business_name", "Our Company")
        prompt_template = self.system_prompt
        system_prompt = prompt_template.format(
            BUSINESS_NAME=business_name,
            POLICIES_CONTENT=self.policies_content,
        )

        prompt_parts = [
            f"{system_prompt}\n",
            f"{business_info}\n\n",
            "Instructions:\n"
            "- Do not repeat greetings if you have already greeted the user in this conversation.\n"
            "- If the user asks about Instagram, payment, or business hours, always answer with the exact info from above.\n"
            "- If the user asks for a product or service, suggest from the catalog if possible before using your own words.\n"
            f"Recent conversation:\n{chat_history}\n\n",
            f"User: {user_message}\n\n"
        ]

        if catalog_intro:
            prompt_parts.append(f"Product highlights:\n{catalog_intro}\n\n")

        prompt_parts.append(
            "Respond conversationally, nudge toward purchase, "
            "**keep replies under 40 words unless sending item details**, "
            f"and tag your reply with exactly one of the following keys: {keys}\n"
        )

        return "".join(prompt_parts)

    def _build_catalog_intro(self, catalog: List[Dict[str, Any]]) -> str:
        """Build a catalog preview for the prompt."""
        if catalog:
            logger.info("Sample catalog item for highlights: %s", catalog[0])
            currency = self.config.get("currency", "₦")
            return "\n".join(
                f"- {item.get('name', 'Unnamed')}: {currency}{item.get('price', 'N/A')}"
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

    # -----------------------------------------------------------------
    # Policies
    # -----------------------------------------------------------------
    def _load_policies(self) -> str:
        """Load company policies from config/policies.txt."""
        policies_path = Path("config/policies.txt")
        if policies_path.exists():
            try:
                with open(policies_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as exc:
                logger.error("Failed to load policies.txt: %s", exc)
                return ""
        else:
            logger.warning("policies.txt not found in config directory.")
            return ""

    def reload_policies(self):
        """Reload policies at runtime if needed."""
        self.policies_content = self._load_policies()

    def get_system_prompt(self) -> str:
        """Return the system prompt with the current company policies included."""
        return (
            f"{self.system_prompt}\n"
            f"**Current Company Policies:**\n"
            f"{self.policies_content}\n"
        )
