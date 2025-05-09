# modules/utils.py

import json
import os
from functools import lru_cache
import logging
from modules.s3_service import S3Service

logger = logging.getLogger("utils")

TENANT_MAP_PATH = "tenant_map.json"
DEFAULT_TENANT_ID = "default"

def normalize_message(msg: str) -> str:
    """Trim, lower, and remove punctuation from the message."""
    return msg.strip().lower()

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

def get_tenant_id_from_sender(sender_number: str) -> str:
    """Lookup the tenant_id for the given WhatsApp sender number."""
    sender_number = sender_number.replace("whatsapp:", "")
    if not os.path.exists(TENANT_MAP_PATH):
        logger.warning("tenant_map.json not found. Defaulting to fallback tenant.")
        return DEFAULT_TENANT_ID
    try:
        with open(TENANT_MAP_PATH, "r", encoding="utf-8") as f:
            tenant_map = json.load(f)
        tenant_id = tenant_map.get(sender_number)
        if tenant_id:
            logger.info(f"Tenant '{tenant_id}' matched for sender {sender_number}")
            return tenant_id
        logger.warning(f"No tenant match for sender {sender_number}. Using default tenant.")
        return DEFAULT_TENANT_ID
    except Exception as e:
        logger.error(f"Error reading tenant map: {e}")
        return DEFAULT_TENANT_ID
