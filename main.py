from fastapi import FastAPI, Request, HTTPException, Form, Response, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from twilio.twiml.messaging_response import MessagingResponse
from pyngrok import ngrok, conf
import os
import shutil
import logging
from datetime import datetime
import uvicorn
import aiofiles
import hashlib
import json
from dotenv import load_dotenv
from functools import lru_cache
import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from pydantic import BaseModel
from openai import AsyncOpenAI
from pathlib import Path
from stores.shopify_async import get_products_for_image_matching, get_shopify_products, _fuzzy_match_product, _format_product
from modules.shared import image_processor, s3_service
import csv
from fastapi.middleware.cors import CORSMiddleware
import aiosqlite

# ---------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------
class PaymentVerification(BaseModel):
    code: str

class ShopifyAskRequest(BaseModel):
    query: str

class DevChatRequest(BaseModel):
    query: str
    context_type: Optional[str] = "none"
    model: str = "gpt-4o"
    prompt_override: Optional[str] = None


# ---------------------------------------------------------------------
# Imports for Modules
# ---------------------------------------------------------------------
from modules.shopify_webhooks import router as shopify_router
from modules.payment_module import PaymentHandler
from modules.user_memory_module import UserMemory, build_conversation_history
from modules.utils import detect_picture_request, cached_list_images, compute_state_id
from modules.bot_responses import BotResponses, grade_turn
from modules.shopify_agent import agent
from config import config
from logging_config import configure_logger
from init_db import init_db
from admin.homepage import router as homepage_router
from modules.dev_assistant import agent as dev_agent, code_search, code_edit, _persist

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
responses = BotResponses()

if config.APP.get("debug"):
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
app.include_router(homepage_router)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure the "uploads" directory exists during startup
UPLOADS_DIR = "uploads"
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Define the /upload-image endpoint
@app.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """Handle image uploads and return a public URL."""
    path = os.path.join(UPLOADS_DIR, file.filename)
    with open(path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)
    public_url = f"http://localhost:8000/uploads/{file.filename}"
    return {"url": public_url}

# Serve the "uploads" folder as static files
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# Define the base directory and config directory
BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
CONFIG_DIR.mkdir(exist_ok=True)

# Mount the 'config' directory as static files
app.mount("/config", StaticFiles(directory=str(CONFIG_DIR)), name="config")

# Jinja2 templates for admin frontend
templates = Jinja2Templates(directory="admin/templates")

# ---------------------------------------------------------------------
# Startup and Shutdown
# ---------------------------------------------------------------------
refresh_task: Optional[asyncio.Task] = None

async def startup():
    logger.info("Starting Grace...")
    ensure_required_files()
    global refresh_task
    refresh_task = asyncio.create_task(refresh_cached_images())
    await start_ngrok()
    init_db()
    await payment_handler._ensure_tables()
    await image_processor.initialize()
    shopify_products = await get_products_for_image_matching()
    await image_processor.load_external_catalog(shopify_products)

async def shutdown():
    logger.info("Gracefully shutting down Grace.")
    global refresh_task
    if refresh_task and not refresh_task.cancelled():
        refresh_task.cancel()
        try:
            await refresh_task
        except asyncio.CancelledError:
            logger.debug("refresh_cached_images task cancelled")
    
    # Close the ImageProcessor instance
    if app.state.image_processor:
        try:
            await app.state.image_processor.close()
            logger.info("ImageProcessor closed successfully.")
        except Exception as e:
            logger.error(f"Error while closing ImageProcessor: {e}")

    # Kill Ngrok process
    try:
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
    MediaContentType0: Optional[str] = Form(None),
):
    sender = From
    message = Body.strip()
    logger.info(f"Sender: {sender}")

    form_data = await request.form()
    logger.info(f"Webhook form data: {dict(form_data)}")

    # Collect all media URLs and types
    media_urls = []
    media_types = []
    for i in range(10):
        url = form_data.get(f"MediaUrl{i}")
        mtype = form_data.get(f"MediaContentType{i}")
        if url:
            media_urls.append(url)
            media_types.append(mtype)

    try:
        # Accountant check
        if sender == config.BUSINESS_RULES.get("accountant_contact"):
            await payment_handler.process_accountant_message(message)
            return Response(content="ok", media_type="text/plain")

        # Payment-related message
        if "payment" in message.lower() or "deposit" in message.lower():
            reply = await payment_handler.process_user_message(sender, message)
            twilio_resp = MessagingResponse()
            twilio_resp.message(reply)
            await log_chat(sender, message, reply)
            return Response(content=str(twilio_resp), media_type="application/xml")

        # Build conversation history
        conversation_history = await build_conversation_history(sender)

        twilio_resp = MessagingResponse()
        # Handle multiple media
        if media_urls:
            for url, mtype in zip(media_urls, media_types):
                bot_reply = await responses.handle_media_message(sender, url, mtype)
                msg = twilio_resp.message(bot_reply)
        elif message:
            bot_reply = await responses.handle_text_message(sender, message, conversation_history)
            msg = twilio_resp.message(bot_reply)
            # Attach image as media if present in reply
            import re
            match = re.search(r'(https?://\S+\.(?:jpg|jpeg|png|gif))', bot_reply)
            if match:
                msg.media(match.group(1))
            await log_chat(sender, message, bot_reply)
        else:
            default_reply = "Please send a message or an image."
            twilio_resp.message(default_reply)
            await log_chat(sender, message, default_reply)

        return Response(content=str(twilio_resp), media_type="application/xml")

    except Exception as e:
        logger.error(f"Webhook error for sender '{sender}': {e}", exc_info=True)
        return Response(content="Sorry, something went wrong.", media_type="application/xml")

