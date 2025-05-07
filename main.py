from fastapi import FastAPI, Request, HTTPException, status, Form, Response, UploadFile, File
from fastapi.responses import JSONResponse
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

from modules.payment_module import PaymentHandler
from modules.user_memory_module import UserMemory, build_conversation_history
from modules.s3_service import S3Service
from modules.image_processing_module import ImageProcessor
from modules.utils import detect_picture_request, cached_list_images
from modules.bot_responses import BotResponses
from config import config
from logging_config import configure_logger
from init_db import init_db

# Configure logger
logger = configure_logger("main")
logger.info("Main module initialized.")

load_dotenv()
conf.get_default().auth_token = os.getenv("NGROK_AUTH_TOKEN")

TENANTS_DIR = "tenants"
payment_handler = PaymentHandler()
s3_service = S3Service()
image_processor = ImageProcessor(s3_service)

if config.APP['debug']:
    print("Running in debug mode")
    logger.info("Debug mode enabled")

class PaymentVerification(BaseModel):
    code: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup()
    yield
    await shutdown()

app = FastAPI(lifespan=lifespan)

async def startup():
    logger.info("Starting Grace...")
    asyncio.create_task(refresh_cached_images())
    await start_ngrok()
    init_db()

async def shutdown():
    logger.info("Gracefully shutting down Grace.")
    ngrok.kill()

async def start_ngrok():
    try:
        public_url = ngrok.connect(8000).public_url
        logger.info(f"Ngrok public URL: {public_url}")
        print(f"\n{'='*50}\nServer running at: {public_url}\nTwilio Webhook URL: {public_url}/webhook\n{'='*50}\n")
    except Exception as e:
        logger.error(f"Error starting Ngrok: {e}")

def get_tenant_from_sender(sender: str) -> str:
    """Basic tenant resolver (replace with DB or config lookup if needed)."""
    phone_number = sender.replace("whatsapp:", "")
    return phone_number  # You can map this to tenant folders later

@app.post("/webhook")
async def handle_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(""),
    MediaUrl0: Optional[str] = Form(None),
    MediaContentType0: Optional[str] = Form(None)
):
    twilio_resp = MessagingResponse()
    sender = From
    message = Body.strip()
    media_url = MediaUrl0
    media_type = MediaContentType0

    tenant_id = get_tenant_from_sender(sender)
    responses = BotResponses(tenant_id)

    try:
        conversation_history = await build_conversation_history(sender)
        user = UserMemory(sender)

        if media_url:
            bot_reply = await responses.handle_media_message(sender, media_url, media_type)
        elif message:
            bot_reply = await responses.handle_text_message(sender, message, conversation_history)
        else:
            bot_reply = "Please send a message or an image."

        if isinstance(bot_reply, list):
            bot_reply = "\n".join(bot_reply)

        twilio_resp.message(bot_reply)
        await log_chat(sender, message, bot_reply)
        return Response(content=str(twilio_resp), media_type="application/xml")

    except Exception as e:
        logger.error(f"Webhook error for {sender}: {e}", exc_info=True)
        twilio_resp.message("Sorry, something went wrong. Please try again later.")
        return Response(content=str(twilio_resp), media_type="application/xml")

@app.post("/verify-payment")
async def verify_payment(verification: PaymentVerification):
    try:
        logger.debug(f"Payment verification request: {verification.dict()}")
        result = await asyncio.to_thread(payment_handler.verify_payment, verification.code)
        if result['status'] == "success":
            logger.info(f"Payment verified: {verification.code}")
            return result
        raise HTTPException(status_code=404, detail=result)
    except Exception as e:
        logger.error(f"Payment verification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload_catalog")
async def upload_catalog(
    tenant_id: str = Form(...),
    file: UploadFile = File(...)
):
    tenant_path = os.path.join(TENANTS_DIR, tenant_id)
    os.makedirs(tenant_path, exist_ok=True)
    catalog_path = os.path.join(tenant_path, "catalog.json")

    try:
        with open(catalog_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        with open(catalog_path, "r") as f:
            json.load(f)

        return JSONResponse(content={"message": f"Catalog uploaded for {tenant_id}"}, status_code=200)

    except json.JSONDecodeError:
        os.remove(catalog_path)
        raise HTTPException(status_code=400, detail="Uploaded file is not valid JSON")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
    except Exception as e:
        logger.error(f"Error logging chat for {clean_sender}: {e}")

async def refresh_cached_images():
    while True:
        cached_list_images.cache_clear()
        logger.info("Refreshed cached product images")
        await asyncio.sleep(300)

@lru_cache(maxsize=1)
async def cached_health_check():
    return await health_check()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=config.APP['debug'])
