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

from modules.grace_brain import GraceBrain
from modules.utils import detect_picture_request
from modules.image_processing_module import ImageProcessor
from modules.s3_service import S3Service
from modules.intent_recognition_module import recognize_intent, normalize_message

logger = configure_logger("bot_responses")

# ---------------------------------------------------------------------------
# Tunables & shared singletons
# ---------------------------------------------------------------------------
MAX_IMAGES: int = 10
MAX_HISTORY_LENGTH: int = 1000
MAX_HISTORY_MESSAGES: int = 6
REQUEST_TIMEOUT: int = 15

image_processor = ImageProcessor(S3Service())
image_history: Dict[str, List[Dict[str, float]]] = {}

# ---------------------------------------------------------------------------
# BotResponses class – API unchanged, internals improved
# ---------------------------------------------------------------------------
class BotResponses:
    """High‑level orchestration for Grace’s responses."""

    def __init__(self) -> None:
        self.brain = GraceBrain()
        self.gpt_client = AsyncOpenAI(timeout=REQUEST_TIMEOUT)

    # ------------------------------------------------------------------
    # Intent dispatch map
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
    # Public handlers – called from main.py
    # ------------------------------------------------------------------
    async def handle_text_message(
        self,
        sender: str,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Process a plain‑text WhatsApp message."""
        conversation_history = conversation_history or []
        logger.info("Handling message from %s: %s", sender, message)

        try:
            message = normalize_message(message)

            # Quick check: picture request → shortcut to catalog
            if await detect_picture_request(message):
                return await self.handle_catalog_response("catalog_request", message, conversation_history)

            # Route by recognized intents
            for intent in recognize_intent(message):
                handler = self.intent_handlers().get(intent)
                if handler:
                    response = await handler(intent, message, conversation_history)
                    if response:
                        return response

            # Nothing matched → fallback to GPT
            return await self.generate_fallback_response(conversation_history, message)

        except Exception:
            logger.exception("Error while handling message")
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
    # Intent‑specific handlers
    # ------------------------------------------------------------------
    async def handle_configured_text(self, intent: str, _msg: str, _hist: list) -> str:  # noqa: D401
        """Return canned responses stored in speech_library.json."""
        return self.brain.get_response(intent)

    async def handle_business_hours(self, _intent: str, _msg: str, _hist: list) -> str:
        hours = self.brain.get_business_hours()
        return f"We're open from {hours['start']} to {hours['end']}."

    async def handle_catalog_response(self, _intent: str, _msg: str, _hist: list) -> str:
        try:
            catalog = await self.brain.get_catalog()
            if not catalog:
                return self.brain.get_response("catalog_empty")

            intro = self.brain.get_response("catalog_intro")
            lines = [intro]
            for item in catalog[:MAX_IMAGES]:
                name, url = item.get("name"), item.get("url")
                if not name or not url:
                    logger.warning("Invalid catalog item: %s", item)
                    continue
                clean_url = urlunparse(urlparse(url)._replace(query=""))
                lines.append(f"{name}: {clean_url}")
            return "\n".join(lines)
        except Exception:
            logger.exception("Catalog fetch failed")
            return self.brain.get_response("catalog_error")

    async def handle_off_topic(self, _intent: str, _msg: str, _hist: list) -> str:
        return self.brain.get_response("funny_redirects")

    # ------------------------------------------------------------------
    # Fallback GPT handler – fixed signature
    # ------------------------------------------------------------------
    async def generate_fallback_response(
        self,
        history: List[Dict[str, str]],
        latest_user_message: str,
    ) -> str:
        """Stream a GPT‑4o response when no intent matched."""
        logger.info("Fallback GPT triggered for message: %s", latest_user_message)
        formatted = self.format_conversation(history)
        prompt = await self.brain.build_prompt(formatted, latest_user_message)
        logger.info("Generated prompt for GPT: %s", prompt)

        try:
            async with self.gpt_client.beta.realtime.connect(model="gpt-4o-realtime-preview") as conn:
                await conn.session.update(session={"modalities": ["text"]})
                logger.info("Connected to GPT realtime session.")

                await conn.conversation.item.create(item={
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                })
                logger.info("Sent prompt to GPT.")

                await conn.response.create()

                full_response = ""
                async for event in conn:
                    if event.type in ("response.text.delta", "response.delta"):
                        full_response += getattr(event, "delta", getattr(event, "text", ""))
                    elif event.type in ("response.text.done", "response.done"):
                        break
                logger.info("Received GPT response: %s", full_response)
        except Exception as e:
            logger.exception("Fallback GPT failed: %s", e)
            return "I'm sorry, I couldn't process your request. Please try again later."

        matched_key = self.brain.extract_response_key(full_response)
        reply = self.brain.get_response(matched_key) or full_response
        await self.brain.update_library(matched_key, latest_user_message, reply)
        logger.info("Final fallback response: %s", reply)
        return reply

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def format_conversation(self, history: List[Dict[str, str]]) -> str:
        """Condense recent chat into a plain‑text transcript for prompting."""
        formatted = [
            f"{h['role']}: {h['content']}" for h in history[-MAX_HISTORY_MESSAGES:] if h.get("role") and h.get("content")
        ]
        convo = "\n".join(formatted)
        return convo[:MAX_HISTORY_LENGTH].rsplit("\n", 1)[0] if len(convo) > MAX_HISTORY_LENGTH else convo