@app.post("/verify-payment")
async def verify_payment(verification: PaymentVerification):
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
        "fallback_responses": "fallback_responses.json",
        "system_prompt": "system_prompt.json"
    }
    if file_type not in filename_map:
        raise HTTPException(status_code=400, detail="Invalid file type")
    file_path = os.path.join("config", filename_map[file_type])
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        if file_type == "system_prompt":
            responses.brain.__init__()  # Re-initialize to reload prompt
        return {"message": f"{file_type} uploaded successfully."}
    except Exception as e:
        logger.error(f"Error uploading file '{file_type}': {e}")
        raise HTTPException(status_code=500, detail="File upload failed")

@app.get("/admin/upload")
async def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

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

@app.post("/shopify/ask")
async def shopify_ask(req: ShopifyAskRequest):
    """
    Search catalog by name (fast) and fall back to the LLM agent for
    free-form questions that aren’t matched.
    """
    try:
        # 1) Fast fuzzy match first
        products = await get_shopify_products()
        match = _fuzzy_match_product(req.query, products)
        if match:
            # Format the matched product for the front-end
            formatted_product = _format_product(match)
            return {"products": [formatted_product]}  # <-- front-end ready

        # 2) Otherwise let the agent reason (but guard schema)
        try:
            llm_out = await agent.ainvoke({"input": req.query})
            interpreted = llm_out.get("output", req.query)
        except Exception as e:
            logger.warning("Agent failed: %s. Using raw query.", e)
            interpreted = req.query

        # Fuzzy match again with the interpreted query
        match = _fuzzy_match_product(interpreted, products)
        if match:
            formatted_product = _format_product(match)
            return {"products": [formatted_product]}

        # No match found
        return {"products": []}

    except Exception as e:
        logger.exception("Unexpected error in /shopify/ask")
        raise HTTPException(500, "Store unavailable")
    
@app.post("/shopify/catalog")
async def get_full_catalog():
    """Return the full Shopify catalog."""
    prods = await get_products_for_image_matching()
    return {"products": prods}

def load_prompt(filename: str) -> str:
    path = Path("config") / filename
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")

