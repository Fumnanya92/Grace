import re
import os
import time
import logging
import asyncio
from typing import List, Dict, Callable
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

MAX_IMAGES = 10
MAX_HISTORY_LENGTH = 1000
MAX_HISTORY_MESSAGES = 6
REQUEST_TIMEOUT = 15

image_processor = ImageProcessor(S3Service())
image_history = {}

class BotResponses:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.brain = GraceBrain(tenant_id)
        self.gpt_client = AsyncOpenAI(timeout=REQUEST_TIMEOUT)

    def intent_handlers(self) -> Dict[str, Callable]:
        return {
            "greetings": self.handle_configured_text,
            "package_details": self.handle_configured_text,
            "deposit_instructions": self.handle_configured_text,
            "payment_confirmed": self.handle_configured_text,
            "selection_confirmation": self.handle_configured_text,
            "self_introduction": self.handle_configured_text,
            "business_hours": self.handle_business_hours,
            "catalog_request": self.handle_catalog_response,
            "off_topic": self.handle_off_topic
        }

    async def handle_text_message(self, sender: str, message: str, conversation_history: list) -> str:
        logger.info(f"[{self.tenant_id}] Handling message from {sender}: {message}")
        try:
            message = normalize_message(message)

            if await detect_picture_request(message):
                return await self.handle_catalog_response("catalog_request", message, conversation_history)

            intents = recognize_intent(message)
            handlers = self.intent_handlers()

            for intent in intents:
                handler = handlers.get(intent)
                if handler:
                    response = await handler(intent, message, conversation_history)
                    if response:
                        return response
            return await self.generate_fallback_response(conversation_history, message)

        except Exception as e:
            logger.error(f"[{self.tenant_id}] Error handling message: {e}", exc_info=True)
            return await self.brain.get_response("error_response")

    async def handle_media_message(self, sender: str, media_url: str, media_type: str) -> str:
        logger.info(f"[{self.tenant_id}] Received media from {sender}")
        if media_type.startswith("image/"):
            try:
                image_history.setdefault(sender, []).append({
                    "url": media_url,
                    "timestamp": time.time()
                })
                return await image_processor.handle_image(sender, media_url)
            except Exception as e:
                logger.error(f"[{self.tenant_id}] Image processing error: {e}", exc_info=True)
                return await self.brain.get_response("image_error")
        if media_type.startswith("video/"):
            return "Thank you for sending a video. We'll review it shortly."
        elif media_type.startswith("application/"):
            return "Thank you for sending a document. We'll review it shortly."
        return await self.brain.get_response("unsupported_media")

    async def handle_configured_text(self, intent: str, message: str, history: list) -> str:
        return await self.brain.get_response(intent)

    async def handle_business_hours(self, intent: str, message: str, history: list) -> str:
        hours = self.brain.get_business_hours()
        return f"We're open from {hours['start']} to {hours['end']}."

    async def handle_catalog_response(self, intent: str, message: str, history: list) -> str:
        try:
            catalog = await self.brain.get_catalog()
            if not catalog:
                return await self.brain.get_response("catalog_empty")

            lines = [await self.brain.get_response("catalog_intro")]
            for item in catalog[:MAX_IMAGES]:
                if "name" not in item or "url" not in item:
                    logger.warning(f"Invalid catalog item: {item}")
                    continue
                clean_url = urlunparse(urlparse(item["url"])._replace(query=""))
                lines.append(f"{item['name']}: {clean_url}")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"[{self.tenant_id}] Catalog fetch failed: {e}", exc_info=True)
            return await self.brain.get_response("catalog_error")

    async def handle_off_topic(self, intent: str, message: str, history: list) -> str:
        return await self.brain.get_response("funny_redirects")

    async def generate_fallback_response(self, history: List[Dict[str, str]], latest_user_message: str) -> str:
        try:
            formatted = self.format_conversation(history)
            prompt = await self.brain.build_prompt(formatted, latest_user_message)

            async with self.gpt_client.beta.realtime.connect(model="gpt-4o-realtime-preview") as conn:
                await conn.session.update(session={"modalities": ["text"]})
                await conn.conversation.item.create({
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}]
                })
                await conn.response.create()

                full_response = ""
                async for event in conn:
                    if event.type == "response.text.delta":
                        full_response += event.delta
                    elif event.type == "response.text.done":
                        break

            matched_key = self.brain.extract_response_key(full_response)
            reply = await self.brain.get_response(matched_key)
            if not reply:
                reply = full_response
            await self.brain.update_library(matched_key, latest_user_message, reply)
            return reply

        except Exception as e:
            logger.error(f"[{self.tenant_id}] Fallback GPT response failed: {e}", exc_info=True)
            return "I'm sorry, I couldn't process your request. Please try again later."

    def format_conversation(self, history: List[Dict[str, str]]) -> str:
        formatted = [
            f"{entry['role']}: {entry['content']}"
            for entry in history[-MAX_HISTORY_MESSAGES:]
            if "role" in entry and "content" in entry
        ]
        conversation = "\n".join(formatted)
        return conversation[:MAX_HISTORY_LENGTH].rsplit("\n", 1)[0] if len(conversation) > MAX_HISTORY_LENGTH else conversation
