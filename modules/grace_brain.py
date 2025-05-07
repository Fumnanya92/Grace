# grace_brain.py
import json
import os
from typing import Optional, Dict
from logging_config import configure_logger

logger = configure_logger("grace_brain")

TENANTS_DIR = "tenants"
DEFAULT_FALLBACKS = "fallback_responses.json"

class GraceBrain:
    def __init__(self, tenant_id: str = "akanrabyatuche"):
        self.tenant_id = tenant_id
        self.tenant_path = os.path.join(TENANTS_DIR, self.tenant_id)

        logger.info(f"GraceBrain initialized for tenant: {self.tenant_id}")

        self.speech_library = self.load_file("speech_library.json", default={"intents": {}, "responses": {}})
        self.tone_config = self.load_file("tone.json", default={"style": "friendly", "persona": "grace"})
        self.catalog = self.load_file("catalog.json", default=[])
        self.fallbacks = self.load_file(DEFAULT_FALLBACKS, default={})

    def load_file(self, filename: str, default: Optional[dict] = None) -> dict:
        """Safely load a JSON file with a fallback default."""
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
        """
        Fetch a dynamic response using the tenant’s speech library.
        If not found, fallback to default templates.
        """
        responses = self.speech_library.get("responses", {}).get(key, [])
        if responses:
            response = responses[0].get("response", "")
            return response.format(**kwargs)

        logger.warning(f"No response found for key '{key}' in tenant speech_library.")
        return self.fallbacks.get(key, f"[{key}] I'm still learning how to respond to this.")

    def get_catalog(self) -> list:
        """Return tenant’s current product catalog."""
        return self.catalog

    def get_tone(self) -> Dict[str, str]:
        """Return the tone/persona style for this tenant."""
        return self.tone_config

    def get_tenant_config(self) -> dict:
        """Load the config.json file for this tenant (e.g., name, WhatsApp number, etc.)."""
        return self.load_file("config.json", default={})