@app.post("/dev/chat")
async def dev_chat(req: DevChatRequest):
    """
    Handle requests to the Dev Assistant via /dev/chat.
    """
    client = AsyncOpenAI()
    system_prompt = req.prompt_override or load_prompt("dev_assistant_prompt.txt")
    context_data = ""

    # Load on-demand context (e.g., catalog, config, tone, chatlog)
    if req.context_type in {"catalog", "config", "tone"}:
        file_path = f"config/{req.context_type}.json"
        if Path(file_path).exists():
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                content = await f.read()
                context_data += f"---\n{req.context_type.upper()}:\n{content}\n---"
    elif req.context_type == "chatlog":
        from glob import glob
        files = sorted(glob("logs/*_chat_history.json"), reverse=True)
        if files:
            async with aiofiles.open(files[0], "r", encoding="utf-8") as f:
                data = json.loads(await f.read())
            last_5 = data[-5:] if len(data) >= 5 else data
            context_data += "---\nRecent Conversation:\n" + "\n".join(
                f"U: {x['user_message']}\nG: {x['bot_reply']}" for x in last_5
            ) + "\n---"

    # Load Dev Assistant memory if context_type is "dev_memory"
    if req.context_type == "dev_memory":
        memory_file = "config/dev_assistant_memory.json"
        if os.path.exists(memory_file):
            async with aiofiles.open(memory_file, "r", encoding="utf-8") as f:
                memory_data = json.loads(await f.read())
                conversations = memory_data.get("conversations", [])
                notes = memory_data.get("notes", {})
                context_data += "---\nDev Memory:\n"
                context_data += "Conversations:\n" + "\n".join(
                    f"- {conv['timestamp']} [{conv['topic']}]: {conv['user_prompt']} → {conv['assistant_reply']}"
                    for conv in conversations
                )
                context_data += "\nNotes:\n" + "\n".join(
                    f"- {key}: {', '.join(value)}" for key, value in notes.items()
                )
                context_data += "\n---"

    # Combine system prompt, context data, and user query
    full_prompt = f"{system_prompt}\n\n{context_data}\n\nUser query:\n{req.query}"

    try:
        # Use the dev_agent to process the query
        result = await dev_agent.arun(req.query)

        # Save the conversation to Dev Assistant memory if context_type is "dev_memory"
        if req.context_type == "dev_memory":
            async with aiofiles.open(memory_file, "r+", encoding="utf-8") as f:
                try:
                    memory_data = json.loads(await f.read())
                except json.JSONDecodeError:
                    memory_data = {"conversations": [], "notes": {}}
                memory_data["conversations"].append({
                    "timestamp": datetime.now().isoformat(),
                    "topic": req.query.split()[0],  # Use the first word as a topic placeholder
                    "user_prompt": req.query,
                    "assistant_reply": result
                })
                await f.seek(0)
                await f.write(json.dumps(memory_data, indent=2))
                await f.truncate()

        # Persist memory turn
        _persist({"user": req.query, "assistant": result})

        return {"result": result}
    except Exception as e:
        logger.error(f"Error in /dev/chat: {str(e)}")
        return {"error": str(e)}

# ---------------------------------------------------------------------
@app.get("/admin/get_dev_memory")
async def get_dev_memory():
    """
    Retrieve the Dev Assistant memory.
    """
    file_path = "config/dev_assistant_memory.json"
    if not os.path.exists(file_path):
        return {"conversations": [], "notes": {}}
    async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
        try:
            data = json.loads(await f.read())
            return data
        except Exception:
            return {"conversations": [], "notes": {}}


@app.post("/admin/save_dev_memory")
async def save_dev_memory(req: Request):
    """
    Save a note to the Dev Assistant memory.
    """
    data = await req.json()
    key = data.get("key", "").strip()
    value = data.get("value", "").strip()
    if not key or not value:
        return {"error": "Missing key or value"}
    file_path = "config/dev_assistant_memory.json"
    async with aiofiles.open(file_path, "r+", encoding="utf-8") as f:
        try:
            memory_data = json.loads(await f.read())
        except json.JSONDecodeError:
            memory_data = {"conversations": [], "notes": {}}
        if key not in memory_data["notes"]:
            memory_data["notes"][key] = []
        memory_data["notes"][key].append(value)
        await f.seek(0)
        await f.write(json.dumps(memory_data, indent=2))
        await f.truncate()
    return {"message": "Note added successfully"}

@app.get("/dev")
async def dev_chat_ui(request: Request):
    return templates.TemplateResponse("dev_chat.html", {"request": request})

@app.post("/admin/save_speech_library")
async def save_speech_library(req: Request):
    data = await req.json()
    phrase = data.get("phrase", "").strip()
    response = data.get("response", "").strip()
    if not phrase or not response:
        return {"error": "Missing phrase or response"}
    file_path = "config/speech_library.json"
    async with aiofiles.open(file_path, "r+", encoding="utf-8") as f:
        try:
            existing = json.loads(await f.read())
        except:
            existing = {"training_data": []}
        existing["training_data"].append({"phrase": phrase, "response": response})
        await f.seek(0)
        await f.write(json.dumps(existing, indent=2))
        await f.truncate()
    return {"message": "Saved to speech library ✅"}

@app.get("/admin/get_speech_library")
async def get_speech_library():
    """
    Returns the current speech library as JSON.
    """
    file_path = "config/speech_library.json"
    if not os.path.exists(file_path):
        return {"training_data": []}
    async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
        try:
            data = json.loads(await f.read())
            return data
        except Exception:
            return {"training_data": []}

@app.post("/dev/tone")
async def generate_tones(req: Request):
    data = await req.json()
    base = data.get("message", "")
    tones = {
        "Friendly": f"Rephrase this in a warm, casual, friendly tone: {base}",
        "Formal": f"Rephrase this more formally and politely: {base}",
        "Playful": f"Make this sound fun and cheeky, but still clear: {base}",
        "Professional": f"Rephrase this for a business-savvy, helpful assistant: {base}",
    }
    results = {}
    client = AsyncOpenAI()
    for tone, prompt in tones.items():
        try:
            res = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Rewrite in a specific tone."},
                    {"role": "user", "content": prompt}
                ]
            )
            results[tone] = res.choices[0].message.content.strip()
        except Exception as e:
            results[tone] = f"Error: {e}"
    return results

