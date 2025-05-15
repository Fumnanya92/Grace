from fastapi import FastAPI, Request, HTTPException, Form, Response, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from twilio.twiml.messaging_response import MessagingResponse
from pyngrok import ngrok, conf
import os
import shutil
import logging
from datetime import datetime
import uvicorn
import aiofiles
import json
from dotenv import load_dotenv
from functools import lru_cache
import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from pydantic import BaseModel
from pathlib import Path

# ---------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------
class PaymentVerification(BaseModel):
    code: str

# ---------------------------------------------------------------------
# Imports for Modules
# ---------------------------------------------------------------------
from modules.shopify_webhooks import router as shopify_router
from modules.payment_module import PaymentHandler
from modules.user_memory_module import UserMemory, build_conversation_history
from modules.s3_service import S3Service
from modules.image_processing_module import ImageProcessor
from modules.utils import detect_picture_request, cached_list_images
from modules.bot_responses import BotResponses
from config import config
from logging_config import configure_logger
from init_db import init_db

# ---------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------
logger = configure_logger("main")
logger.info("Main module initialized.")

# Load environment variables
load_dotenv()
conf.get_default().auth_token = config.APP["ngrok_auth_token"]

# Initialize services
payment_handler = PaymentHandler()
s3_service = S3Service()
image_processor = ImageProcessor(s3_service)

if config.APP["debug"]:
    logger.info("Debug mode enabled")

# ---------------------------------------------------------------------
# FastAPI App Setup
# ---------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup()
    yield
    await shutdown()

app = FastAPI(lifespan=lifespan)
app.include_router(shopify_router)

# Define the base directory and config directory
BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
CONFIG_DIR.mkdir(exist_ok=True)  # Ensure the 'config' directory exists

# Mount the 'config' directory as static files
app.mount("/config", StaticFiles(directory=str(CONFIG_DIR)), name="config")

# ---------------------------------------------------------------------
# Startup and Shutdown
# ---------------------------------------------------------------------
async def startup():
    logger.info("Starting Grace...")
    ensure_required_files()
    asyncio.create_task(refresh_cached_images())
    await start_ngrok()
    init_db()
    await payment_handler._ensure_tables()  # Ensure payment database tables exist

async def shutdown():
    logger.info("Gracefully shutting down Grace.")
    try:
        logger.debug("Attempting to kill Ngrok process...")
        ngrok.kill()
        logger.debug("Ngrok process killed successfully.")
    except Exception as e:
        logger.error(f"Error while shutting down Ngrok: {e}")

async def start_ngrok():
    try:
        public_url = ngrok.connect(config.APP["port"]).public_url
        logger.info(f"Ngrok public URL: {public_url}")
        print(f"\n{'='*50}\nServer running at: {public_url}\nTwilio Webhook URL: {public_url}/webhook\n{'='*50}\n")
    except Exception as e:
        logger.error(f"Error starting Ngrok: {e}")

# ---------------------------------------------------------------------
# Webhook Endpoints
# ---------------------------------------------------------------------
@app.post("/webhook")
async def handle_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(""),
    MediaUrl0: Optional[str] = Form(None),
    MediaContentType0: Optional[str] = Form(None)
):
    sender = From
    message = Body.strip()
    media_url = MediaUrl0
    media_type = MediaContentType0
    logger.info(f"Sender: {sender}")

    responses = BotResponses()

    try:
        # Check if the sender is the accountant
        if sender == config.BUSINESS_RULES["accountant_contact"]:
            await payment_handler.process_accountant_message(message)
            return Response(content="ok", media_type="text/plain")

        # Check if the message is payment-related
        if "payment" in message.lower() or "deposit" in message.lower():
            reply = await payment_handler.process_user_message(sender, message)
            twilio_resp = MessagingResponse()
            twilio_resp.message(reply)
            await log_chat(sender, message, reply)
            return Response(content=str(twilio_resp), media_type="application/xml")

        # Build conversation history
        conversation_history = await build_conversation_history(sender)

        # Process the message or media
        if media_url:
            bot_reply = await responses.handle_media_message(sender, media_url, media_type)
        elif message:
            bot_reply = await responses.handle_text_message(sender, message, conversation_history)
        else:
            bot_reply = "Please send a message or an image."

        twilio_resp = MessagingResponse()
        twilio_resp.message(bot_reply)
        await log_chat(sender, message, bot_reply)
        return Response(content=str(twilio_resp), media_type="application/xml")

    except Exception as e:
        logger.error(f"Webhook error for sender '{sender}': {e}", exc_info=True)
        return Response(content="Sorry, something went wrong.", media_type="application/xml")

