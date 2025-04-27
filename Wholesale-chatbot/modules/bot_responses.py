from typing import Optional, List, Dict
import random
import re
import logging
from functools import lru_cache
from config import config
import openai
import time
from logging_config import configure_logger
import asyncio

logger = configure_logger("bot_responses")

logger.info("Bot responses module loaded.")

PAYMENT_DETAILS = config.PAYMENT_DETAILS
APP_DETAILS = config.APP

# Configuration constants
MAX_HISTORY_LENGTH = 1000  # characters
MAX_HISTORY_MESSAGES = 6
REQUEST_TIMEOUT = 15  # seconds

# Load the smart state machine prompt
STATE_MACHINE_PROMPT = """
You are Grace, a friendly, persuasive, and human-sounding WhatsApp sales assistant for Atuche Woman wholesale fashion.

Your mission:
- Detect the user's current intent based on the latest message and conversation history.
- Choose the correct emotional tone (excited, playful, urgent, reassuring) to match the situation.
- Move the conversation forward toward closing a wholesale order (minimum 4 styles).

🚨 IMPORTANT: Your responses must ALWAYS include one (and only one) of these exact template keys enclosed in double brackets [[like_this]] at the beginning of the message:

[[greetings]], [[ask_for_designs]], [[package_details]], [[image_instructions]],
[[deposit_instructions]], [[payment_confirmed]], [[feedback_request]], 
[[handoff_to_manager]], [[default_response]], [[error_response]], [[funny_redirects]]

⚡️ Response Rules:
- Select the correct key based on the user's intent.
- After the key, write a short, warm, and action-focused message matching Nigerian business style: friendly slang ("love", "wahala", "o") and 1–3 emojis.
- Never invent new keys. Only use the provided ones.
- If user is stuck or confused, gently guide them toward picking designs, sending screenshots, or confirming payment.

📚 INTENT CLASSIFICATION:

Classify the user's current intent as one of:
- Asking for Catalog/Designs → use [[ask_for_designs]]
- Ready to Pick Styles → use [[ask_for_designs]] or [[image_instructions]]
- Confused/Needs Help → use [[default_response]] or [[error_response]]
- Stalling/Buying Time → use [[funny_redirects]] to refocus them
- Wants to Finalize Order → use [[deposit_instructions]] or [[payment_confirmed]]

🎭 EMOTIONAL TONE:

Choose tone based on user's vibe:
- Excited (if they're eager)
- Playful (if they’re friendly but slow)
- Urgent (if they’re delaying)
- Reassuring (if they’re confused or nervous)

💬 MESSAGE STRUCTURE:

Format every message like:
[[selected_key]] Natural, friendly reply here with emojis and slang.

EXAMPLES:
- [[greetings]] Hey love! Ready to create your perfect Ankara collection? 
- [[ask_for_designs]] Do you already have 4 designs picked out? If not, I'll send our catalog! 
- [[funny_redirects]] 😂 Focus o! Your profits are waiting for you! Which styles are you eyeing?

Always stay proactive, short, and friendly. Never sound robotic.
"""

