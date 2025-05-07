from fastapi import FastAPI, Request, HTTPException, status, Form, Response
from twilio.twiml.messaging_response import MessagingResponse
from pyngrok import ngrok, conf
import os
import logging
from datetime import datetime
import uvicorn
import aiofiles
from dotenv import load_dotenv
from init_db import init_db
import json
from functools import lru_cache
import asyncio
from modules.payment_module import PaymentHandler
from modules.user_memory_module import UserMemory, build_conversation_history
from modules.s3_service import S3Service
from modules.image_processing_module import ImageProcessor
from config import config
from logging_config import configure_logger
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional
from modules.utils import detect_picture_request, cached_list_images  # Import from utils.py
from modules.bot_responses import BotResponses  # Import the BotResponses class

# Configure logger for this module
logger = configure_logger("main")
logger.info("Main module initialized.")

# Create an instance of BotResponses
responses = BotResponses()

load_dotenv()
conf.get_default().auth_token = os.getenv("NGROK_AUTH_TOKEN")

# Accessing payment details
account_number = config.PAYMENT_DETAILS['account_number']

# AWS S3 configuration
s3_bucket = config.AWS['bucket']

# Checking debug mode
if config.APP['debug']:
    print("Running in debug mode")
    logger.info("Debug mode enabled")

# Initialize services
payment_handler = PaymentHandler()
s3_service = S3Service()
image_processor = ImageProcessor(s3_service)

# Pydantic models
class PaymentVerification(BaseModel):
    code: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan management for FastAPI app"""
    # Startup
    await startup()
    yield
    # Shutdown
    await shutdown()

app = FastAPI(lifespan=lifespan)

# Ngrok management
async def start_ngrok():
    try:
        public_url = ngrok.connect(8000).public_url
        logger.info(f"Ngrok public URL: {public_url}")
        print(f"\n{'='*50}")
        print(f"Server running at: {public_url}")
        print(f"Twilio Webhook URL: {public_url}/webhook")
        print(f"{'='*50}\n")
        
        tunnels = ngrok.get_tunnels()
        if tunnels:
            logger.info(f"Ngrok tunnels: {tunnels}")
        else:
            logger.error("No ngrok tunnels found!")
    except Exception as e:
        logger.error(f"Error starting Ngrok: {e}")

async def startup():
    """Async startup tasks"""
    logger.info("Starting Grace...")
    # Refresh cached images
    asyncio.create_task(refresh_cached_images())
    await start_ngrok()
    init_db()

async def shutdown():
    """Cleanup tasks"""
    logger.info("Gracefully shutting down Grace.")
    ngrok.kill()

@app.post("/webhook")
async def handle_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(""),
    MediaUrl0: Optional[str] = Form(None),
    MediaContentType0: Optional[str] = Form(None)
):
    """Handle WhatsApp messages"""
    twilio_resp = MessagingResponse()
    sender = From
    message = Body.strip()
    media_url = MediaUrl0
    media_type = MediaContentType0

    try:
        # Ensure conversation_history is awaited properly
        conversation_history = await build_conversation_history(sender)

        logger.debug(f"Conversation history for {sender}: {conversation_history}")
        logger.debug(f"Incoming message from {sender}: {message[:100]}{'...' if len(message) > 100 else ''}")
        logger.debug(f"Media URL from {sender}: {media_url[:100]}{'...' if media_url and len(media_url) > 100 else ''}" if media_url else "Media URL: None")

        user = UserMemory(sender)

        # Handle media and image requests
        if media_url:
            bot_reply = await responses.handle_media_message(sender, media_url, media_type)
        elif message:
            # Handle text messages
            bot_reply = await responses.handle_text_message(sender, message, conversation_history)
        else:
            # Fallback for empty messages
            bot_reply = "Please send a message or an image."

        # Ensure bot_reply is a string
        if isinstance(bot_reply, list):
            bot_reply = "\n".join(bot_reply)

        # Create Twilio response
        twilio_resp.message(bot_reply)
        await log_chat(sender, message, bot_reply)
        return Response(content=str(twilio_resp), media_type="application/xml")

    except Exception as e:
        logger.error(f"Unexpected error for sender {sender}: {e}")
        bot_reply = "Sorry, something went wrong. Please try again later."
        twilio_resp.message(bot_reply)
        await log_chat(sender, message, bot_reply)
        return Response(content=str(twilio_resp), media_type="application/xml")

@app.post("/verify-payment")
async def verify_payment(verification: PaymentVerification):
    """Handle payment verification"""
    try:
        logger.debug(f"Received payment verification request: {verification.dict()}")
        
        # Run payment verification asynchronously
        result = await asyncio.to_thread(payment_handler.verify_payment, verification.code)
        
        if result['status'] == "success":
            logger.info(f"Payment verification successful for code: {verification.code}")
            return result
        raise HTTPException(status_code=404, detail=result)

    except Exception as e:
        logger.error(f"Payment verification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    try:
        database_status = await asyncio.wait_for(UserMemory.check_connection(), timeout=5)
        s3_status = await asyncio.wait_for(s3_service.check_connection(), timeout=5)
        ngrok_status = "connected" if ngrok.get_tunnels() else "disconnected"

        return {
            "status": "active",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "database": "connected" if database_status else "disconnected",
                "s3": "connected" if s3_status else "disconnected",
                "ngrok": ngrok_status
            }
        }
    except asyncio.TimeoutError:
        logger.error("Health check timeout")
        raise HTTPException(status_code=500, detail="Health check timed out")

@app.get("/")
async def home():
    return "Hello from Grace!"

async def log_chat(sender: str, user_msg: str, bot_reply: str) -> None:
    """Log conversation with enhanced structure"""
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
            async with aiofiles.open(log_file, "r+", encoding="utf-8") as file:
                try:
                    data = json.loads(await file.read())
                except json.JSONDecodeError:
                    logger.warning(f"Corrupted log file for {clean_sender}. Overwriting...")
                    data = []
                data.append(log_entry)
                await file.seek(0)
                await file.write(json.dumps(data, indent=2))
        else:
            async with aiofiles.open(log_file, "w", encoding="utf-8") as file:
                await file.write(json.dumps([log_entry], indent=2))
                
        logger.info(f"Logged message for {clean_sender}")
    except Exception as e:
        logger.error(f"Error logging chat for {clean_sender}: {e}")

async def refresh_cached_images():
    while True:
        cached_list_images.cache_clear()
        logger.info("Cached images cleared and refreshed")
        await asyncio.sleep(300)

@lru_cache(maxsize=1)  # Cache the health check result for a certain period to reduce repeated checks
async def cached_health_check():
    return await health_check()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=config.APP['debug'])