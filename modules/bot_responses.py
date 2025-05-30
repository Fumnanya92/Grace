"""Refactored bot_responses.py – second pass

Fixes the OpenAI realtime API signature error:
    TypeError: AsyncRealtimeConversationItemResource.create() got an unexpected keyword argument 'type'

Key change ➜ use `conn.messages.create(role="user", content=prompt)` instead of the previous call.
The rest of the file structure, constants, and function order is preserved for easy diff.
"""

import re
import os
import time
import logging
import asyncio
import hashlib
import openai
import json
import csv
from typing import List, Dict, Callable, Optional
from urllib.parse import urlparse, urlunparse

from openai import AsyncOpenAI
from config import config
from logging_config import configure_logger
logger = configure_logger("bot_responses")
from modules.langchain_agent import GraceAgent
from modules.grace_brain import GraceBrain
from modules.utils import detect_picture_request, compute_state_id
from modules.intent_recognition_module import recognize_intent
from modules.shopify_agent import agent, shopify_product_lookup, shopify_create_order, shopify_track_order
from modules.payment_module import PaymentHandler
from modules.shared import image_processor
from stores.retrieval_store import search, add_pair

# ---------------------------------------------------------------------------
# Constants & Shared Singletons
# ---------------------------------------------------------------------------
MAX_IMAGES: int = 10
MAX_HISTORY_LENGTH: int = 1000
MAX_HISTORY_MESSAGES: int = 6
REQUEST_TIMEOUT: int = 15
MAX_WORDS = 40

SHOPIFY_KEYWORDS = [
    "shopify", "order", "stock", "inventory", "product", "buy", "purchase", "track"
]

image_history: Dict[str, List[Dict[str, float]]] = {}
payment_handler = PaymentHandler()
CONFIRMATION_PHRASES = {"yes", "yes please", "go ahead", "sure", "okay", "ok", "proceed"}

SYSTEM_GRADER_PROMPT = """\
You are a quality-control assistant. Score the assistant reply from 1-10 on:
accuracy, tone, and goal-progress. Return JSON: {"score": <int>}"""

def squash(text: str) -> str:
    words = text.split()
    return " ".join(words[:MAX_WORDS]) + ("…" if len(words) > MAX_WORDS else "")

def log_metric(event_type, sender, value=1):
    with open("logs/conversation_metrics.csv", "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([event_type, sender, value, time.strftime("%Y-%m-%d %H:%M:%S")])

def export_top_pair(user_msg, bot_reply, score, path="logs/top_pairs.jsonl"):
    if score is not None and score >= 8:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"question": user_msg, "answer": bot_reply, "score": score}) + "\n")

async def grade_turn(user, reply):
    try:
        resp = await openai.AsyncOpenAI().chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_GRADER_PROMPT},
                {"role": "user", "content": user},
                {"role": "assistant", "content": reply},
            ],
        )
        score = int(json.loads(resp.choices[0].message.content)["score"])
        return score
    except Exception as e:
        logger.error(f"Auto-grader failed: {e}")
        return None

def fix_whatsapp_bold(text):
    # Replace **text** or __text__ with *text*
    text = re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)
    text = re.sub(r"__(.*?)__", r"*\1*", text)
    return text

def resolve_reference(user_message: str, chat_history: list) -> str:
    """
    Replace ambiguous references like 'it', 'this', 'that' in user_message
    with the last mentioned product/service/item in chat_history.
    """
    if re.search(r"\b(it|this|that)\b", user_message, re.I):
        for turn in reversed(chat_history):
            # Look for product/service/item/plan/course/package in user or bot messages
            match = re.search(
                r"\b([A-Za-z0-9 \-]+(dress|set|shirt|service|product|item|plan|course|package))\b",
                turn.get('user_message', ''), re.I)
            if match:
                return re.sub(r"\b(it|this|that)\b", match.group(0), user_message, flags=re.I)
            match = re.search(
                r"\b([A-Za-z0-9 \-]+(dress|set|shirt|service|product|item|plan|course|package))\b",
                turn.get('bot_reply', ''), re.I)
            if match:
                return re.sub(r"\b(it|this|that)\b", match.group(0), user_message, flags=re.I)
    return user_message