@app.post("/dev/grade")
async def dev_grade(req: Request):
    data = await req.json()
    user = data.get("user", "")
    reply = data.get("reply", "")
    if not user or not reply:
        return {"error": "Missing user or reply"}
    prompt = (
        "You are an expert conversation grader. "
        "Given a user message and Grace's reply, score the reply from 1-10 for clarity, helpfulness, tone, and conversion potential. "
        "Then explain your score in 1-2 sentences.\n\n"
        f"User: {user}\nGrace: {reply}\n\n"
        "Respond in JSON: {\"score\": <number>, \"explanation\": \"...\"}"
    )
    client = AsyncOpenAI()
    try:
        res = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": prompt}]
        )
        import json as pyjson
        import re
        text = res.choices[0].message.content
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return pyjson.loads(match.group(0))
        return {"score": None, "explanation": text}
    except Exception as e:
        return {"error": str(e)}

@app.get("/memory")
async def get_all_memories():
    """
    Retrieve all stored user memories.
    """
    try:
        async with aiosqlite.connect("memory.db") as conn:
            cursor = await conn.execute("SELECT * FROM user_memory")
            rows = await cursor.fetchall()
            memories = [
                {
                    "sender": row[0],
                    "name": row[1],
                    "conversation_history": json.loads(row[2]) if row[2] else [],
                    "preferences": json.loads(row[3]) if row[3] else {},
                    "last_order": row[4],
                    "last_interaction": row[5],
                }
                for row in rows
            ]
        return {"memories": memories}
    except Exception as e:
        logger.error(f"Failed to retrieve memories: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve memories.")

@app.get("/prompt")
async def get_system_prompt():
    """
    Retrieve the system prompt from the config file.
    """
    try:
        prompt_file = "config/system_prompt.txt"
        if not os.path.exists(prompt_file):
            return {"prompt": ""}
        async with aiofiles.open(prompt_file, "r", encoding="utf-8") as f:
            prompt = await f.read()
        return {"prompt": prompt}
    except Exception as e:
        logger.error(f"Failed to retrieve system prompt: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system prompt.")

# ---------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------
async def log_chat(sender: str, user_msg: str, bot_reply: str, auto_score: int = None, prompt_version: str = None) -> None:
    clean_sender = sender.replace("whatsapp:", "")
    log_file = f"logs/{clean_sender}_chat_history.json"
    state_id = await compute_state_id()
    score = await grade_turn(user_msg, bot_reply)
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "sender": clean_sender,
        "user_message": user_msg,
        "bot_reply": bot_reply,
        "auto_score": score,
        "human_score": None,
        "state_id": state_id,
        "prompt_version": prompt_version
    }
    # Conversation Metrics
    try:
        if "order placed" in bot_reply.lower():
            with open("logs/conversation_metrics.csv", "a", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["order_placed", clean_sender, 1, datetime.now().isoformat()])
        if "refund" in user_msg.lower() or "refund" in bot_reply.lower():
            with open("logs/conversation_metrics.csv", "a", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["refund_mentioned", clean_sender, 1, datetime.now().isoformat()])
        with open("logs/conversation_metrics.csv", "a", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["words_per_turn", clean_sender, len(bot_reply.split()), datetime.now().isoformat()])
    except Exception as e:
        logger.error(f"Error logging conversation metrics for {clean_sender}: {e}")

    # Export Top Q&A Pairs for Fine-Tuning
    try:
        if score is not None and score >= 8:
            with open("logs/top_pairs.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "question": user_msg,
                    "answer": bot_reply,
                    "score": score
                }) + "\n")
    except Exception as e:
        logger.error(f"Error exporting top Q&A pair for {clean_sender}: {e}")

    # Log Chat Turn
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
    try:
        while True:
            cached_list_images.cache_clear()
            logger.info("Refreshed cached product images")
            await asyncio.sleep(300)
    except asyncio.CancelledError:
        logger.info("refresh_cached_images task cancelled")

def ensure_required_files():
    required_files = ["config.json", "catalog.json", "speech_library.json", "fallback_responses.json"]
    for file in required_files:
        file_path = os.path.join("config", file)
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                if file == "speech_library.json":
                    json.dump({"training_data": []}, f, indent=2)
                else:
                    f.write("{}")
            logger.warning(f"Created placeholder for missing file: {file}")

@lru_cache(maxsize=1)
async def cached_health_check():
    return await health_check()

# ---------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.APP["port"],
        reload=False,
        log_level="info",
    )
