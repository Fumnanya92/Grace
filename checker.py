import json
import os
import re
from typing import Optional, Dict, List
from logging_config import configure_logger

logger = configure_logger("grace_brain")

TENANTS_DIR = "tenants"
DEFAULT_FALLBACKS = "fallback_responses.json"

class GraceBrain:
    def __init__(self, tenant_id: str = "akanrabyatuche"):
        self.tenant_id = tenant_id
        self.tenant_path = os.path.join(TENANTS_DIR, self.tenant_id)

        logger.info(f"GraceBrain initialized for tenant: {self.tenant_id}")

        self.config = self._load_file("config.json", default={})
        self.speech_library = self._load_file("speech_library.json", default={"intents": {}, "responses": {}})
        self.tone_config = self._load_file("tone.json", default={"style": "friendly", "persona": "grace"})
        self.catalog = self._load_file("catalog.json", default=[])
        self.fallbacks = self._load_file(DEFAULT_FALLBACKS, default={})

    def _load_file(self, filename: str, default: Optional[dict] = None) -> dict:
        path = os.path.join(self.tenant_path, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"{filename} not found for tenant {self.tenant_id}. Using default.")
            return default or {}
        except Exception as e:
            logger.error(f"Failed to load {filename} for tenant {self.tenant_id}: {e}")
            return default or {}

    async def get_response(self, key: str, **kwargs) -> str:
        responses = self.speech_library.get("responses", {}).get(key, [])
        if responses:
            response = responses[0].get("response", "")
            return response.format(**kwargs)
        logger.warning(f"No response found for key '{key}' in tenant speech_library.")
        return self.fallbacks.get(key, f"[{key}] I'm still learning how to respond to this.")

    def get_catalog(self) -> list:
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

    def load_tone(self) -> dict:
        return self.tone_config or {
            "greeting_prefix": "Hello 👋",
            "tone": "neutral",
            "fallback_persona": "You are Grace, a helpful sales assistant guiding users toward making purchases."
        }

    async def build_prompt(self, formatted_history: str, user_message: str) -> str:
        tone = self.load_tone()
        persona = tone.get("fallback_persona", "You are Grace, a helpful assistant.")
        catalog_intro = "\n".join(
            [f"- {item['name']}: ₦{item.get('price', 'N/A')}" for item in self.catalog[:5]]
        )
        keys = self.get_intent_keys()
        return (
            f"{persona}\n"
            f"Recent conversation:\n{formatted_history}\n\n"
            f"User: {user_message}\n\n"
            f"Product Highlights:\n{catalog_intro}\n"
            "Respond conversationally and helpfully, with a warm tone.\n"
            "Only use one of the following keys to tag your message: "
            + ", ".join([f"[[{k}]]" for k in keys]) + ".\n"
        )

    def extract_response_key(self, text: str) -> str:
        match = re.search(r"\[\[(.*?)\]\]", text)
        return match.group(1) if match else "default_response"

    async def update_library(self, key: str, user_input: str, ai_response: str):
        entry = {"phrase": user_input, "confidence": 0.5}
        reply = {"response": ai_response, "confidence": 0.5}

        self.speech_library.setdefault("intents", {}).setdefault(key, [])
        self.speech_library.setdefault("responses", {}).setdefault(key, [])

        if entry not in self.speech_library["intents"][key]:
            self.speech_library["intents"][key].append(entry)
        if reply not in self.speech_library["responses"][key]:
            self.speech_library["responses"][key].append(reply)

        try:
            save_path = os.path.join(self.tenant_path, "speech_library.json")
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(self.speech_library, f, indent=2)
            logger.info(f"Updated speech_library.json for {self.tenant_id}")
        except Exception as e:
            logger.error(f"Failed to save updated speech_library for {self.tenant_id}: {e}")
