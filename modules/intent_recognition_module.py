# modules/intent_recognition_module.py
"""
Intent recognition for Grace.

Flow hierarchy
--------------
1. Exact‑phrase lookup from speech_library      (fast, deterministic)
2. Keyword / regex heuristics (fallback list)   (cheap, explainable)
3. Default "unknown"

The function `recognize_intent()` returns a *list* so existing callers
(BotResponses) remain unchanged, but it always puts the primary intent
at index 0.
"""
import logging
import re
from typing import List


from logging_config import configure_logger
from modules.utils import match_intent

logger = configure_logger("intent_recognition")

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def normalize_message(message) -> str:
    """Flatten incoming Twilio/FastAPI payload to a plain string."""
    if isinstance(message, str):
        return message
    if isinstance(message, dict):
        return message.get("text") or message.get("content", "")
    if isinstance(message, list):
        return " ".join(str(x) for x in message)
    return str(message)


# ---------------------------------------------------------------------
# Heuristic keyword / regex map
# ---------------------------------------------------------------------
KEYWORD_INTENTS = {
    "greetings": [
        "hi",
        "hello",
        "good morning",
        "good afternoon",
        "good evening",
        "hey",
        "greetings",
        "sup",
        "yo",
        "howdy",
        "what's up",
        "good day",
    ],
    "deposit_instructions": [
        "how to pay",
        "payment options",
        "payment methods",
        "bank details",
        "account information",
        "how do i pay",
        "payment instructions",
        "where to send money",
        "how can i transfer",
        "payment process",
    ],
    "ask_for_designs": [
        "colors",
        "prints",
        "catalog",
        "designs",
        "styles",
        "new arrivals",
        "ordering process",
        "collections",
        "available designs",
    ],
    "customer_engagement": [
        "help",
        "guide",
        "show me",
        "need assistance",
        "can you help",
        "tell me more",
        "assist",
        "give me info",
        "show me more",
    ],
    "selection_confirmation": [
        "confirm order",
        "order now",
        "place order",
        "ready to buy",
        "book for me",
        "lock in my order",
        "finalize my order",
        "i’m ready to purchase",
        "let’s close the deal",
    ],
    "image_request": [
        "show me pictures",
        "can i see designs",
        "send me images",
        "show me your catalog",
        "display your designs",
        "can i view your collection",
        "show me some samples",
        "see your designs",
    ],
    "package_details": [
        "package details",
        "wholesale package",
        "premium package",
        "offer details",
        "what's included",
        "tell me about the package",
    ],
    "shopify_product_lookup": [
        "in stock",
        "stock of",
        "do you have",
        "is available",
        "availability",
        "product details",
        "how much is",
        "price of",
        "show product",
        "find product",
    ],
    "shopify_create_order": [
        "order for",
        "buy",
        "purchase",
        "i want to order",
        "place order",
        "create order",
        "checkout",
        "add to cart",
    ],
    "shopify_track_order": [
        "track order",
        "order status",
        "where is my order",
        "has my order shipped",
        "delivery status",
        "order tracking",
        "track my order",
    ],
}

# Separate regex patterns that need full match / ignore‑case
REGEX_INTENTS = {
    "off_topic": [
        r"weather",
        r"your name",
        r"where are you",
        r"who are you",
        r"how old are you",
        r"tell me a joke",
        r"are you real",
        r"football",
        r"game",
        r"holiday",
        r"funny",
    ]
}

PRIORITY_ORDER = [
    "package_details",
    "ask_for_designs",
    "deposit_instructions",
    "greetings",
    "off_topic",
    "image_request",
]

# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------
def recognize_intent(message: str) -> List[str]:
    """
    Detect the user's intent.

    Returns
    -------
    list[str]
        Primary intent at index 0; returns ["unknown"] if nothing matches.
    """
    msg = normalize_message(message).lower().strip()
    logger.info("Normalized message: %s", msg)

    # 1) Exact phrase match from speech_library
    if intent := match_intent(msg):
        logger.info("Selected intent from speech_library: %s", intent)
        return [intent]

    # 2) Keyword list heuristics
    matched: List[str] = []
    for intent_key, keywords in KEYWORD_INTENTS.items():
        if any(keyword in msg for keyword in keywords):
            matched.append(intent_key)

    # 3) Regex heuristics
    for intent_key, patterns in REGEX_INTENTS.items():
        if any(re.search(pat, msg, re.IGNORECASE) for pat in patterns):
            matched.append(intent_key)

    if not matched:
        matched.append("unknown")

    # Resolve priority
    for p in PRIORITY_ORDER:
        if p in matched:
            logger.info("Selected intent via heuristic: %s", p)
            return [p]

    logger.info("No intent matched. Returning 'unknown'.")
    return matched
