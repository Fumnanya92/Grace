# grace_brain.py
import json
import os
import re
from typing import Optional, Dict, List
from logging_config import configure_logger

logger = configure_logger("grace_brain")

CONFIG_DIR = "config"
DEFAULT_FALLBACKS = "fallback_responses.json"

class GraceBrain:
    def __init__(self):
        # Centralized configuration files
        self.config = self._load_file("config.json", default={})
        self.speech_library = self._load_file("speech_library.json", default={"intents": {}, "responses": {}})
        self.tone_config = self._load_file("tone.json", default={"style": "friendly", "persona": "grace"})
        self.catalog = self._load_file("catalog.json", default=[])
        self.fallbacks = self._load_file(DEFAULT_FALLBACKS, default={})

    def _load_file(self, filename: str, default: Optional[dict] = None) -> dict:
        """Safely load a JSON file with a fallback default."""
        path = os.path.join(CONFIG_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"{filename} not found. Using default.")
            return default or {}
        except Exception as e:
            logger.error(f"Failed to load {filename}: {e}")
            return default or {}

    def get_response(self, key: str, **kwargs) -> str:
        """Fetch a dynamic response using the speech library or fallback."""
        responses = self.speech_library.get("responses", {}).get(key, [])
        if responses:
            response = responses[0].get("response", "")
            return response.format(**kwargs)

        logger.warning(f"No response found for key '{key}' in speech_library.")
        return self.fallbacks.get(key, f"[{key}] I'm still learning how to respond to this.")

    def get_catalog(self) -> List[Dict[str, str]]:
        """Return the current product catalog."""
        return self.catalog

    def get_config_value(self, key: str, default=None):
        return self.config.get(key, default)

    def get_business_hours(self) -> Dict[str, str]:
        return self.config.get("business_hours", {"start": "09:00", "end": "17:00"})

    def get_payment_details(self) -> Dict[str, str]:
        return self.config.get("payment_details", {})

    def get_intent_keys(self) -> List[str]:
        return self.config.get("intent_keys", [])

    def is_catalog_enabled(self) -> bool:
        return self.config.get("catalog_enabled", False)

    def get_business_info(self) -> Dict:
        """Return general business info used across messages or prompts."""
        return {
            "name": self.config.get("business_name"),
            "type": self.config.get("business_type"),
            "instagram": self.config.get("instagram"),
            "shop_link": self.config.get("shop_link"),
            "currency": self.config.get("currency"),
            "delivery_time_days": self.config.get("delivery_time_days"),
        }

    def load_tone(self) -> dict:
        """Load tone configuration."""
        return self.tone_config

    async def build_prompt(self, formatted_history: str, user_message: str) -> str:
        """Build a prompt for AI-based responses."""
        tone = self.load_tone()
        persona = tone.get("fallback_persona", "You are Grace, a helpful assistant.")
        greeting = tone.get("greeting_prefix", "Hello 👋")

        catalog_intro = "\n".join(
            [f"- {item['name']}: ₦{item.get('price', 'N/A')}" for item in self.catalog[:5]]
        ) if self.catalog else "No products available at the moment."
        intent_keys = self.get_intent_keys()

        return (
            f"{persona}\n"
            f"Recent conversation:\n{formatted_history}\n\n"
            f"User: {user_message}\n\n"
            f"Product Highlights:\n{catalog_intro}\n"
            "Respond conversationally and helpfully, with a warm tone.\n"
            "Only use one of the following keys to tag your message: "
            + ", ".join([f"[[{k}]]" for k in intent_keys]) + ".\n"
        )

    def extract_response_key(self, text: str) -> str:
        """Extract the response key from the AI's response."""
        match = re.search(r"\[\[(.*?)\]\]", text)
        if match:
            return match.group(1)
        return "default_response"

    async def update_library(self, key: str, user_input: str, ai_response: str):
        """Update the speech library with new training data."""
        entry = {"phrase": user_input, "confidence": 0.5}
        reply = {"response": ai_response, "confidence": 0.5}

        self.speech_library.setdefault("intents", {}).setdefault(key, [])
        self.speech_library.setdefault("responses", {}).setdefault(key, [])

        if entry not in self.speech_library["intents"][key]:
            self.speech_library["intents"][key].append(entry)

        if reply not in self.speech_library["responses"][key]:
            self.speech_library["responses"][key].append(reply)

        try:
            save_path = os.path.join(CONFIG_DIR, "speech_library.json")
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(self.speech_library, f, indent=2)
            logger.info(f"Updated speech_library.json")
        except Exception as e:
            logger.error(f"Failed to save updated speech_library: {e}")
