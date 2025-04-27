from flask import Flask, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse
from pyngrok import ngrok, conf
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from init_db import init_db
import atexit
import json
from functools import lru_cache
from threading import Timer
import signal
import sys

# Import modules
from modules.payment_module import PaymentHandler
from modules.user_memory_module import UserMemory, build_conversation_history
from modules.s3_service import S3Service
from modules.image_processing_module import ImageProcessor
from modules.bot_responses import ResponseTemplates, get_dynamic_response
from config import config
from logging_config import configure_logger

# Configure logger for this module
logger = configure_logger("main")

logger.info("Main module initialized.")

def detect_picture_request(message: str) -> bool:
    """Detect if the user is asking to see pictures or designs."""
    triggers = [
        "send pictures", "send me pictures", "see designs", "show me", 
        "catalog", "available designs", "pictures of dresses", "dress pictures",
        "send designs", "send catalog", "show dresses", "pictures available"
    ]
    message = message.lower()
    return any(trigger in message for trigger in triggers)

# Accessing payment details
account_number = config.PAYMENT_DETAILS['account_number']

# AWS S3 configuration
s3_bucket = config.AWS['bucket']

# Checking debug mode
if config.APP['debug']:
    print("Running in debug mode")

# Initialize Flask app
app = Flask(__name__)

# Load configuration
load_dotenv()
conf.get_default().auth_token = os.getenv("NGROK_AUTH_TOKEN")

# Initialize services
responses = ResponseTemplates()
payment_handler = PaymentHandler()

# Initialize S3Service
s3_service = S3Service()

# Pass S3Service to ImageProcessor
image_processor = ImageProcessor(s3_service)

@lru_cache(maxsize=1)
def cached_list_images():
    return s3_service.list_images()

@app.route("/webhook", methods=["POST"])
def handle_webhook():
    """Main entry point for WhatsApp messages"""
    twilio_resp = MessagingResponse()
    sender = request.values.get("From", "")
    message = request.values.get("Body", "").strip()
    media_url = request.values.get("MediaUrl0")
    media_type = request.values.get("MediaContentType0")  # Get the media content type
    conversation_history = build_conversation_history(sender)

    logger.debug(f"Conversation history for {sender}: {conversation_history}")
    logger.debug(f"Incoming message: {message[:100]}{'...' if len(message) > 100 else ''}")
    logger.debug(f"Media URL: {media_url[:100]}{'...' if media_url and len(media_url) > 100 else ''}" if media_url else "Media URL: None")

    try:
        user = UserMemory(sender)

        # Handle media messages
        if media_url:
            if media_type and media_type.startswith("image/"):  # Check if the media type is an image
                bot_reply = image_processor.handle_image(sender, media_url)
            else:
                bot_reply = "Sorry, I can only process image files. Please send an image."
            twilio_resp.message(bot_reply)
            log_chat(sender, message, bot_reply)
            return str(twilio_resp)

        # Handle text messages
        if detect_picture_request(message):
            # Retrieve all images from S3
            images = cached_list_images()
            if not images:
                bot_reply = "Sorry, I couldn't find any images in the catalog."
                twilio_resp.message(bot_reply)
                log_chat(sender, message, bot_reply)
                return str(twilio_resp)

            bot_reply = "Here are some of our best-selling designs!"
            twilio_resp.message(bot_reply)

            # Attach each image to the response
            for image in images:
                if "url" in image:
                    twilio_resp.message().media(image["url"])

            log_chat(sender, message, bot_reply)
            return str(twilio_resp)

        if message:
            # Process the text message and generate a response
            bot_reply = get_dynamic_response(message, conversation_history)
            twilio_resp.message(bot_reply)
            log_chat(sender, message, bot_reply)
            return str(twilio_resp)

        # If no message or media is provided
        bot_reply = "Please send a message or an image."
        twilio_resp.message(bot_reply)
        log_chat(sender, "", bot_reply)
        return str(twilio_resp)

    except Exception as e:
        logger.error(f"Unexpected error for sender {sender}: {e}")
        bot_reply = "Sorry, something went wrong. Please try again later."
        twilio_resp.message(bot_reply)
        log_chat(sender, message, bot_reply)
        return str(twilio_resp)

@app.route("/verify-payment", methods=["POST"])
def verify_payment():
    """Endpoint for payment verification"""
    try:
        data = request.get_json()
        logger.debug(f"Received payment verification request: {data}")
        if not data or 'code' not in data:
            return jsonify({"status": "error", "message": "Missing verification code"}), 400

        result = payment_handler.verify_payment(data['code'])
        if result['status'] == "success":
            logger.info(f"Payment verification successful for code: {data['code']}")
            return jsonify(result), 200
        return jsonify(result), 404

    except Exception as e:
        logger.error(f"Payment verification error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/health", methods=["GET"])
def health_check():
    database_status = UserMemory.check_connection()
    s3_status = s3_service.check_connection()

    logger.info(f"Health check - Database: {'connected' if database_status else 'disconnected'}, S3: {'connected' if s3_status else 'disconnected'}")

    return jsonify({
        "status": "active",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "database": "connected" if database_status else "disconnected",
            "s3": "connected" if s3_status else "disconnected"
        }
    })

def log_chat(sender: str, user_msg: str, bot_reply: str) -> None:
    """Log conversation with enhanced structure."""
    clean_sender = sender.replace("whatsapp:", "")
    log_file = f"logs/{clean_sender}_chat_history.json"
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "sender": clean_sender,
        "user_message": user_msg,
        "bot_reply": bot_reply
    }

    try:
        if os.path.exists(log_file):
            with open(log_file, "r+", encoding="utf-8") as file:
                try:
                    data = json.load(file)
                except json.JSONDecodeError:
                    logger.warning(f"Corrupted log file for {clean_sender}. Overwriting...")
                    data = []
                data.append(log_entry)
                file.seek(0)
                json.dump(data, file, indent=2)
        else:
            with open(log_file, "w", encoding="utf-8") as file:
                json.dump([log_entry], file, indent=2)
                
        logging.info(f"Logged message for {clean_sender}")
    except Exception as e:
     logging.error(f"Error logging chat for {clean_sender}: {e}")

def refresh_cached_images():
    cached_list_images.cache_clear()
    cached_list_images()
    Timer(300, refresh_cached_images).start()  # Refresh every 5 minutes

refresh_cached_images()

def cleanup():
    logging.info("Gracefully shutting down Grace.")
    ngrok.kill()

atexit.register(cleanup)

# Handle SIGINT (Ctrl+C) gracefully
def handle_sigint(signal, frame):
    logging.info("SIGINT received. Exiting gracefully...")
    try:
        os._exit(0)  # Force exit without triggering threading shutdown noise
    except SystemExit:
        pass

signal.signal(signal.SIGINT, handle_sigint)

if __name__ == "__main__":
    init_db()
    public_url = ngrok.connect(5000).public_url
    logger.info(f"Ngrok public URL: {public_url}")
    
    print(f"\n{'='*50}")
    print(f"Server running at: {public_url}")
    print(f"Twilio Webhook URL: {public_url}/webhook")
    print(f"{'='*50}\n")
    
    app.run(port=5000)