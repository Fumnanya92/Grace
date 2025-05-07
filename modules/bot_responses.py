# modules/bot_responses.py

import re
import os
import time
import logging
import asyncio
from typing import List, Dict
from urllib.parse import urlparse, urlunparse

from openai import AsyncOpenAI
from config import config
from logging_config import configure_logger

from modules.grace_brain import GraceBrain
from modules.utils import normalize_message, detect_picture_request
from modules.image_processing_module import ImageProcessor
from modules.s3_service import S3Service
from modules.intent_recognition_module import recognize_intent

logger = configure_logger("bot_responses")

# Constants
MAX_IMAGES = 10
MAX_HISTORY_LENGTH = 1000
MAX_HISTORY_MESSAGES = 6
REQUEST_TIMEOUT = 15

image_processor = ImageProcessor(S3Service())
image_history = {}  # Temporary: consider tenant-specific DB storage

class BotResponses:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.brain = GraceBrain(tenant_id)
        self.gpt_client = AsyncOpenAI(timeout=REQUEST_TIMEOUT)

    async def handle_text_message(self, sender: str, message: str, conversation_history: list) -> str:
        logger.info(f"[{self.tenant_id}] Handling message from {sender}: {message}")
        try:
            message = normalize_message(message)

            if await detect_picture_request(message):
                return await self.fetch_images_and_respond()

            intents = recognize_intent(message)
            for intent in intents:
                response = await self.brain.get_response_by_intent(intent)
                if response:
                    return response

            return await self.generate_fallback_response(conversation_history, message)

        except Exception as e:
            logger.error(f"[{self.tenant_id}] Text message handling error: {e}", exc_info=True)
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
        return await self.brain.get_response("unsupported_media")

    async def fetch_images_and_respond(self) -> str:
        try:
            catalog = await self.brain.get_catalog()
            if not catalog:
                return await self.brain.get_response("image_not_found")

            response_lines = [await self.brain.get_response("image_instructions")]
            for item in catalog[:MAX_IMAGES]:
                url = urlunparse(urlparse(item["url"])._replace(query=""))
                response_lines.append(f"{item['name']}: {url}")
            return "\n".join(response_lines)

        except Exception as e:
            logger.error(f"[{self.tenant_id}] Catalog fetch failed: {e}", exc_info=True)
            return await self.brain.get_response("image_not_found")

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
            return await self.brain.get_response("error_response")

    def format_conversation(self, history: List[Dict[str, str]]) -> str:
        formatted = [
            f"{entry['role']}: {entry['content']}"
            for entry in history[-MAX_HISTORY_MESSAGES:]
            if "role" in entry and "content" in entry
        ]
        conversation = "\n".join(formatted)
        return conversation[:MAX_HISTORY_LENGTH].rsplit("\n", 1)[0] if len(conversation) > MAX_HISTORY_LENGTH else conversation
