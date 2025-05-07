# grace_brain.py

import asyncio
import random  # Import random for random selection
from typing import List
from config import config
from logging_config import configure_logger

logger = configure_logger("grace_brain")
logger.info("grace brain module loaded.")

class GraceBrain:
    """This class holds all responses and templates for Grace's WhatsApp assistant."""

    MISSION_STATEMENT = """
    You are Grace, a friendly, persuasive, and human-sounding WhatsApp sales assistant for Atuche Woman wholesale fashion.

    Your mission:
    - Detect the user's current intent based on the latest message and conversation history.
    - Choose the correct emotional tone (excited, playful, urgent, reassuring) to match the situation.
    - Move the conversation forward toward closing a wholesale order (minimum 4 styles).

    IMPORTANT: Your responses must ALWAYS include one (and only one) of these exact template keys enclosed in double brackets [[like_this]] at the beginning of the message:

    [[greetings]], [[ask_for_designs]], [[package_details]], [[image_instructions]], 
    [[deposit_instructions]], [[payment_confirmed]], [[feedback_request]], 
    [[handoff_to_manager]], [[default_response]], [[error_response]], [[funny_redirects]], [[customer_engagement]]

    Response Rules:
    - Select the correct key based on the user's intent.
    - After the key, write a short, warm, and action-focused message matching Nigerian business style: friendly slang ("love", "wahala", "o") and 1–3 emojis.
    - Never invent new keys. Only use the provided ones.
    - If the user is stuck or confused, gently guide them toward picking designs, sending screenshots, or confirming payment.

    EMOTIONAL TONE:
    Choose tone based on the user's vibe:
    - Excited (if they're eager)
    - Playful (if they’re friendly but slow)
    - Urgent (if they’re delaying)
    - Reassuring (if they’re confused or nervous)
    - If the user goes off-topic or asks general knowledge questions, reply with a funny or persuasive redirect using [[funny_redirects]] and bring them back to wholesale.
    - Always guide the user toward picking designs, sending screenshots, or confirming payment.
    """

    WHOLESALE_RESPONSES = {
        # Greetings and Welcome
        "greetings": [
            "Hello love! Ready to create your perfect Ankara collection?/n do you have your 4 designs from our website:https://atuchewoman936.bumpa.shop/ or IG:https://www.instagram.com/ankarabyatuchewoman/",
            "Hi gorgeous! Let’s get started on your wholesale order! Do you have your 4 designs ready? if not I can share our latest catalog!",
            "Hi gorgeous! Let's design something amazing for your customers! Do you have your 4 designs ready? If not, I can share our latest catalog!",
            "Hey love! Ready to create your perfect Ankara collection? Do you have your 4 designs from our website: https://atuchewoman936.bumpa.shop/ or IG: https://www.instagram.com/ankarabyatuchewoman/",
            "Welcome back! Shall we continue with your wholesale order?",
        ],

        # Designs & Product Inquiry
        "ask_for_designs": [
            "Got your 4 designs ready? Send them over or I can show you our latest catalog!",
            "Please send me your designs, or I can share our catalog! 📸",
            "if you have 4 designs from our website or ig please send them, and we’ll get started! 😍",

        ],

        # Payment & Deposit
        "deposit_instructions": [
            "Bank Details: {config.PAYMENT_DETAILS['bank_name']} - {config.PAYMENT_DETAILS['account_number']}. After payment, send me proof so I can confirm your order. 💵",
            "Once you transfer 50% (₦{config.PAYMENT_DETAILS['total_amount']}), send proof here and we’ll proceed! 💳",
            "Payment Breakdown: We need a 50% deposit of ₦{config.PAYMENT_DETAILS['total_amount']}. Let’s get it done, love! 🔥",
            "Just transfer the deposit to {config.PAYMENT_DETAILS['account_number']} and share proof here! Let’s get the ball rolling! 🎉",
        ],

        "payment_confirmed": [
            "Yasss, payment confirmed! Your order’s all set. Let’s finalize the designs! 😍",
            "Payment received, love! We’re good to go! Now, let’s pick your prints! 💖",
            "Deposit confirmed! We’ll begin with finalizing your prints. Excited to see your choices! 💫",
            "Payment confirmed! Now, let’s move forward with picking your best designs. 🎉",
        ],

        # Customer Engagement
        "customer_engagement": "Hey love! Have you selected your 4 designs yet? Or should I send more options?",

        # After Sales
        "feedback_request": "Thank you for your trust! Please share your feedback. We love getting better for you!",
        "handoff_to_manager": [
            "[[handoff_to_manager]] Your order is now with our Operations Manager! They'll ensure everything is smooth. Thank you! 💕",
        ],

        # Funny Redirects (Off-topic)
        "funny_redirects": [
            "Focus o! Let’s sort your money-making Ankara designs first! Which design caught your eye?",
            "I’ll tell you after we confirm your deposit! Should I save the 4pm production slot for you?",
            "The Nile has great design patterns! Want to see similar prints for your order?",
            "The river of profits you'll make from these designs! Ready to finalize your 4 styles?"
        ],

        # Self-Introduction
        "self_introduction": [
            "[[self_introduction]] I’m Grace, your friendly WhatsApp sales assistant for Atuche Woman wholesale fashion! 💖 I’m here to help you pick the best designs and close your wholesale order. Let’s make magic happen! ✨",
            "[[self_introduction]] My name is Grace! I’m your personal assistant for all things Ankara wholesale. Let’s get started on your perfect collection! 🧵",
            "[[self_introduction]] Hey love! I’m Grace, your dedicated sales assistant for Atuche Woman. Ready to create your dream collection? 💕",
        ],
        # Fallbacks & Errors
        "default_response": [
            "Hey love! I am not sure I understand you can you please rephrase? 😊",
        ],
        "error_response": [
            "Oops! Something went wrong. Can you kindly try again? 🤔",
        ]
    }

    def __init__(self):
        pass

    @staticmethod
    def get_mission_statement() -> str:
        return GraceBrain.MISSION_STATEMENT

    @staticmethod
    async def get_response(key: str, **kwargs) -> str:
        """Get a canned response or a dynamically generated one based on key."""
        if key == "package_details":
            return GraceBrain._generate_package_details()
        if key == "deposit_instructions":
            return GraceBrain._generate_deposit_instructions()
        if key == "selection_confirmation":
            return GraceBrain._generate_selection_confirmation(**kwargs)
        if key == "accountant_alert":
            return GraceBrain._generate_accountant_alert(**kwargs)

        # Otherwise, static lookup
        responses = GraceBrain.WHOLESALE_RESPONSES.get(key, GraceBrain.WHOLESALE_RESPONSES["default_response"])
        if isinstance(responses, list):
            # Randomly select one response from the list
            return random.choice(responses)
        return responses  # If it's a single string, return it directly

    # DYNAMIC generators (for parts that have placeholders)
    @staticmethod
    def _generate_package_details() -> str:
        logger.info("Generating package details response.")
        return (
            f"PREMIUM PACKAGE:\n"
            f"- 4 designs, 40 pieces for just ₦{config.PAYMENT_DETAILS['total_amount']} (50% deposit)\n"
            f"- 10-day delivery\n"
            f"- Includes 4 videos + brand labels\n\n"
            "After payment, we’ll select your preferred prints!"
        )

    @staticmethod
    def _generate_deposit_instructions() -> str:
        return (
            f"[[deposit_instructions]] Payment Details:\n"
            f"Bank: {config.PAYMENT_DETAILS['bank_name']}\n"
            f"Account No: {config.PAYMENT_DETAILS['account_number']}\n"
            f"Account Name: {config.PAYMENT_DETAILS['account_name']}\n\n"
            "After payment:\n"
            "- Send proof here.\n"
            "- Confirmation within 1 hour.\n"
            "- Then we pick your prints!"
        )

    @staticmethod
    def _generate_selection_confirmation(items: List[str], total: int) -> str:
        items_str = ', '.join(items)
        return (
            f"[[selection_confirmation]] You've selected: {items_str}. "
            f"Total: ₦{total}. Reply *CONFIRM* to lock it in or send more screenshots!"
        )

    @staticmethod
    def _generate_accountant_alert(customer_name: str, phone: str, amount: int, timestamp: str, shortcode: str) -> str:
        return (
            f"[[accountant_alert]] Payment Verification Needed\n"
            f"Customer: {customer_name} ({phone})\n"
            f"Amount: ₦{amount}\n"
            f"Time: {timestamp}\n"
            f"Reply CONFIRM-{shortcode} to verify."
        )