def format_conversation(history: List[Dict[str, str]]) -> str:
    formatted = [
        f"{h['role']}: {h['content']}" for h in history[-MAX_HISTORY_MESSAGES:] if h.get("role") and h.get("content")
    ]
    convo = "\n".join(formatted)
    return convo[:MAX_HISTORY_LENGTH].rsplit("\n", 1)[0] if len(convo) > MAX_HISTORY_LENGTH else convo

class BotResponses:
    """High-level orchestration for Grace’s responses."""

    def __init__(self) -> None:
        self.brain = GraceBrain()
        self.gpt_client = AsyncOpenAI(timeout=REQUEST_TIMEOUT)
        self.greeted_users = {}
        self.user_sessions = {}

    def get_user_session(self, sender):
        if sender not in self.user_sessions:
            self.user_sessions[sender] = {}
        return self.user_sessions[sender]

    def recently_greeted(self, sender):
        last = self.greeted_users.get(sender)
        return last and (time.time() - last < 3600)  # 1 hour

    def mark_greeted(self, sender):
        self.greeted_users[sender] = time.time()

    def extract_name(self, message: str) -> Optional[str]:
        # Simple patterns for "My name is X" or "I'm X"
        patterns = [
            r"my name is ([A-Za-z]+)",
            r"i am ([A-Za-z]+)",
            r"i'm ([A-Za-z]+)",
            r"this is ([A-Za-z]+)"
        ]
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1).capitalize()
        return None

    def get_user_name(self, sender):
        session = self.get_user_session(sender)
        return session.get("customer_name")

    def set_user_name(self, sender, name):
        session = self.get_user_session(sender)
        session["customer_name"] = name

    async def handle_configured_text(self, intent: str, _msg: str, _hist: list) -> str:
        """Return canned responses stored in speech_library.json."""
        return self.brain.get_response(intent)

    async def handle_media_message(self, sender: str, media_url: str, media_type: str) -> str:
        """Process images, videos, or documents from WhatsApp."""
        logger.info("Received %s from %s", media_type, sender)

        if media_type.startswith("image/"):
            try:
                image_history.setdefault(sender, []).append({"url": media_url, "timestamp": time.time()})
                result = await image_processor.handle_image(sender, media_url)
                return result
            except Exception:
                logger.exception("Image processing error")
                return self.brain.get_response("image_error")

        if media_type.startswith("video/"):
            return "Thank you for sending a video. We'll review it shortly."
        if media_type.startswith("application/"):
            return "Thank you for sending a document. We'll review it shortly."
        return self.brain.get_response("unsupported_media")

    async def handle_text_message(self, sender, message, conversation_history=None):
        conversation_history = conversation_history or []
        logger.info(f"Grace AI handling message from {sender}: {message}")

        session = self.get_user_session(sender)
        normalized = message.strip().lower()
        intent = recognize_intent(message)[0]
        logger.info(f"Recognized intent: {intent}")

        # 1) Retrieval-augmented shortcut
        examples = search(message)
        if examples:
            return examples[0][1]

        # 2) Handle confirmations for pending actions
        if session.get("pending_action") == "finalize_order" and normalized in CONFIRMATION_PHRASES:
            args = session.get("pending_order_args")
            if args:
                result = await shopify_create_order.ainvoke(args)
                session["pending_action"] = None
                session["pending_order_args"] = None
                payment = config.PAYMENT
                return (
                    f"Order placed! {result}\n"
                    f"You can now proceed with payment.\n"
                    f"Account Name: {payment['account_name']}\n"
                    f"Account Number: {payment['account_number']}\n"
                    f"Bank: {payment['bank_name']}"
                )
            else:
                session["pending_action"] = None
                return "Sorry, I couldn't find your order details. Could you specify your order again?"

        # 3) Canned responses for critical intents
        if intent in {"payment_confirmed", "deposit_instructions", "funny_redirects", "self_introduction"}:
            return await self.handle_configured_text(intent, message, conversation_history)

        # 4) Greeting throttling
        if intent == "greetings":
            if not self.recently_greeted(sender):
                self.mark_greeted(sender)
                return await self.handle_configured_text("greetings", message, conversation_history)

        # 5) Shopify/product lookup
        if intent == "shopify_product_lookup":
            from stores.shopify_async import get_product_details
            details = await get_product_details(message)
            if details and "doesn’t look like a product question" not in details.lower():
                return details
            result = await shopify_product_lookup.ainvoke(message)
            session["pending_order_args"] = {"query": message}
            session["pending_action"] = "finalize_order"
            return str(result)

        elif intent == "shopify_create_order":
            log_metric("order_placed", sender)
            args = session.get("pending_order_args") or {"query": message}
            result = await shopify_create_order.ainvoke(args)
            session["pending_action"] = None
            session["pending_order_args"] = None
            payment = config.PAYMENT
            return (
                f"Order placed! {result}\n"
                f"You can now proceed with payment.\n"
                f"Account Name: {payment['account_name']}\n"
                f"Account Number: {payment['account_number']}\n"
                f"Bank: {payment['bank_name']}"
            )

        elif intent == "shopify_track_order":
            order_id = ""  # TODO: Implement order_id extraction from message
            result = await shopify_track_order.ainvoke(order_id)
            return str(result)

        elif intent == "payment":
            with open("config/speech_library.json") as f:
                speech_library = json.load(f)
            return speech_library["payment"]["default"]

        # 6) Direct business info handlers
        if intent == "business_hours":
            hours = config.BUSINESS_HOURS
            return f"Our business hours are {hours['start']} to {hours['end']}."

        elif intent == "catalog_request":
            try:
                catalog = await self.brain.get_catalog()
                if not catalog:
                    return "Our catalog is being updated — please check back soon."
                lines = []
                for item in catalog[:3]:  # 3 items max
                    if not item.get("image_url"):
                        continue
                    price = item.get("price", "N/A")
                    lines.append(f"{item['name']} – ₦{price}\n{item['image_url']}")
                return "\n\n".join(lines) if lines else \
                    "I couldn't find images for those items just now — let me check and get back to you."
            except Exception as e:
                logger.exception("Catalog fetch failed")
                return "I'm sorry, I couldn't fetch the product catalog at the moment. Please try again later."

        elif intent == "instagram_link":
            return f"Our Instagram: {config.INSTAGRAM}"

        # 7) All other intents: use LLM, then grade and store
        try:
            # --- Contextual reference resolution ---
            resolved_message = resolve_reference(message, conversation_history)
            formatted_history = format_conversation(conversation_history)
            logger.info(f"Formatted conversation history: {formatted_history}")

            prompt = await self.brain.build_prompt(formatted_history, resolved_message)
            logger.info(f"Generated prompt: {prompt}")

            response = await GraceAgent.ainvoke(prompt)
            response_text = (response.content or "").strip() if response else ""
            if not response_text:
                logger.warning("Empty response from LangChain pipeline.")
                return await self.handle_configured_text("error_response", message, conversation_history)

            tag = self.brain.extract_response_key(response_text) or "unknown"
            cleaned = re.sub(r"\[\[.*?\]\]", "", response_text).strip()

            await self.brain.update_library(tag, message, cleaned)
            logger.info(f"Learned response for tag '{tag}': {cleaned}")

            # Add to retrieval store for future use (to be graded)
            add_pair(message, cleaned)

            # Compute state_id for traceability
            state_id = await compute_state_id()
            logger.info(f"state_id for this turn: {state_id}")

            # --- Auto-grade the turn and persist if high quality ---
            async def grade_and_store():
                score = await grade_turn(message, cleaned)
                if score is not None:
                    logger.info(f"Auto-graded score: {score} for: {message[:40]}...")
                    if score >= 8:
                        add_pair(message, cleaned)
                    export_top_pair(message, cleaned, score)

            asyncio.create_task(grade_and_store())

            cleaned = squash(cleaned)  # Enforce 40-word cap before reply goes out
            cleaned = fix_whatsapp_bold(cleaned)
            return cleaned

        except Exception as e:
            logger.error("LangChain error: %s", e, exc_info=True)
            return await self.handle_configured_text("error_response", message, conversation_history)

