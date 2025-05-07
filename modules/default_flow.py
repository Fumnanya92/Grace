import json
import os
import logging
from typing import Optional
from config import config

logger = logging.getLogger("GraceFlowManager")


class GraceFlowManager:
    """
    Tracks default sales flow for each customer using step-based progression.
    """

    FLOW_SEQUENCE = [
        {
            "step": "greetings",
            "message": "Hey love! Welcome 💕 Ready to build your Ankara collection? Check out our catalog on IG: {ig_link} or website: {shop_link}"
        },
        {
            "step": "package_details",
            "message": "Here's what you get with our PREMIUM PACKAGE:\n\n"
                       "- 4 Designs (40 pieces)\n"
                       "- 10-day Delivery\n"
                       "- 4 Promo Videos + Branded Labels\n\n"
                       "Total: ₦{total_amount} (50% deposit to start)."
        },
        {
            "step": "ask_for_designs",
            "message": "Have you picked your 4 designs yet? If not, I can show you our latest catalog. 📸"
        },
        {
            "step": "deposit_instructions",
            "message": "Once you're ready, make a 50% deposit to:\n\n"
                       "{bank_name} - {account_number}\n"
                       "Account Name: {account_name}\n\n"
                       "Send your payment screenshot here and we’ll get started! 💳"
        },
        {
            "step": "payment_confirmed",
            "message": "Payment confirmed! 🎉 Let's pick your final prints and lock in your delivery slot."
        },
        {
            "step": "design_review",
            "message": "Got your screenshots! 👀 Give me a moment to check availability. I’ll get right back to you."
        },
        {
            "step": "confirm_selection",
            "message": "Perfect! You picked: {{designs_list}}.\nPlease note that delivery will take 10 working days. Now, shall we discuss the prints?"
        },
        {
            "step": "handoff_to_manager",
            "message": "[[handoff_to_manager]] Handing off to the operations team 📦\nThey’ll discuss the prints with you. Thank you for choosing us, love! 💕"
        }
    ]

    def __init__(self, store_path: str = None):
        self.store_path = store_path or config.APP.get("flow_store_path", "flow_progress.json")
        self._store = self._load()

    def _load(self):
        """Load the flow progress from the JSON file."""
        if os.path.exists(self.store_path):
            with open(self.store_path, "r") as f:
                logger.info(f"Loading flow progress from {self.store_path}")
                return json.load(f)
        logger.warning(f"No flow progress file found at {self.store_path}. Starting fresh.")
        return {}

    def _save(self):
        """Save the flow progress to the JSON file."""
        with open(self.store_path, "w") as f:
            json.dump(self._store, f)
            logger.info(f"Flow progress saved to {self.store_path}")

    def get_next_step(self, phone: str) -> Optional[dict]:
        current_index = self._store.get(phone, -1) + 1
        if current_index < len(self.FLOW_SEQUENCE):
            self._store[phone] = current_index
            self._save()

            step_data = self.FLOW_SEQUENCE[current_index].copy()
            step_data["message"] = step_data["message"].format(
                ig_link=config.SOCIAL_LINKS["instagram"],
                shop_link=config.SOCIAL_LINKS["shop_link"],
                bank_name=config.PAYMENT_DETAILS["bank_name"],
                account_number=config.PAYMENT_DETAILS["account_number"],
                account_name=config.PAYMENT_DETAILS["account_name"],
                total_amount=config.PAYMENT_DETAILS["total_amount"]
        )
            return step_data    
        logger.info(f"Customer {phone} has completed the flow.")
        return {"step": "end", "message": "Thank you for completing the process! Let us know if you need further assistance."}

    def reset_flow(self, phone: str):
        """Reset the flow for a given phone number."""
        self._store[phone] = -1
        self._save()
        logger.info(f"Flow reset for customer {phone}")

    def validate_phone(phone: str):
        if not phone.isdigit() or len(phone) < 10:
            raise ValueError(f"Invalid phone number: {phone}")