class ResponseTemplates:
    """Class to manage bot responses for various scenarios."""

    WHOLESALE_RESPONSES = {
        "greetings": [
            "Hello love!  Ready to create your perfect Ankara collection?",
            "Hi gorgeous!  Let's design something amazing for your customers!",
            "Welcome back!  Shall we continue with your wholesale order?"
        ],
        "ask_for_designs": """
Do you already have 4 screenshots of the Ankara Dashiki (short-bubu) designs you like?

If yes, feel free to send them here.  
If not, no worries — just let me know and I'll send you our latest catalog! 
""",
        "package_details": f"""
📦 *PREMIUM WHOLESALE PACKAGE*:
- 4 designs, 40 pieces
- ₦{PAYMENT_DETAILS['total_amount']} (50% deposit)
- 10 working days delivery
- Includes: 4 videos + brand labels

After payment, we'll select your preferred prints!

Do you have 4 designs ready? If not, I'll send our catalog!
""",
        "image_instructions": """
📸 *How to Pick Designs*:
1. Send screenshots you love from our website/Instagram.
2. I'll confirm what's available.
3. If needed, I'll suggest close alternatives.
4. You'll get a final price summary!
""",
        "image_processing": "🔍*Processing Your Images*...",
        "image_received": "Image received! Checking availability... (Please give me 20 seconds!)",
        "image_not_found": "This design isn't in our current wholesale package. Here are similar available options:",
        "selection_confirmation": "You've selected: {items}. Total: ₦{total}. Reply *CONFIRM* to lock it in or send more screenshots!",
        "deposit_instructions": f"""
💳 *Payment Details*:
Bank: {PAYMENT_DETAILS['bank_name']}
Account No: {PAYMENT_DETAILS['account_number']}
Account Name: {PAYMENT_DETAILS['account_name']}

✅ After payment:
- Send proof here.
- Confirmation within 1 hour.
- Then we pick your prints!
""",
        "accountant_alert": """
🔄 *Payment Verification Needed*
Customer: {customer_name} ({phone})
Amount: ₦{amount}
Time: {timestamp}

Reply CONFIRM-{shortcode} to verify""",
        "payment_confirmed": """
✅ *Payment Verified*
Your deposit has been confirmed! Now let's select your prints.
""",
        "feedback_request": """
Thank you for your order! 🙌 Could you please share your feedback on how I did? Your input helps us improve. 😊
""",
        "handoff_to_manager": """
Your order is now with our Operations Manager! 🚀 They'll make sure everything runs smoothly. Thank you for choosing Atuche Woman! 💖
""",
        "default_response": "Hey love! 💖 How can I assist with your wholesale order today?",
        "error_response": "Oops! Something went wrong on my end. Could you please try again?",
        "funny_redirects": [
            "😂 Focus o! Let's get your Ankara money-making designs sorted first! Which design caught your eye?",
            "😉 I'll tell you after we confirm your deposit! Now, should I save the 4pm production slot for you?",
            "🌊 Fun fact: The Nile has great design patterns! Want to see similar prints for your order?",
            "💰 The river of profits you'll make from these designs! Ready to finalize your 4 styles?"
        ],
    }

    def __init__(self):
        self.ai_phrases = [
            "as a language model",
            "openai",
            "AI assistant",
            "I'm an AI",
            "I'm a chatbot",
            "I am not a human",
            "I was trained",
            "I cannot",
            "I am not capable"
        ]
        self.ai_phrases_pattern = re.compile(r"|".join(map(re.escape, self.ai_phrases)))
        self.key_pattern = re.compile(r"\[\[(.*?)\]\]")

        # Pre-compile positive and negative patterns
        self.positive_patterns = [
            re.compile(r"\b(yes|yeah|yep|sure|of course|i have|i've got|ready|i'm ready|all set)\b", re.IGNORECASE)
        ]
        self.negative_patterns = [
            re.compile(r"\b(no|nope|nah|not yet|don't have|send catalog|need catalog|haven't)\b", re.IGNORECASE)
        ]

    def get_greeting(self, name: Optional[str] = None) -> str:
        """Return a personalized greeting."""
        greeting = random.choice(self.WHOLESALE_RESPONSES["greetings"])
        if name:
            return f"{greeting} What would you like to do today, {name}?"
        return f"{greeting} Should I show you our best-selling designs?"

    @lru_cache(maxsize=32)
    def get_response(self, key: str, **kwargs) -> str:
        """Return a formatted response based on the key."""
        logger.debug(f"Generating response for key: {key} with kwargs: {kwargs}")
        if key not in self.WHOLESALE_RESPONSES:
            logger.warning(f"Response key '{key}' not found. Using default response.")
            key = "default_response"
        
        response = self.WHOLESALE_RESPONSES[key]
        if isinstance(response, list):
            response = random.choice(response)
        
        try:
            return response.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing variable in response formatting: {e}")
            return self.WHOLESALE_RESPONSES["error_response"]

    def extract_response_key(self, ai_output: str) -> str:
        """Extract and validate the response key from AI output."""
        match = self.key_pattern.search(ai_output)
        if match:
            key = match.group(1)
            if key in self.WHOLESALE_RESPONSES:
                return key
            if not match:
                logger.warning(f"No key found in AI output: {ai_output}")
            elif key not in self.WHOLESALE_RESPONSES:
                logger.warning(f"Unrecognized key extracted: {key}")
                return "default_response"

    def clean_response(self, response: str) -> str:
        """Remove AI-related phrases from the response."""
        return self.ai_phrases_pattern.sub("", response).strip()
    
def format_conversation(history: List[Dict[str, str]]) -> str:
    safe_history = []
    for msg in history[-MAX_HISTORY_MESSAGES:]:
        if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
            safe_history.append(f"{msg['role']}: {msg['content']}")
    conversation = "\n".join(safe_history)
    return conversation[-MAX_HISTORY_LENGTH:]  # Auto-truncate


async def generate_grace_response(history: List[Dict[str, str]], latest_user_message: str) -> str:
    """
    Generate a response for Grace using OpenAI's GPT model.

    Args:
        history (List[Dict[str, str]]): The conversation history.
        latest_user_message (str): The latest message from the user.

    Returns:
        str: The generated response.
    """
    logger.debug(f"Generating response for user message: {latest_user_message}")
    start_time = time.time()

    templates = ResponseTemplates()
    try:
        # Prepare conversation text
       # Prepare conversation context safely
        formatted_history = format_conversation(history)

        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[
                {"role": "system", "content": STATE_MACHINE_PROMPT},
                {"role": "user", "content": f"{formatted_history}\n\nUser: {latest_user_message}"}
            ],
            temperature=0.7,
            max_tokens=150,
            request_timeout=REQUEST_TIMEOUT
        )
        
        ai_output = response.choices[0].message.content
        logger.debug(f"Raw AI output: {ai_output}")
        
        # Extract and return the proper template
        response_key = templates.extract_response_key(ai_output)
        formatted_response = templates.get_response(response_key)
        
        logger.info(f"Response generated in {time.time()-start_time:.2f}s")
        return templates.clean_response(formatted_response)
        
    except openai.error.RateLimitError:
        logger.error("OpenAI rate limit exceeded")
        return templates.get_response("error_response")
    except asyncio.TimeoutError:
        logger.error(f"OpenAI API error: {e}")
        return "Network wahala o 😓! Please give me 5 minutes and let's try again love!"
    except Exception as e:
        logger.error(f"Unexpected error in generate_grace_response: {str(e)}", exc_info=True)
        return templates.get_response("error_response")
   