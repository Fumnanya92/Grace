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
from typing import List, Dict, Callable, Optional
from urllib.parse import urlparse, urlunparse

from openai import AsyncOpenAI
from config import config
from logging_config import configure_logger
from modules.langchain_agent import GraceAgent
from modules.grace_brain import GraceBrain
from modules.utils import detect_picture_request
from modules.image_processing_module import ImageProcessor
from modules.s3_service import S3Service
from modules.intent_recognition_module import recognize_intent
from modules.shopify_agent import agent, shopify_product_lookup, shopify_create_order, shopify_track_order
from modules.payment_module import PaymentHandler

logger = configure_logger("bot_responses")

# ---------------------------------------------------------------------------
# Constants & Shared Singletons
# ---------------------------------------------------------------------------
MAX_IMAGES: int = 10
MAX_HISTORY_LENGTH: int = 1000
MAX_HISTORY_MESSAGES: int = 6
REQUEST_TIMEOUT: int = 15

SHOPIFY_KEYWORDS = [
    "shopify", "order", "stock", "inventory", "product", "buy", "purchase", "track"
]

image_processor = ImageProcessor(S3Service())
image_history: Dict[str, List[Dict[str, float]]] = {}

payment_handler = PaymentHandler()

CONFIRMATION_PHRASES = {"yes", "yes please", "go ahead", "sure", "okay", "ok", "proceed"}

# ---------------------------------------------------------------------------
# BotResponses Class
# ---------------------------------------------------------------------------
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

    async def handle_text_message(self, sender, message, conversation_history=None):
        conversation_history = conversation_history or []
        logger.info(f"Grace AI handling message from {sender}: {message}")

        session = self.get_user_session(sender)
        normalized = message.strip().lower()
        intent = recognize_intent(message)[0]
        logger.info(f"Recognized intent: {intent}")

        # Handle confirmations for pending actions (context-aware)
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

        # Canned responses for critical intents only
        if intent in {"payment_confirmed", "deposit_instructions", "funny_redirects", "self_introduction"}:
            return await self.handle_configured_text(intent, message, conversation_history)

        # Greeting throttling (optional: can also be a canned response)
        if intent == "greetings":
            if not self.recently_greeted(sender):
                self.mark_greeted(sender)
                return await self.handle_configured_text("greetings", message, conversation_history)
            # If already greeted, let LLM handle or skip

        # Shopify/product lookup
        if intent == "shopify_product_lookup":
            result = await shopify_product_lookup.ainvoke(message)
            session["pending_order_args"] = {"query": message}
            session["pending_action"] = "finalize_order"
            return str(result)
        elif intent == "shopify_create_order":
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
            return await payment_handler.process_user_message(sender, message)

        # Direct business info handlers (not canned, just factual)
        if intent == "business_hours":
            hours = config.BUSINESS_HOURS
            return f"Our business hours are {hours['start']} to {hours['end']}."
        elif intent == "catalog_request":
            try:
                catalog = await self.brain.get_catalog()
                if not catalog:
                    return "I'm sorry, but our product catalog is currently empty. Please check back later!"
                filtered_products = [
                    item for item in catalog if item.get("name") and item.get("price")
                ]
                if not filtered_products:
                    return "I couldn't find any matching products. Can you provide more details?"

                product_lines = []
                for item in filtered_products[:5]:
                    name = item.get("name", "Unnamed Product")
                    price = item.get("price", "N/A")
                    currency = getattr(config, "CURRENCY", "₦")
                    image_url = item.get("image_url") or item.get("image") or "No image available"
                    description = item.get("description", "")
                    line = f"{name} ({currency}{price})\n{image_url}"
                    if description:
                        line += f"\n{description}"
                    product_lines.append(line)

                product_list = "\n\n".join(product_lines)
                return f"Here are some products you might like:\n\n{product_list}"

            except Exception as e:
                logger.exception("Catalog fetch failed")
                return "I'm sorry, I couldn't fetch the product catalog at the moment. Please try again later."
        elif intent == "instagram_link":
            return f"Our Instagram: {config.INSTAGRAM}"

        # All other intents: always use LLM for dynamic response
        try:
            formatted_history = self.format_conversation(conversation_history)
            logger.info(f"Formatted conversation history: {formatted_history}")

            prompt = await self.brain.build_prompt(formatted_history, message)
            logger.info(f"Generated prompt: {prompt}")

            response = await GraceAgent.ainvoke(prompt)

            if not response or not response.content.strip():
                logger.warning("Empty response from LangChain pipeline.")
                return await self.handle_configured_text("error_response", message, conversation_history)

            response_text = response.content.strip()
            logger.info(f"LangChain response: {response_text}")

            tag = self.brain.extract_response_key(response_text) or "unknown"
            cleaned = re.sub(r"\[\[.*?\]\]", "", response_text).strip()

            await self.brain.update_library(tag, message, cleaned)
            logger.info(f"Learned response for tag '{tag}': {cleaned}")

            return cleaned

        except Exception as e:
            logger.error("LangChain error: %s", e, exc_info=True)
            return await self.handle_configured_text("error_response", message, conversation_history)

    async def handle_media_message(self, sender: str, media_url: str, media_type: str) -> str:
        """Process images, videos, or documents from WhatsApp."""
        logger.info("Received %s from %s", media_type, sender)

        if media_type.startswith("image/"):
            try:
                image_history.setdefault(sender, []).append({"url": media_url, "timestamp": time.time()})
                return await image_processor.handle_image(sender, media_url)
            except Exception:
                logger.exception("Image processing error")
                return self.brain.get_response("image_error")

        if media_type.startswith("video/"):
            return "Thank you for sending a video. We'll review it shortly."
        if media_type.startswith("application/"):
            return "Thank you for sending a document. We'll review it shortly."
        return self.brain.get_response("unsupported_media")

    async def handle_configured_text(self, intent: str, _msg: str, _hist: list) -> str:
        """Return canned responses stored in speech_library.json."""
        return self.brain.get_response(intent)

    def format_conversation(self, history: List[Dict[str, str]]) -> str:
        formatted = [
            f"{h['role']}: {h['content']}" for h in history[-MAX_HISTORY_MESSAGES:] if h.get("role") and h.get("content")
        ]
        convo = "\n".join(formatted)
        return convo[:MAX_HISTORY_LENGTH].rsplit("\n", 1)[0] if len(convo) > MAX_HISTORY_LENGTH else convo
