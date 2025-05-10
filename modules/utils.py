# modules/utils.py

import json
import os
from pathlib import Path
import logging
from functools import lru_cache
from modules.s3_service import S3Service
from logging_config import configure_logger

logger = configure_logger("utils")

CONFIG_DIR = Path("config")  # Centralized configuration directory
CONFIG_FILES = {
    "speech_library": CONFIG_DIR / "speech_library.json",
    "catalog": CONFIG_DIR / "catalog.json",
    "config": CONFIG_DIR / "config.json",
    "fallback_responses": CONFIG_DIR / "fallback_responses.json"
}

SPEECH_LIBRARY_FILE = os.path.join(CONFIG_DIR, "speech_library.json")

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


def ensure_config_structure():
    """Ensure the centralized configuration folder structure exists."""
    if not CONFIG_DIR.exists():
        logger.warning(f"Configuration directory '{CONFIG_DIR}' not found. Creating it.")
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config_file(file_key: str) -> dict:
    """Load a configuration file from the centralized config directory."""
    ensure_config_structure()
    file_path = CONFIG_FILES.get(file_key)
    if not file_path:
        logger.error(f"Invalid configuration file key: {file_key}")
        return {}

    try:
        if not file_path.exists():
            logger.warning(f"Configuration file '{file_path}' not found. Returning empty structure.")
            return {}
        with file_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load configuration file '{file_path}': {e}")
        return {}


def save_config_file(file_key: str, data: dict) -> None:
    """Save a configuration file to the centralized config directory."""
    ensure_config_structure()
    file_path = CONFIG_FILES.get(file_key)
    if not file_path:
        logger.error(f"Invalid configuration file key: {file_key}")
        return

    try:
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Configuration file '{file_path}' saved successfully.")
    except Exception as e:
        logger.error(f"Failed to save configuration file '{file_path}': {e}")


def update_speech_library(intent: str, phrase: str, response: str, confidence: float = 1.0):
    """Update the speech library with new intent-response training data."""
    if not intent or not phrase or not response:
        logger.warning("Skipping update due to missing values.")
        return

    lib = load_config_file("speech_library")

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
            save_config_file("speech_library", lib)
        except PermissionError as e:
            logger.error(f"Permission denied while saving speech library: {e}")
        logger.info(f"Added intent '{intent}' with phrase '{phrase}'")
    else:
        logger.info(f"Duplicate phrase-intent pair skipped.")


def load_speech_library() -> dict:
    """Load the speech library from the centralized configuration directory."""
    try:
        with open(SPEECH_LIBRARY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Speech library file '{SPEECH_LIBRARY_FILE}' not found. Returning empty library.")
        return {"intents": {}, "responses": {}}
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding speech library JSON: {e}")
        return {"intents": {}, "responses": {}}
