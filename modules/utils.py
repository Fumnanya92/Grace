# modules/utils.py

import json
import os
from pathlib import Path
import logging
from functools import lru_cache
from modules.s3_service import S3Service
from logging_config import configure_logger

logger = configure_logger("utils")

TENANT_MAP_PATH = Path("tenant_map.json")
DEFAULT_TENANT_ID = "default"
TENANTS_DIR = Path("tenants")

async def detect_picture_request(message: str) -> bool:
    """Detect if user is asking to see pictures/designs."""
    triggers = [
        "send pictures", "send me pictures", "see designs", "show me",
        "catalog", "available designs", "pictures of dresses", "dress pictures",
        "send designs", "send catalog", "show dresses", "pictures available"
    ]
    message = message.lower()
    return any(trigger in message for trigger in triggers)


@lru_cache(maxsize=128)
async def cached_list_images():
    """Fetch the list of images from the S3 bucket (cached)."""
    try:
        images = await S3Service().list_images()
        return [{"name": img["name"], "url": img["url"]} for img in images]
    except Exception as e:
        logger.error(f"Error listing images from S3: {e}")
        raise


def get_tenant_id_from_sender(sender: str) -> str:
    tenant_map = get_tenant_map()
    for tenant_id, tenant_info in tenant_map.items():
        if sender.replace("whatsapp:", "") in tenant_info.get("platforms", []):
            return tenant_id
    return None


def get_tenant_map() -> dict:
    """Load tenant map from JSON file."""
    map_path = os.path.join("tenants", "tenant_map.json")
    try:
        if os.path.exists(map_path):
            with open(map_path) as f:
                return json.load(f)
        logger.warning("tenant_map.json not found. Returning empty map.")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to load tenant_map.json: {e}")
    return {}


def get_speech_library_path(tenant_id: str) -> Path:
    """Builds the speech library path for a tenant."""
    return TENANTS_DIR / tenant_id / "speech_library.json"


def ensure_tenant_structure(tenant_id: str):
    """Ensure the tenant folder structure exists."""
    tenant_dir = TENANTS_DIR / tenant_id
    if not tenant_dir.exists():
        logger.warning(f"Tenant directory '{tenant_dir}' not found. Creating it.")
        tenant_dir.mkdir(parents=True, exist_ok=True)


def load_speech_library(tenant_id: str) -> dict:
    """Load the speech library for a specific tenant."""
    path = get_speech_library_path(tenant_id)
    try:
        if not path.exists():
            logger.warning(f"[{tenant_id}] No speech_library.json found. Returning empty structure.")
            return {"training_data": []}
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[{tenant_id}] Failed to load speech library: {e}")
        return {"training_data": []}


def save_speech_library(tenant_id: str, data: dict) -> None:
    """Save the speech library for a specific tenant."""
    ensure_tenant_structure(tenant_id)
    path = get_speech_library_path(tenant_id)
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"[{tenant_id}] Speech library saved successfully.")
    except Exception as e:
        logger.error(f"[{tenant_id}] Failed to save speech library: {e}")


def update_speech_library(tenant_id: str, intent: str, phrase: str, response: str, confidence: float = 1.0):
    """Update the tenant’s speech library with new intent-response training data."""
    if not intent or not phrase or not response:
        logger.warning(f"[{tenant_id}] Skipping update due to missing values.")
        return

    lib = load_speech_library(tenant_id)

    if "training_data" not in lib:
        lib["training_data"] = []

    if not any(entry["phrase"].lower() == phrase.lower() and entry["intent"] == intent for entry in lib["training_data"]):
        lib["training_data"].append({
            "intent": intent,
            "phrase": phrase.lower(),
            "response": response,
            "confidence": confidence
        })
        # Sort the training data for better readability
        lib["training_data"].sort(key=lambda x: x["intent"])
        try:
            save_speech_library(tenant_id, lib)
        except PermissionError as e:
            logger.error(f"[{tenant_id}] Permission denied while saving speech library: {e}")
        logger.info(f"[{tenant_id}] Added intent '{intent}' with phrase '{phrase}'")
    else:
        logger.info(f"[{tenant_id}] Duplicate phrase-intent pair skipped.")