@app.post("/verify-payment")
async def verify_payment(verification: PaymentVerification):
    """
    Verify a payment using the PaymentHandler.
    """
    try:
        logger.debug(f"Payment verification request: {verification.dict()}")
        result = await asyncio.to_thread(payment_handler.verify_payment, verification.code)
        if result["status"] == "success":
            logger.info(f"Payment verified: {verification.code}")
            return result
        raise HTTPException(status_code=404, detail=result)
    except Exception as e:
        logger.error(f"Payment verification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/upload")
async def upload_file(file: UploadFile = File(...), file_type: str = Form(...)):
    filename_map = {
        "catalog": "catalog.json",
        "config": "config.json",
        "speech_library": "speech_library.json",
        "fallback_responses": "fallback_responses.json"
    }

    if file_type not in filename_map:
        raise HTTPException(status_code=400, detail="Invalid file type")

    file_path = os.path.join("config", filename_map[file_type])

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"message": f"{file_type} uploaded successfully."}
    except Exception as e:
        logger.error(f"Error uploading file '{file_type}': {e}")
        raise HTTPException(status_code=500, detail="File upload failed")

@app.get("/health")
async def health_check():
    try:
        db = await asyncio.wait_for(UserMemory.check_connection(), timeout=5)
        s3 = await asyncio.wait_for(s3_service.check_connection(), timeout=5)
        ngrok_status = "connected" if ngrok.get_tunnels() else "disconnected"

        return {
            "status": "active",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "database": "connected" if db else "disconnected",
                "s3": "connected" if s3 else "disconnected",
                "ngrok": ngrok_status
            }
        }
    except asyncio.TimeoutError:
        raise HTTPException(status_code=500, detail="Health check timed out")

@app.get("/")
async def home():
    return "Hello from Grace!"

# ---------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------
async def log_chat(sender: str, user_msg: str, bot_reply: str) -> None:
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
                    data = []
                data.append(log_entry)
                await file.seek(0)
                await file.write(json.dumps(data, indent=2))
        else:
            async with aiofiles.open(log_file, "w", encoding="utf-8") as file:
                await file.write(json.dumps([log_entry], indent=2))

        logger.info(f"Logged message for {clean_sender}")
    except PermissionError as e:
        logger.error(f"Permission denied while logging chat for {clean_sender}: {e}")
    except Exception as e:
        logger.error(f"Error logging chat for {clean_sender}: {e}")

async def refresh_cached_images():
    while True:
        cached_list_images.cache_clear()
        logger.info("Refreshed cached product images")
        await asyncio.sleep(300)

def ensure_required_files():
    """Ensure required configuration files exist in the 'config' directory."""
    required_files = ["config.json", "catalog.json", "speech_library.json", "fallback_responses.json"]
    for file in required_files:
        file_path = os.path.join("config", file)
        if not os.path.exists(file_path):
            with open(file_path, "w") as f:
                f.write("{}")  # Create an empty JSON file
            logger.warning(f"Created placeholder for missing file: {file}")

@lru_cache(maxsize=1)
async def cached_health_check():
    return await health_check()

# ---------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=config.APP["port"], reload=config.APP["debug"])
