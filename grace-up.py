from flask import Flask, request, abort
from twilio.twiml.messaging_response import MessagingResponse
from pyngrok import ngrok, conf
import openai
import os
import json
import sqlite3
import logging
import glob
import re
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import Optional, Dict, Any, List
import requests
from fuzzywuzzy import fuzz
from bs4 import BeautifulSoup
from functools import lru_cache

# Load environment variables
load_dotenv()

# Fetch credentials from .env
SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY")
SHOPIFY_PASSWORD = os.getenv("SHOPIFY_PASSWORD")
SHOPIFY_STORE_NAME = os.getenv("SHOPIFY_STORE_NAME")
openai.api_key = os.getenv("OPENAI_API_KEY")
ngrok_auth_token = os.getenv("NGROK_AUTH_TOKEN")
conf.get_default().auth_token = ngrok_auth_token

# Setup logging
logging.basicConfig(
    filename='grace.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(message)s',
    filemode='w'  # Clear logs on startup
)

# Initialize Flask app
app = Flask(__name__)

# Cache configuration
PRODUCT_CACHE_TTL = 3600  # 1 hour cache for products
last_product_fetch_time = 0
cached_products = []

# SQLite3 datetime adapters for Python 3.12+
def adapt_datetime(dt):
    return dt.isoformat()

def convert_datetime(text):
    return datetime.fromisoformat(text.decode())

sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("datetime", convert_datetime)

# Database setup with migration
def init_db():
    """Initialize or migrate the database schema."""
    try:
        with sqlite3.connect('memory.db', detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_memory'")
            table_exists = cursor.fetchone()

            if table_exists:
                cursor.execute("PRAGMA table_info(user_memory)")
                columns = [col[1] for col in cursor.fetchall()]
                if 'conversation_history' not in columns:
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS new_user_memory (
                            sender TEXT PRIMARY KEY,
                            name TEXT,
                            conversation_history TEXT,
                            preferences TEXT,
                            last_order TEXT,
                            last_interaction TIMESTAMP
                        )
                    ''')
                    cursor.execute('''
                        INSERT INTO new_user_memory (sender, name, last_order, last_interaction)
                        SELECT sender, name, appointment, datetime('now') 
                        FROM user_memory
                    ''')
                    cursor.execute("DROP TABLE user_memory")
                    cursor.execute("ALTER TABLE new_user_memory RENAME TO user_memory")
                    logging.info("Database schema migrated successfully")
            else:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_memory (
                        sender TEXT PRIMARY KEY,
                        name TEXT,
                        conversation_history TEXT,
                        preferences TEXT,
                        last_order TEXT,
                        last_interaction TIMESTAMP
                    )
                ''')
            conn.commit()
    except Exception as e:
        logging.error(f"Error initializing database: {e}")

# Clean old log files
def clean_old_logs(days_to_keep=7):
    """Clean log files older than the specified days."""
    try:
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        for log_file in glob.glob("logs/*.json"):
            file_time = datetime.fromtimestamp(os.path.getmtime(log_file))
            if file_time < cutoff_date:
                os.remove(log_file)
                logging.info(f"Removed old log file: {log_file}")
    except Exception as e:
        logging.error(f"Error cleaning old logs: {e}")

