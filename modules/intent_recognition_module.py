import re
from typing import List
from modules.utils import load_speech_library  # Import the speech library loader
from logging_config import configure_logger

# Initialize the logger
logger = configure_logger("intent_recognition")


def normalize_message(message):
    """
    Normalize the message to a string regardless of whether it's a string, dictionary, or list.
    """
    if isinstance(message, str):
        # If it's already a string, return it as-is.
        return message
    elif isinstance(message, dict):
        # If it's a dictionary, try to get the text field (default to empty string if not found).
        return message.get("text", message.get("content", ""))
    elif isinstance(message, list):
        # If it's a list, join all elements into a single string.
        return " ".join(str(item) for item in message)
    else:
        # If it's some other type, convert it to a string.
        return str(message)


def recognize_intent(message: str) -> str:
    """
    Enhanced intent recognition for Grace's assistant.
    Combines dynamic intent recognition from the speech library with predefined logic.
    Prioritizes the most relevant intent when multiple intents are detected.
    """
    intents = []  # Initialize an empty list to store identified intents
    message = normalize_message(message)

    # Load dynamic intents from the speech library
    library = load_speech_library()
    if "intents" in library:
        for intent, phrases in library["intents"].items():
            # Ensure phrases is a list of strings
            if not all(isinstance(phrase, str) for phrase in phrases):
                logger.warning(f"Invalid phrases for intent '{intent}': {phrases}")
                continue

            # Match dynamic intents based on phrases
            if any(phrase in message for phrase in phrases):
                intents.append(intent)

    # If no dynamic intent is matched, fall back to predefined logic
    if not intents:
        predefined_intents = {
            "greetings": [
                "hi", "hello", "good morning", "good afternoon", "good evening", "hey",
                "greetings", "sup", "yo", "howdy", "what's up", "good day"
            ],
            "deposit_instructions": [
                "how to pay", "payment options", "payment methods", "bank details",
                "account information", "how do I pay", "payment instructions",
                "where to send money", "how can I transfer", "payment process"
            ],
            "ask_for_designs": [
                "colors", "prints", "catalog", "designs", "styles", "new arrivals",
                "ordering process", "collections", "available designs"
            ],
            "customer_engagement": [
                "help", "guide", "show me", "need assistance", "can you help",
                "tell me more", "assist", "give me info", "show me more"
            ],
            "selection_confirmation": [
                "confirm order", "order now", "place order", "ready to buy",
                "book for me", "lock in my order", "finalize my order",
                "I’m ready to purchase", "let’s close the deal"
            ],
            "off_topic": [
                r"weather", r"your name", r"where are you", r"who are you",
                r"how old are you", r"tell me a joke", r"are you real", r"football",
                r"game", r"holiday", r"funny"
            ],
            "image_request": [
                "show me pictures", "can I see designs", "send me images",
                "show me your catalog", "display your designs", "can I view your collection",
                "show me some samples", "see your designs"
            ],
            "package_details": [
                "package details", "wholesale package", "premium package",
                "offer details", "what's included", "tell me about the package"
            ]
        }

        # Match predefined intents
        for intent, keywords in predefined_intents.items():
            if intent == "off_topic":
                # Use regex for off-topic patterns
                if any(re.search(pattern, message, re.IGNORECASE) for pattern in keywords):
                    intents.append(intent)
            else:
                # Use simple keyword matching for other intents
                if any(keyword in message for keyword in keywords):
                    intents.append(intent)

    # Default if no specific intent is recognized
    if not intents:
        intents.append("unknown")

    # Prioritize intents if multiple are detected
    priority_order = ["package_details", "ask_for_designs", "deposit_instructions", "greetings", "off_topic", "image_request"]
    for intent in priority_order:
        if intent in intents:
            logger.info(f"Selected intent: {intent}")
            return intent

    # Default if no specific intent is recognized
    logger.info("No specific intent recognized. Defaulting to 'unknown'.")
    return "unknown"
