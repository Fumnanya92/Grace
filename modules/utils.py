# modules/utils.py
"""
Utility helpers for Grace:
* speech_library loading and live updates
* intent lookup & canned responses
* S3 image cache
* generic config file helpers
"""

import json
import os
import random
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Set

from modules.s3_service import S3Service
from logging_config import configure_logger

logger = configure_logger("utils")

# ---------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------
CONFIG_DIR = Path("config")
CONFIG_FILES = {
    "speech_library": CONFIG_DIR / "speech_library.json",
    "catalog": CONFIG_DIR / "catalog.json",
    "config": CONFIG_DIR / "config.json",
    "fallback_responses": CONFIG_DIR / "fallback_responses.json",
}
SPEECH_LIBRARY_FILE = CONFIG_FILES["speech_library"]

# ---------------------------------------------------------------------
# In‑memory tables populated from speech_library.json
# ---------------------------------------------------------------------
INTENT_PHRASES: Dict[str, Set[str]] = {}
INTENT_RESPONSES: Dict[str, List[Dict]] = {}


def _rebuild_tables(data: dict) -> None:
    """(Re)build INTENT_PHRASES & INTENT_RESPONSES from training_data list."""
    INTENT_PHRASES.clear()
    INTENT_RESPONSES.clear()

    for row in data.get("training_data", []):
        if not row.get("phrase") or not row.get("response"):
            logger.warning("Skipping invalid row in training_data: %s", row)
            continue
        intent = row.get("intent", "default_response")
        phrase = row["phrase"].lower().strip()

        INTENT_PHRASES.setdefault(intent, set()).add(phrase)
        INTENT_RESPONSES.setdefault(intent, []).append(
            {
                "response": row["response"],
                "confidence": row.get("confidence", 1.0),
            }
        )


def _load_speech_library_into_tables() -> None:
    """Read speech_library.json (training_data format) on startup."""
    if not SPEECH_LIBRARY_FILE.exists():
        logger.warning("speech_library.json not found; starting with empty tables")
        return

    try:
        data = json.loads(SPEECH_LIBRARY_FILE.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        logger.error("Error reading speech_library: %s", e)
        return

    if "training_data" not in data:
        logger.error("speech_library.json must include a 'training_data' list")
        return

    _rebuild_tables(data)


_load_speech_library_into_tables()

# ---------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------
def match_intent(message: str) -> Optional[str]:
    """Return first intent whose phrase exactly matches the message."""
    logger.info("Matching intent for message: %s", message)
    for intent, phrases in INTENT_PHRASES.items():
        if message in phrases:
            logger.info("Matched intent: %s", intent)
            return intent
    logger.info("No match found in speech_library.")
    return None


def get_canned_response(intent: str) -> Optional[str]:
    """Return one canned response for the intent, weighted by confidence."""
    pool = INTENT_RESPONSES.get(intent)
    if not pool:
        return None

    total = sum(r["confidence"] for r in pool)
    pick = random.random() * total
    for r in pool:
        pick -= r["confidence"]
        if pick <= 0:
            return r["response"]
    # Fallback (shouldn’t happen)
    return pool[-1]["response"]


def update_speech_library(
    intent: str, phrase: str, response: str, confidence: float = 1.0
) -> None:
    """Append a new training row and refresh in‑memory tables."""
    ensure_config_structure()

    # basic validation
    if not all(isinstance(x, str) and x.strip() for x in (intent, phrase, response)):
        logger.error("Intent, phrase and response must be non‑empty strings")
        return
    if not (0.0 <= confidence <= 1.0):
        logger.error("Confidence must be between 0 and 1")
        return

    try:
        data = (
            json.loads(SPEECH_LIBRARY_FILE.read_text(encoding="utf-8"))
            if SPEECH_LIBRARY_FILE.exists()
            else {"training_data": []}
        )
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to load speech_library.json: %s", e)
        return

    # prevent duplicates
    dup = next(
        (
            True
            for row in data["training_data"]
            if row["intent"] == intent
            and row["phrase"].lower().strip() == phrase.lower().strip()
        ),
        False,
    )
    if dup:
        logger.info("Duplicate phrase‑intent pair skipped.")
        return

    new_entry = {
        "intent": intent,
        "phrase": phrase.lower().strip(),
        "response": response,
        "confidence": confidence,
    }
    data["training_data"].append(new_entry)
    data["training_data"].sort(key=lambda x: x["intent"])

    try:
        SPEECH_LIBRARY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Added to speech_library: %s", new_entry)
        _rebuild_tables(data)  # live‑refresh
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to save speech_library.json: %s", e)


# ---------------------------------------------------------------------
# Picture detection & S3 helpers
# ---------------------------------------------------------------------
def load_picture_triggers() -> List[str]:
    triggers_file = CONFIG_DIR / "picture_triggers.json"
    if triggers_file.exists():
        return json.loads(triggers_file.read_text(encoding="utf-8"))
    # default triggers
    return [
        "send pictures",
        "send me pictures",
        "see designs",
        "show me",
        "catalog",
        "available designs",
    ]


async def detect_picture_request(message: str) -> bool:
    return any(t in message.lower() for t in load_picture_triggers())


@lru_cache(maxsize=128)
async def cached_list_images():
    """Cached list of product images from S3."""
    try:
        images = await S3Service().list_images()
        return [{"name": i["name"], "url": i["url"]} for i in images]
    except Exception as e:  # noqa: BLE001
        logger.error("Error listing images from S3: %s", e)
        raise


# ---------------------------------------------------------------------
# Generic config file helpers
# ---------------------------------------------------------------------
def ensure_config_structure() -> None:
    if not CONFIG_DIR.exists():
        logger.warning("Configuration directory '%s' not found. Creating it.", CONFIG_DIR)
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config_file(file_key: str) -> dict:
    """Return parsed JSON for the given key, or empty dict on error."""
    ensure_config_structure()
    file_path = CONFIG_FILES.get(file_key)
    if not file_path:
        logger.error("Invalid configuration file key: %s", file_key)
        return {}
    try:
        return json.loads(file_path.read_text(encoding="utf-8")) if file_path.exists() else {}
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to load configuration file '%s': %s", file_path, e)
        return {}


def save_config_file(file_key: str, data: dict) -> None:
    ensure_config_structure()
    file_path = CONFIG_FILES.get(file_key)
    if not file_path:
        logger.error("Invalid configuration file key: %s", file_key)
        return
    try:
        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Configuration file '%s' saved successfully.", file_path)
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to save configuration file '%s': %s", file_path, e)