# Save user memory to database
def save_memory(sender: str, name: Optional[str] = None, conversation: Optional[list] = None,
                preferences: Optional[dict] = None, last_order: Optional[str] = None) -> None:
    """Save user memory to the database."""
    with sqlite3.connect('memory.db', detect_types=sqlite3.PARSE_DECLTYPES) as conn:
        cursor = conn.cursor()
        existing = get_memory(sender)
        updated_name = name or (existing['name'] if existing else None)
        updated_conversation = conversation or (existing['conversation_history'] if existing else [])
        updated_preferences = {**(existing['preferences'] if existing else {}), **(preferences or {})}
        updated_order = last_order or (existing['last_order'] if existing else None)

        cursor.execute('''
            INSERT OR REPLACE INTO user_memory 
            (sender, name, conversation_history, preferences, last_order, last_interaction)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (sender, updated_name, json.dumps(updated_conversation), json.dumps(updated_preferences), updated_order, datetime.now()))
        conn.commit()

# Retrieve user memory from the database
def get_memory(sender: str) -> Optional[Dict[str, Any]]:
    """Retrieve user memory from the database."""
    with sqlite3.connect('memory.db', detect_types=sqlite3.PARSE_DECLTYPES) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT name, conversation_history, preferences, last_order 
            FROM user_memory WHERE sender = ?
        ''', (sender,))
        result = cursor.fetchone()

    if result:
        return {
            'name': result[0],
            'conversation_history': json.loads(result[1]) if result[1] else [],
            'preferences': json.loads(result[2]) if result[2] else {},
            'last_order': result[3]
        }
    return None

