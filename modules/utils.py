# modules/utils.py
import json
import os
from modules.s3_service import S3Service
from functools import lru_cache
import logging

# File path for the speech library
SPEECH_LIBRARY_PATH = os.getenv("SPEECH_LIBRARY_PATH", "speech_library.json")
logger = logging.getLogger("utils")

def load_speech_library():
    """Load the speech library from a JSON file."""
    try:
        if not os.path.exists(SPEECH_LIBRARY_PATH):
            return {"training_data": []}
        with open(SPEECH_LIBRARY_PATH, "r") as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"Failed to load speech library: {e}")
        return {"training_data": []}

def save_speech_library(library):
    """Save the speech library to a JSON file."""
    try:
        with open(SPEECH_LIBRARY_PATH, "w") as file:
            json.dump(library, file, indent=4)
    except Exception as e:
        logger.error(f"Failed to save speech library: {e}")

def update_speech_library(intent: str, user_message: str, bot_response: str, confidence: float = None):
    """
    Update the speech library with new user inputs and Grace responses, storing them in the new format.
    """
    if not intent or not user_message or not bot_response:
        logger.error("Invalid input: intent, user_message, and bot_response must be non-empty.")
        return

    try:
        library = load_speech_library()

        # Ensure the "training_data" key exists
        if "training_data" not in library:
            library["training_data"] = []

        # Check if the entry already exists
        existing_entries = [
            entry for entry in library["training_data"]
            if entry["intent"] == intent and entry["phrase"].lower() == user_message.lower()
        ]

        if not existing_entries:
            # Add a new entry to the training data
            library["training_data"].append({
                "intent": intent,
                "phrase": user_message.lower(),
                "response": bot_response,
                "confidence": confidence or 1.0  # Default confidence to 1.0 if not provided
            })
            logger.info(f"Added new entry to speech library: intent='{intent}', phrase='{user_message}', response='{bot_response}'")
        else:
            logger.info(f"Skipped adding duplicate entry for intent='{intent}', phrase='{user_message}'")

        save_speech_library(library)

    except Exception as e:
        logger.error(f"Failed to update speech library: {e}")

async def detect_picture_request(message: str) -> bool:
    """Detect if user is asking to see pictures/designs"""
    triggers = [
"send pictures", "send me pictures", "see designs", "show me", 
        "catalog", "available designs", "pictures of dresses", "dress pictures",
        "send designs", "send catalog", "show dresses", "pictures available"
    ]
    message = message.lower()
    return any(trigger in message for trigger in triggers)

@lru_cache(maxsize=128)
async def cached_list_images():
    """Fetch the list of images from the S3 bucket."""
    try:
        images = await S3Service().list_images()
        return [{"name": img["name"], "url": img["url"]} for img in images]
    except Exception as e:
        logger.error(f"Error listing images from S3: {e}")
        raise
