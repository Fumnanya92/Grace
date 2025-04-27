import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any
import re
import logging
import os
import json
from typing import List, Dict

logging.basicConfig(level=logging.INFO)

class UserMemory:
    def __init__(self, sender):
        self.sender = sender
        self.memory = {}  # Replace with actual database or storage logic

    def get_last_bot_message(self):
        """Retrieve the last bot message sent to the user."""
        return self.memory.get(self.sender, {}).get("last_bot_message", "")

    def save_last_bot_message(self, message):
        """Save the last bot message sent to the user."""
        if self.sender not in self.memory:
            self.memory[self.sender] = {}
        self.memory[self.sender]["last_bot_message"] = message

    def save_memory(self, name: Optional[str] = None, conversation: Optional[list] = None,
             preferences: Optional[dict] = None, last_order: Optional[str] = None) -> None:
        """Save user memory to the database."""
        try:
            with sqlite3.connect('memory.db', detect_types=sqlite3.PARSE_DECLTYPES) as conn:
                cursor = conn.cursor()
                existing = self.get_memory()
                updated_name = name or (existing['name'] if existing else None)
                updated_conversation = conversation or (existing['conversation_history'] if existing else [])
                updated_preferences = {**(existing['preferences'] if existing else {}), **(preferences or {})}
                updated_order = last_order or (existing['last_order'] if existing else None)

                cursor.execute('''
                    INSERT OR REPLACE INTO user_memory 
                    (sender, name, conversation_history, preferences, last_order, last_interaction)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (self.sender, updated_name, json.dumps(updated_conversation), json.dumps(updated_preferences), updated_order, datetime.now()))
                conn.commit()
        except sqlite3.Error as e:
            print(f"Database error while saving memory: {e}")

    def get_memory(self) -> Optional[Dict[str, Any]]:
        """Retrieve user memory from the database."""
        try:
            with sqlite3.connect('memory.db', detect_types=sqlite3.PARSE_DECLTYPES) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT name, conversation_history, preferences, last_order 
                    FROM user_memory WHERE sender = ?
                ''', (self.sender,))
                result = cursor.fetchone()

            if result:
                return {
                    'name': result[0],
                    'conversation_history': json.loads(result[1]) if result[1] else [],
                    'preferences': json.loads(result[2]) if result[2] else {},
                    'last_order': result[3]
                }
            return {}
        except sqlite3.Error as e:
            print(f"Database error while retrieving memory: {e}")
            return {}
    def save_name(self, name):
        """Save the user's name."""
        if self.sender not in self.memory:
            self.memory[self.sender] = {}
        self.memory[self.sender]['name'] = name

    @staticmethod
    def sanitize_input(text: str) -> str:
        """Remove special chars and limit length for security."""
        cleaned = re.sub(r"[^\w\s@#\-.,₦]", "", text)
        return cleaned[:500]

    @staticmethod
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

    @staticmethod
    def check_connection() -> bool:
        """Check if the database connection is active."""
        try:
            with sqlite3.connect('memory.db') as conn:
                conn.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

def validate_and_migrate_schema():
    """Ensure the user_memory table schema matches the expected structure."""
    expected_columns = {
        "sender": "TEXT PRIMARY KEY",
        "name": "TEXT",
        "conversation_history": "TEXT",
        "preferences": "TEXT",
        "last_order": "TEXT",
        "last_interaction": "TIMESTAMP"
    }

    try:
        with sqlite3.connect('memory.db', detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            cursor = conn.cursor()
            
            # Check if the table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_memory'")
            if not cursor.fetchone():
                # Create the table if it doesn't exist
                columns = ", ".join([f"{col} {dtype}" for col, dtype in expected_columns.items()])
                cursor.execute(f"CREATE TABLE user_memory ({columns})")
                logging.info("Created user_memory table.")
                conn.commit()
                return
            
            # Check existing columns
            cursor.execute("PRAGMA table_info(user_memory)")
            existing_columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            # Add missing columns
            for column, dtype in expected_columns.items():
                if column not in existing_columns:
                    cursor.execute(f"ALTER TABLE user_memory ADD COLUMN {column} {dtype}")
                    logging.info(f"Added missing column: {column} ({dtype})")
            
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Error validating schema: {e}")

def build_conversation_history(sender: str) -> List[Dict[str, str]]:
    """
    Retrieve and format the conversation history for a specific customer.

    Args:
        sender (str): The sender's phone number (e.g., "+2347082229034").

    Returns:
        List[Dict[str, str]]: A list of conversation entries, each containing
                              timestamp, user_message, and bot_reply.
    """
    clean_sender = sender.replace("whatsapp:", "")
    log_file = f"logs/{clean_sender}_chat_history.json"

    if not os.path.exists(log_file):
        logging.info(f"No conversation history found for {clean_sender}.")
        return []

    try:
        with open(log_file, "r", encoding="utf-8") as file:
            history = json.load(file)
            logging.info(f"Retrieved conversation history for {clean_sender}.")
            return history
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON for {clean_sender}: {e}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error retrieving history for {clean_sender}: {e}")
        return []
