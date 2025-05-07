import re
from urllib.parse import urlparse, urlunparse
import os  # Add this import to handle file extensions

from cv2 import line
from modules.grace_brain import GraceBrain  # Import the GraceBrain class
from typing import List, Dict
import logging
import time
import openai
from openai import AsyncOpenAI
from config import config
from logging_config import configure_logger
import asyncio
from modules.utils import cached_list_images, detect_picture_request, load_speech_library, save_speech_library, update_speech_library  # Import from utils.py
from modules.image_processing_module import ImageProcessor
from modules.s3_service import S3Service
from modules.intent_recognition_module import recognize_intent, normalize_message

# Setting up logging
logger = configure_logger("bot_responses")
logger.info("Bot responses module loaded.")

# Configuration constants
MAX_HISTORY_LENGTH = 1000  # characters
MAX_HISTORY_MESSAGES = 6
REQUEST_TIMEOUT = 15  # seconds
MAX_IMAGES = 10

# Initialize the image processor
image_processor = ImageProcessor(S3Service())  # Ensure image_processor is initialized with S3 service

# Global dictionary to store image history (use a database for production)
image_history = {}

class BotResponses:
    """Class for generating bot responses based on user input and intent."""
    
    AI_PHRASES_PATTERN = re.compile(r"|".join(map(re.escape, [
        "as a language model", "openai", "AI assistant", "I'm an AI", 
        "I’m a chatbot", "I am not a human", "I was trained", "I cannot", 
        "I am not capable"
    ])))

    def __init__(self):
        self.grace_brain = GraceBrain()  # Create an instance of GraceBrain
        self.gpt_client = AsyncOpenAI(timeout=REQUEST_TIMEOUT)  # Initialize GPT client
        logger.info("BotResponses instance initialized.")  # Log initialization

    async def get_response(self, keys: List[str], **kwargs) -> str:
        """Return a formatted response based on the keys."""
        if not keys:
            logger.warning("No keys provided for response generation.")
            return "Oops! No response keys provided."

        logger.debug(f"Generating response for keys: {keys} with kwargs: {kwargs}")
        response_tasks = [self.grace_brain.get_response(key, **kwargs) for key in keys]
        responses = await asyncio.gather(*response_tasks)
        logger.info(f"Generated responses for keys: {keys}")
        return "\n\n".join(responses)

    async def handle_media_message(self, sender: str, media_url: str, media_type: str) -> str:
        """
        Handle media (image) messages.
        """
        logger.info(f"Handling media message from {sender} with media type: {media_type}")
        if media_type and media_type.startswith("image/"):
            try:
                # Log the image in the history
                if sender not in image_history:
                    image_history[sender] = []
                image_history[sender].append({"url": media_url, "timestamp": time.time()})
                logger.info(f"Logged image for {sender}: {urlparse(media_url)._replace(query='').geturl()}")

                # Process the image
                response = await image_processor.handle_image(sender, media_url)
                logger.info(f"Successfully processed image for {sender}")
                return response
            except Exception as e:
                logger.error(f"Error processing image for {sender}: {e}", exc_info=True)
                return "Sorry, I encountered an issue while processing the image. Please try again later."
        logger.warning(f"Unsupported media type from {sender}: {media_type}")
        return "Sorry, I can only process image files. Please send an image."
    
    
    def check_image_history(sender: str) -> str:
        """
        Check if the sender has sent any images previously.
        """
        if sender in image_history and image_history[sender]:
            response_lines = ["Yes, I have received the following images from you:"]
            for record in image_history[sender]:
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(record["timestamp"]))
                response_lines.append(f"- {record['url']} (Received on {timestamp})")
            return "\n".join(response_lines)
        return "No, I haven't received any images from you yet."

    async def handle_text_message(self, sender: str, message: str, conversation_history: list) -> str:
        """
        Handle text messages, including detecting picture requests and product inquiries.
        """
        logger.info(f"Handling text message from {sender}: {message}")
        try:
            # Ensure message is a string
            message = normalize_message(message)

            # Check if the user is asking about image history
            if "did i send" in message.lower() or "have you received" in message.lower():
                logger.info(f"Image history query detected from {sender}")
                return self.check_image_history(sender)

            # Handle the picture request first
            if await detect_picture_request(message):
                logger.info(f"Picture request detected in message from {sender}")
                return await self.fetch_images_and_respond()

            # Recognize intents
            intents = recognize_intent(message)  # `recognize_intent` is synchronous
            logger.debug(f"Recognized intents for {sender}: {intents}")

            # Process intents and get bot reply
            bot_reply = await self.process_intents(intents, message, conversation_history)

            # Fallback to Grace's general response if no intent matched
            if not bot_reply:
                logger.info(f"No specific intent matched for {sender}. Generating general response.")
                bot_reply = await self.generate_grace_response(conversation_history, message)
                logger.debug(f"Fallback response: {bot_reply}")

            return bot_reply

        except Exception as e:
            logger.error(f"Unexpected error for sender {sender}: {e}", exc_info=True)
            return "Sorry, something went wrong. Please try again later."

    async def process_intents(self, intents: List[str], message: str, conversation_history: list) -> str:
        """Process recognized intents using a dynamic handler registry."""
        intent_handlers = {
            "greetings": self.handle_greeting,
            "ask_for_designs": self.handle_product_inquiry,
            "deposit_instructions": self.handle_payment_details,
            "payment_confirmed": self.handle_payment_confirmation,
            "selection_confirmation": self.handle_order_confirmation,
            "self_introduction": self.handle_off_topic,
            "image_request": self.handle_product_inquiry,
            "package_details": self.handle_package_details,
            "off_topic": self.handle_off_topic,
            "default_response": self.handle_default_response,  # Map to the new method
        }

        for intent in intents:
            handler = intent_handlers.get(intent)
            if handler:
                response = await handler(message, conversation_history)
                if response:
                    return response

        # Return None if no handler produced a response
        return None

    # Individual intent handlers
    async def handle_greeting(self, message: str, conversation_history: list) -> str:
        """Handle greeting intent."""
        return await self.grace_brain.get_response("greetings")

    async def handle_payment_details(self, message: str, conversation_history: list) -> str:
        """Handle intent for providing payment details."""
        return await self.grace_brain.get_response("deposit_instructions")

    async def handle_payment_confirmation(self, message: str, conversation_history: list) -> str:
        """Handle intent for confirming payment."""
        return await self.grace_brain.get_response("payment_confirmed")

    async def handle_product_inquiry(self, message: str, conversation_history: list) -> str:
        """Handle product inquiry intent."""
        images = await cached_list_images()
        if not images:
            return await self.grace_brain.get_response("image_not_found")
        response_lines = [await self.grace_brain.get_response("image_instructions")]
        for image in images[:MAX_IMAGES]:
            if "url" not in image or "name" not in image:
                logger.warning(f"Invalid image data: {image}")
                continue
            line.append(f"{image['name']}: {image['url']}")
        return "\n".join(response_lines)

    async def handle_order_confirmation(self, message: str, conversation_history: list) -> str:
        """Handle order confirmation intent."""
        return await self.grace_brain.get_response("selection_confirmation")

    async def handle_off_topic(self, message: str, conversation_history: list) -> str:
        """Handle off-topic intent."""
        return await self.grace_brain.get_response("funny_redirects")

    async def handle_package_details(self, message: str, conversation_history: list) -> str:
        """Handle package details intent."""
        return await self.grace_brain.get_response("package_details")

    async def handle_default_response(self, message: str, conversation_history: list) -> str:
        """Handle default response intent."""
        return await self.grace_brain.get_response("default_response")

    async def fetch_images_and_respond(self) -> str:
        """Return a formatted text string of product images with their names."""
        try:
            images = await cached_list_images()
            if not images:
                logger.warning("No images found in the catalog.")
                return "Sorry, I couldn't find any images in the catalog."

            # Log the fetched image URLs and names
            logger.info(f"Fetched {len(images)} images from the catalog.")
            for image in images:
                if "url" in image and "name" in image:
                    logger.debug(f"Image Name: {image['name']}, URL: {image['url']}")

            # Prepare the response with sanitized image URLs and names
            lines = ["Here are some of our best-selling designs:"]
            for image in images[:MAX_IMAGES]:
                if "url" not in image or "name" not in image:
                    logger.warning(f"Invalid image data: {image}")
                    continue

                # Sanitize the URL by removing query parameters
                parsed_url = urlparse(image["url"])
                sanitized_url = urlunparse(parsed_url._replace(query=""))
                lines.append(f"{image['name']}: {sanitized_url}")

            response = "\n".join(lines)
            logger.info("Prepared response with sanitized image URLs and names.")
            return response

        except Exception as e:
            logger.error(f"Error fetching images: {e}", exc_info=True)
            return "Sorry, I encountered an error while fetching designs. Please try again later."

    async def generate_grace_response(self, history: List[Dict[str, str]], latest_user_message: str) -> str:
        """
        Generate a response for Grace using the speech library or OpenAI's GPT model.
        """
        logger.debug(f"Generating response for user message: {latest_user_message}")
        start_time = time.time()

        try:
            # Load the speech library
            library = load_speech_library()

            # Check if the user message matches any phrase in the library
            for entry in library.get("training_data", []):
                if entry["phrase"].lower() == latest_user_message.lower():
                    logger.info(f"Matched user message with library entry: {entry}")
                    return entry["response"]

            # If no match is found, proceed with GPT-based response generation
            formatted_history = self.format_conversation(history)
            user_content = f"{formatted_history}\n\nUser: {latest_user_message}"

            # Define the prompt to guide the AI
            prompt = (
                "You are Grace, a helpful assistant for wholesale inquiries. Respond to the user's query and include a response key "
                "from the following list: [[greetings]], [[ask_for_designs]], [[package_details]], [[deposit_instructions]], "
                "[[funny_redirects]], [[self_introduction]]. If the user says anything off-topic (like trivia, jokes, politics, relationships), respond "
                "with [[funny_redirects]] and redirect to wholesale. NEVER invent your own keys. ONLY use one key per message."
            )

            # Combine the prompt with the user content
            full_prompt = f"{prompt}\n\n{user_content}"

            # Connect to GPT-4o and generate response asynchronously
            async with self.gpt_client.beta.realtime.connect(model="gpt-4o-realtime-preview") as connection:
                logger.info("Connected to GPT-4o model for response generation.")
                await connection.session.update(session={"modalities": ["text"]})
                await connection.conversation.item.create(
                    item={"type": "message", "role": "user", "content": [{"type": "input_text", "text": full_prompt}]}
                )
                await connection.response.create()

                full_response = ""
                async for event in connection:
                    if event.type == "response.text.delta":
                        full_response += event.delta
                    elif event.type == "response.text.done":
                        break

            logger.debug(f"Raw AI output: {full_response}")
            matched_key = self.extract_response_key(full_response)
            bot_response = await self.grace_brain.get_response(matched_key)

            # Validate matched_key and bot_response
            if not matched_key or not bot_response:
                logger.warning(f"No canned response for key '{matched_key}'. Using AI-authored response.")
                matched_key = "default_response"
                bot_response = full_response

            # Calculate confidence score
            confidence = self.calculate_confidence(full_response)

            # Update the speech library with confidence
            update_speech_library(matched_key, latest_user_message, bot_response, confidence)

            cleaned_response = await self.clean_response(bot_response)
            logger.info(f"Cleaned response: {cleaned_response}")
            return cleaned_response

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return await self.grace_brain.get_response("error_response")

    def format_conversation(self, history: List[Dict[str, str]]) -> str:
        """Format the conversation history into a string."""
        safe_history = []
        for msg in history[-MAX_HISTORY_MESSAGES:]:
            if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                safe_history.append(f"{msg['role']}: {msg['content']}")
        conversation = "\n".join(safe_history)
        if len(conversation) > MAX_HISTORY_LENGTH:
            conversation = conversation[:MAX_HISTORY_LENGTH].rsplit("\n", 1)[0]  # Truncate at the last full message
        return conversation.strip()

    def extract_response_key(self, ai_output: str) -> str:
        """Extract and validate the response key from AI output."""
        match = re.search(r"\[\[(.*?)\]\]", ai_output)
        if not match:
            logger.warning(f"No key found in AI output: {ai_output}")
            # Infer the most suitable key based on predefined intents
            inferred_key = self.infer_intent_from_response(ai_output)
            logger.info(f"Inferred key: {inferred_key}")
            return inferred_key
        key = match.group(1)
        VALID_KEYS = ["greetings", "ask_for_designs", "package_details", "deposit_instructions", "funny_redirects", "self_introduction"]

        if key not in VALID_KEYS:
            logger.warning(f"Unrecognized key extracted: {key}")
            return "default_response"
        return key

    async def clean_response(self, response: str) -> str:
        """Clean the AI response of unwanted phrases (like AI references)."""
        cleaned_response = self.AI_PHRASES_PATTERN.sub("", response).strip()
        if not cleaned_response:
            logger.warning("Response became empty after cleaning. Returning a fallback response.")
            return "I'm here to assist you with your inquiries."
        logger.debug(f"Original response: {response}")
        logger.debug(f"Cleaned response: {cleaned_response}")
        return cleaned_response

    def calculate_confidence(self, gpt_response: str) -> float:
        """Calculate a confidence score for the GPT response."""
        if not gpt_response:
            return 0.0
        if "[[" in gpt_response and "]]" in gpt_response:
            return 1.0  # High confidence if a valid key is present
        return 0.5  # Medium confidence otherwise

    def infer_intent_from_response(self, response: str) -> str:
        """Infer the most suitable intent key based on the AI's response content."""
        response = response.lower()
        predefined_intents = {
                "greetings": ["hello", "hi", "good morning", "good afternoon", "good evening", "greetings", "welcome"],
                "ask_for_designs": ["design", "catalog", "style", "print", "choose", "pick", "collection", "send screenshot"],
                "package_details": ["package", "offer", "deal", "wholesale", "what's included", "content", "benefit", "premium"],
                "deposit_instructions": ["payment", "pay", "bank", "transfer", "account number", "how do i pay", "how much"],
                "payment_confirmed": ["confirmed", "i paid", "i've sent", "payment made", "transfer done", "check payment"],
                "selection_confirmation": ["i choose", "selected", "my designs are", "confirm order", "i picked"],
                "funny_redirects": ["joke", "trivia", "politics", "relationship", "random", "fact", "love", "celebrity", "useless"],
                "self_introduction": ["your name", "who are you", "what's your name", "are you a person", "tell me about yourself"],
            }
        for key, keywords in predefined_intents.items():
            if any(keyword in response.lower() for keyword in keywords):
                logger.debug(f"Keyword match found for key '{key}' in response: '{response}'")
                return key

            logger.debug(f"No keyword match found in response: '{response}'. Defaulting to 'default_response'")
            return None

    async def send_images_as_media(self, sender: str):
        """Send images as media messages to the user."""
        try:
            # Fetch the images from the catalog
            images = await cached_list_images()
            if not images:
                logger.warning("No images found in the catalog.")
                return await self.send_message(sender, "Sorry, I couldn't find any images in the catalog.")

            # Send each image as a media message
            for image in images[:MAX_IMAGES]:  # Limit the number of images sent
                if "url" not in image or "name" not in image:
                    logger.warning(f"Invalid image data: {image}")
                    continue

                # Remove the file extension from the image name
                image_name = os.path.splitext(image["name"])[0]

                # Send the image as a media message
                await self.send_media_message(
                    sender=sender,
                    media_url=image["url"],
                    caption=image_name  # Use the name without the file extension
                )

            logger.info(f"Sent {len(images[:MAX_IMAGES])} images to {sender}.")
        except Exception as e:
            logger.error(f"Error sending images as media: {e}", exc_info=True)
            await self.send_message(sender, "Sorry, I encountered an error while sending the images. Please try again later.")

    async def send_media_message(self, sender: str, media_url: str, caption: str):
        """Send a media message to the user."""
        try:
            # Use your messaging API (e.g., Twilio) to send the media message
            await self.messaging_client.send_media(
                to=sender,
                media_url=media_url,
                caption=caption
            )
            logger.info(f"Media message sent to {sender}: {media_url}")
        except Exception as e:
            logger.error(f"Failed to send media message to {sender}: {e}", exc_info=True)

