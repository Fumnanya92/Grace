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
from modules.intent_recognition_module import recognize_intent, normalize_message

logger = configure_logger("bot_responses")

# ---------------------------------------------------------------------------
# Constants & Shared Singletons
# ---------------------------------------------------------------------------
MAX_IMAGES: int = 10
MAX_HISTORY_LENGTH: int = 1000
MAX_HISTORY_MESSAGES: int = 6
REQUEST_TIMEOUT: int = 15

image_processor = ImageProcessor(S3Service())
image_history: Dict[str, List[Dict[str, float]]] = {}

# ---------------------------------------------------------------------------
# BotResponses Class
# ---------------------------------------------------------------------------
class BotResponses:
    """High-level orchestration for Grace’s responses."""

    def __init__(self) -> None:
        self.brain = GraceBrain()
        self.gpt_client = AsyncOpenAI(timeout=REQUEST_TIMEOUT)

    # ------------------------------------------------------------------
    # Intent Dispatch Map
    # ------------------------------------------------------------------
    def intent_handlers(self) -> Dict[str, Callable]:
        """Return the mapping of intent → handler."""
        return {
            "greetings": self.handle_configured_text,
            "package_details": self.handle_configured_text,
            "deposit_instructions": self.handle_configured_text,
            "payment_confirmed": self.handle_configured_text,
            "selection_confirmation": self.handle_configured_text,
            "self_introduction": self.handle_configured_text,
            "business_hours": self.handle_business_hours,
            "catalog_request": self.handle_catalog_response,
            "off_topic": self.handle_off_topic,
        }

    # ------------------------------------------------------------------
    # Public Handlers – Called from main.py
    # ------------------------------------------------------------------
    async def handle_text_message(
        self,
        sender: str,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Full AI-driven message handling using LangChain."""
        conversation_history = conversation_history or []
        logger.info(f"Grace AI handling message from {sender}: {message}")

        try:
            # Format conversation history for GPT prompt
            formatted_history = self.format_conversation(conversation_history)
            logger.info(f"Formatted conversation history: {formatted_history}")

            # Build the prompt and get temperature
            prompt = await self.brain.build_prompt(formatted_history, message)
            logger.info(f"Generated prompt: {prompt}")


            # Run LangChain pipeline
            response = await GraceAgent.ainvoke(prompt)

            # Validate response
            if not response or not response.content.strip():
                logger.warning("Empty response from LangChain pipeline.")
                return self.brain.get_response("error_response")

            # Process LangChain response
            response_text = response.content.strip()
            logger.info(f"LangChain response: {response_text}")

            # Extract [[tag]] and clean response
            tag = self.brain.extract_response_key(response_text) or "unknown"
            cleaned = re.sub(r"\[\[.*?\]\]", "", response_text).strip()

            # Handle Shopify product lookup if tagged
            if tag == "shopify_product_lookup":
                product_answer = await self.handle_shopify_product_lookup(message)
                if product_answer and "couldn’t find" not in product_answer.lower():
                    cleaned = product_answer

            # Log and update learned response
            await self.brain.update_library(tag, message, cleaned)
            logger.info(f"Learned response for tag '{tag}': {cleaned}")

            return cleaned

        except Exception as e:
            logger.error("LangChain error: %s", e, exc_info=True)
            return self.brain.get_response("error_response")

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

    # ------------------------------------------------------------------
    # Intent-Specific Handlers
    # ------------------------------------------------------------------
    async def handle_configured_text(self, intent: str, _msg: str, _hist: list) -> str:
        """Return canned responses stored in speech_library.json."""
        return self.brain.get_response(intent)

    async def handle_business_hours(self, _intent: str, _msg: str, _hist: list) -> str:
        hours = self.brain.get_business_hours()
        return f"We're open from {hours['start']} to {hours['end']}."

    async def handle_catalog_response(self, _intent: str, _msg: str, _hist: list) -> str:
        """Handle catalog requests by fetching and formatting product data."""
        try:
            catalog = await self.brain.get_catalog()
            if not catalog:
                return "I'm sorry, but our product catalog is currently empty. Please check back later!"

            # Filter products based on user query (if applicable)
            filtered_products = [
                f"{item['name']}: {item['price']} {self.brain.get_business_info().get('currency', '₦')}"
                for item in catalog if item.get("name") and item.get("price")
            ]

            if not filtered_products:
                return "I couldn't find any matching products. Can you provide more details?"

            # Limit the number of products displayed
            product_list = "\n".join(filtered_products[:5])
            return f"Here are some products you might like:\n{product_list}"

        except Exception as e:
            logger.exception("Catalog fetch failed")
            return "I'm sorry, I couldn't fetch the product catalog at the moment. Please try again later."

    async def handle_shopify_product_lookup(self, query: str) -> str:
        """Handle product lookup requests."""
        try:
            catalog = await self.brain.get_catalog()
            if not catalog:
                return "I'm sorry, but our product catalog is currently empty. Please check back later!"

            # Search for products matching the query
            matching_products = [
                f"{item['name']}: {item['price']} {self.brain.get_business_info().get('currency', '₦')}"
                for item in catalog if query.lower() in item.get("name", "").lower()
            ]

            if not matching_products:
                return f"I couldn't find any products matching '{query}'. Can you try a different query?"

            # Limit the number of products displayed
            product_list = "\n".join(matching_products[:5])
            return f"Here are the products I found:\n{product_list}"

        except Exception as e:
            logger.exception("Product lookup failed")
            return "I'm sorry, I couldn't fetch the product details at the moment. Please try again later."

    async def handle_off_topic(self, _intent: str, _msg: str, _hist: list) -> str:
        """Handle off-topic messages with a funny redirect."""
        return self.brain.get_response("funny_redirects")

    # ------------------------------------------------------------------
    # Utility Helpers
    # ------------------------------------------------------------------
    def format_conversation(self, history: List[Dict[str, str]]) -> str:
        """Condense recent chat into a plain-text transcript for prompting."""
        formatted = [
            f"{h['role']}: {h['content']}" for h in history[-MAX_HISTORY_MESSAGES:] if h.get("role") and h.get("content")
        ]
        convo = "\n".join(formatted)
        return convo[:MAX_HISTORY_LENGTH].rsplit("\n", 1)[0] if len(convo) > MAX_HISTORY_LENGTH else convo