# Handle name extraction from user input
def extract_name(message: str) -> Optional[str]:
    """Extract name from the message."""
    patterns = [
        r"my name is (\w+)",
        r"i am (\w+)",
        r"call me (\w+)",
        r"this is (\w+)",
        r"^(\w+)$"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None

# Build conversation history including memory
def build_conversation_history(sender: str, new_message: str) -> list:
    """Build complete conversation history including Grace's brand-aligned system prompt."""
    memory = get_memory(sender)
    messages = [ {
        "role": "system",
        "content": f"""You are Grace, Atuchewoman's expert WhatsApp assistant.
Speak with warm confidence, celebrate African heritage in every reply,
and never discuss non-Atuchewoman topics. Avoid emojis unless they enhance empathy.
Always recommend products by name and provide direct links to the Shopify store or Instagram.
De-escalate upset customers with sincere empathy and empower every woman through fashion.

{f"Customer details: Name: {memory['name']}" if memory and memory.get('name') else ""}
{f"Last order: {memory['last_order']}" if memory and memory.get('last_order') else ""}
"""
    }]

    if memory and memory.get('conversation_history'):
        messages.extend(memory['conversation_history'])

    messages.append({"role": "user", "content": new_message})
    return messages

# Log conversation
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
                    data = []
                data.append(log_entry)
                file.seek(0)
                json.dump(data, file, indent=2)
        else:
            with open(log_file, "w", encoding="utf-8") as file:
                json.dump([log_entry], file, indent=2)
                
        logging.info(f"Logged message for {clean_sender}")
    except Exception as e:
        logging.error(f"Error logging chat: {e}")

# Process order mentions in user messages
def process_order_mentions(message: str) -> Optional[dict]:
    """Extract order-related information from message."""
    patterns = {
        "order_number": r"(order|reference)\s*(?:no|number)?\s*[:#]?\s*(\w+)",
        "tracking": r"(track|status)\s+(?:my\s+)?order",
        "return": r"(return|exchange)\s+(?:my\s+)?(order|item)"
    }
    
    extracted = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            extracted[key] = match.group(2) if len(match.groups()) > 1 else True
    
    return extracted if extracted else None

# Shopify-related functions with caching
def get_shopify_products(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Get Shopify products with caching mechanism."""
    global last_product_fetch_time, cached_products
    
    current_time = time.time()
    
    if not force_refresh and current_time - last_product_fetch_time < PRODUCT_CACHE_TTL and cached_products:
        return cached_products
    
    url = f"https://{SHOPIFY_STORE_NAME}.myshopify.com/admin/api/2023-01/products.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_PASSWORD,
        "Content-Type": "application/json"
    }

    products = []
    page = 1
    while True:
        response = requests.get(f"{url}?page={page}&limit=50", headers=headers)
        if response.status_code == 200:
            data = response.json().get("products", [])
            if not data:
                break
            products.extend(data)
            page += 1
        else:
            logging.error(f"Error fetching products: {response.status_code}")
            break
    
    # Update cache
    cached_products = products
    last_product_fetch_time = current_time
    return products

def get_product_details(product_query: str) -> Optional[Dict[str, Any]]:
    """Get detailed product information from Shopify including availability."""
    products = get_shopify_products()
    if not products:
        return None
    
    # First try exact match
    for product in products:
        if product_query.lower() == product['title'].lower():
            return product
    
    # Then try fuzzy match if no exact match
    return fuzzy_match_product(product_query, products)

def format_product_response(product: Dict[str, Any]) -> str:
    """Format a standardized product response with all key details."""
    available_stock = product['variants'][0].get('inventory_quantity', 0)
    price = product['variants'][0].get('price', 'Price not available')
    product_link = f"https://{SHOPIFY_STORE_NAME}.myshopify.com/products/{product['handle']}"
    
    response = [
        f"✨ {product['title']} ✨",
        f"💵 Price: {price}",
        f"📦 Availability: {'In stock' if available_stock > 0 else 'Out of stock'}",
        f"{available_stock} units available" if available_stock > 0 else "",
        f"🔗 View product: {product_link}"
    ]
    
    # Add product description if available
    if product.get('body_html'):
        response.append(f"\n📝 Description: {BeautifulSoup(product['body_html'], 'html.parser').get_text()[:200]}...")
    
    return "\n".join(filter(None, response))

def is_product_query(message: str) -> bool:
    """Determine if a message is asking about a product."""
    product_keywords = [
        'have', 'stock', 'carry', 'sell', 'available', 
        'product', 'item', 'dress', 'collection'
    ]
    
    # Check for direct questions
    if any(word in message.lower() for word in product_keywords):
        return True
        
    # Check for "Do you have X?" pattern
    if re.search(r'do you (have|sell|carry|stock)', message, re.IGNORECASE):
        return True
        
    return False

def extract_product_name(message: str) -> Optional[str]:
    """Extract product name from a query."""
    # Handle "Do you have X?" pattern
    match = re.search(r'do you (?:have|sell|carry|stock) (.*?)\??$', message, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Handle "I'm looking for X"
    match = re.search(r'(?:looking for|want|need) (.*?)[\.\?]?$', message, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Handle direct product mentions
    product_words = ['dress', 'top', 'skirt', 'item', 'product']
    if any(word in message.lower() for word in product_words):
        return message  # Return the whole message for fuzzy matching
    
    return None

def fuzzy_match_product(user_input: str, products: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Find the best matching product using fuzzy matching."""
    user_input = user_input.lower()
    matches = []
    for product in products:
        title = product['title'].lower()
        score = fuzz.token_set_ratio(user_input, title)
        if score > 70:  # Threshold for a good match
            matches.append((product, score))
    matches.sort(key=lambda x: x[1], reverse=True)
    return matches[0][0] if matches else None

def get_order_status(order_id: str) -> str:
    shopify_url = f"https://{SHOPIFY_STORE_NAME}.myshopify.com/admin/api/2023-01/orders/{order_id}.json"
    headers = {
        'X-Shopify-Access-Token': SHOPIFY_PASSWORD
    }

    response = requests.get(shopify_url, headers=headers)

    if response.status_code == 200:
        try:
            order_data = response.json().get('order', {})
            status = order_data.get('fulfillment_status')
            if status is None:
                return "Not fulfilled yet"
            return status
        except requests.exceptions.JSONDecodeError:
            return "Invalid response format."
    elif response.status_code == 404:
        return "Order not found. Please check the order ID."
    else:
        return f"Unable to retrieve status. Shopify returned {response.status_code}."

def track_order(order_id: str) -> str:
    order_status = get_order_status(order_id)
    return f"Your order is currently: {order_status}"

def handle_customer_images(image_url: str) -> str:
    logging.info(f"Received image link: {image_url}")
    return f"Thanks for sending the image! Please give me a moment while I check for the details."

def ask_for_size() -> str:
    return "Could you please provide your size from the size chart below?\n\n" \
           "If you're unsure, don't worry! I can guide you on how to measure yourself."

def display_size_chart() -> str:
    return "Here is the Atuchewoman size chart:\n" \
           "Size 6 -> Bust: 33, Waist: 26, Hips: 36\n" \
           "Size 8 -> Bust: 35, Waist: 28, Hips: 38\n" \
           "Size 10 -> Bust: 37, Waist: 30, Hips: 40\n" \
           "Size 12 -> Bust: 39, Waist: 32, Hips: 42\n" \
           "Size 14 -> Bust: 41, Waist: 34, Hips: 44\n" \
           "Size 16 -> Bust: 43, Waist: 36, Hips: 46\n" \
           "Size 18 -> Bust: 45, Waist: 38, Hips: 48\n" \
           "Size 20 -> Bust: 47, Waist: 40, Hips: 50\n" \
           "Size 22 -> Bust: 49, Waist: 42, Hips: 52\n"

def guide_on_measuring() -> str:
    return "No problem! Here's how to measure yourself for the best fit:\n" \
           "1. **Bust**: Measure the widest part of your bust while keeping your arms down.\n" \
           "2. **Waist**: Measure around the narrowest part of your waist.\n" \
           "3. **Hips**: Measure around the fullest part of your hips.\n\n" \
           "Once you have your measurements, let me know your size!"

def handle_size_request() -> str:
    return (ask_for_size() + "\n" + display_size_chart() + "\n" + guide_on_measuring())

def get_latest_collection() -> str:
    """Get a formatted string of the latest collection."""
    products = get_shopify_products()
    if not products:
        return "Our latest collection is currently being updated. Please check back soon!"
    
    # Get the 5 most recently updated products
    latest_products = sorted(products, key=lambda x: x.get('updated_at', ''), reverse=True)[:5]
    
    response = ["✨ Our Latest Collection ✨"]
    for product in latest_products:
        product_link = f"https://{SHOPIFY_STORE_NAME}.myshopify.com/products/{product['handle']}"
        response.append(f"\n- {product['title']}: {product_link}")
    
    return "\n".join(response)

def process_product_query(customer_query: str) -> str:
    """Handle product-related queries with Shopify integration."""
    product_name = extract_product_name(customer_query)
    if not product_name:
        return "Could you please specify which product you're asking about?"
    
    product = get_product_details(product_name)
    if product:
        return format_product_response(product)
    else:
        # Product not found - suggest alternatives
        return (
            f"I couldn't find '{product_name}' in our collection. "
            f"Here are some similar items you might like:\n\n"
            f"{get_latest_collection()}"
        )

def process_customer_query(customer_query: str, order_id: Optional[str] = None, 
                          product_id: Optional[str] = None, image_url: Optional[str] = None) -> str:
    """Process customer queries with priority to Shopify product info."""
    if image_url:
        return handle_customer_images(image_url)
    elif order_id:
        return track_order(order_id)
    elif customer_query.lower() in ["order status", "track my order"]:
        return track_order(order_id) if order_id else "Please provide your order number"
    elif "size" in customer_query.lower():
        return handle_size_request()
    elif is_product_query(customer_query):
        return process_product_query(customer_query)
    else:
        return "Could you please clarify your request? I'm happy to help with product information, order status, or sizing."

# Helper function to enforce timeout
def enforce_timeout(start_time: float, timeout: float, sender: str, twilio_resp: MessagingResponse) -> None:
    """Enforce a timeout for processing a request."""
    if time.time() - start_time > timeout:
        logging.warning(f"Timeout processing message from {sender}")
        twilio_resp.message("Sorry, it seems like the request is taking too long. Please try again later.")
        abort(500)

# Helper function to retrieve conversation history
def get_conversation_history(sender: str, new_message: str) -> list:
    """Retrieve and build the conversation history for a user."""
    return build_conversation_history(sender, new_message)

# Helper function to retrieve user memory
def retrieve_user_memory(sender: str) -> Optional[Dict[str, Any]]:
    """Retrieve user memory for a given sender."""
    return get_memory(sender)

# Helper function to update user memory
def update_user_memory(sender: str, conversation: list) -> None:
    """Update user memory with the latest conversation."""
    save_memory(sender=sender, conversation=conversation[-10:])

# Helper function to log conversations
def log_conversation(sender: str, user_message: str, bot_response: str) -> None:
    """Log the conversation between the user and the bot."""
    log_chat(sender, user_message, bot_response)

# Webhook to handle Twilio messages
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    start_time = time.time()
    timeout = 4.5  # Timeout in seconds
    bot_reply = "Thanks for your message! Please wait while I process your request..."
    twilio_resp = MessagingResponse()

    # Get message data
    incoming_msg = request.values.get("Body", "").strip()
    sender = request.values.get("From", "")
    clean_sender = sender.replace("whatsapp:", "")
    image_url = request.values.get("MediaUrl0", None)

    try:
        # Enforce timeout
        enforce_timeout(start_time, timeout, sender, twilio_resp)

        # Retrieve existing memory
        memory = retrieve_user_memory(clean_sender)
        enforce_timeout(start_time, timeout, sender, twilio_resp)

        if not incoming_msg and not image_url:  # Handle empty message
            return str(twilio_resp)

        # Check for order mentions
        order_info = process_order_mentions(incoming_msg)
        order_id = order_info.get("order_number") if order_info else None

        # Process the query based on content
        if image_url:
            bot_reply = handle_customer_images(image_url)
        elif order_id:
            bot_reply = track_order(order_id)
        elif is_product_query(incoming_msg):
            bot_reply = process_product_query(incoming_msg)
        else:
            # Normal conversation with OpenAI
            messages = get_conversation_history(clean_sender, incoming_msg)
            enforce_timeout(start_time, timeout, sender, twilio_resp)

            try:
                for _ in range(3):  # Retry up to 3 times
                    try:
                        response = openai.chat.completions.create(
                            model="gpt-4",
                            messages=messages,
                            temperature=0.7,
                            timeout=120  # OpenAI API timeout
                        )
                        break
                    except openai.error.RateLimitError:
                        logging.warning("Rate limit reached. Retrying...")
                        time.sleep(2)  # Wait before retrying
                    except openai.error.APIConnectionError as e:
                        logging.error(f"OpenAI API Connection Error: {e}")
                        bot_reply = "I'm having trouble connecting to my brain right now. Please try again later!"
                        return str(twilio_resp.message(bot_reply))

                bot_reply = response.choices[0].message.content.strip()

                # Update conversation history
                updated_conversation = messages + [{"role": "assistant", "content": bot_reply}]
                update_user_memory(clean_sender, updated_conversation)
            except Exception as e:
                logging.error(f"OpenAI API Error: {e}")
                bot_reply = "I'm not sure how to respond to that right now. Could you please rephrase or ask something else?"

        twilio_resp.message(bot_reply)

    except Exception as e:
        logging.error(f"Unexpected error processing message: {e}")
        twilio_resp.message("Something went wrong on my end. Please try again later or contact support.")

    # Log the conversation after sending the response
    log_conversation(sender, incoming_msg, bot_reply)

    return str(twilio_resp)

# Main entry point for app
if __name__ == "__main__":
    # Initialize database with migration support
    init_db()

    # Clean old logs on startup
    clean_old_logs()

    # Pre-fetch products to warm the cache
    get_shopify_products()

    # Start ngrok and Flask
    public_url = ngrok.connect(5000)
    clean_public_url = str(public_url).replace('NgrokTunnel: "', '').split('" ->')[0]
    
    print(f"\n{'='*50}")
    print(f"Ngrok Public URL: {clean_public_url}")
    print(f"Twilio Webhook URL: {clean_public_url}/webhook")
    print(f"{'='*50}\n")

    logging.info(f"Ngrok public URL: {clean_public_url}")
    app.run(port=5000, debug=False)  # Set debug=False for stability