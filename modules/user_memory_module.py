import aiosqlite
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
import re
import logging
import os
import aiofiles
import asyncio
from logging_config import configure_logger

logger = configure_logger("user_memory_module")

class UserMemory:
    def __init__(self, sender: str):
        """Initialize user memory with async capabilities"""
        self.sender = sender
        self.db_path = 'memory.db'
        self.lock = asyncio.Lock()

    async def get_last_bot_message(self) -> str:
        """Retrieve the last bot message asynchronously"""
        memory = await self.get_memory()
        return memory.get("last_bot_message", "")

    async def save_last_bot_message(self, message: str) -> None:
        """Save the last bot message with async locking"""
        async with self.lock:
            memory = await self.get_memory()
            memory["last_bot_message"] = message
            await self._save_memory(memory)

    async def save_memory(self, **kwargs) -> None:
        """Async save with proper transaction handling"""
        async with self.lock:
            memory = await self.get_memory()
            memory.update({
                'name': kwargs.get('name', memory.get('name')),
                'conversation_history': kwargs.get('conversation', memory.get('conversation_history', [])),
                'preferences': {**memory.get('preferences', {}), **kwargs.get('preferences', {})},
                'last_order': kwargs.get('last_order', memory.get('last_order'))
            })
            await self._save_memory(memory)

    async def _save_memory(self, memory: Dict) -> None:
        """Internal async save operation"""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute('''
                    INSERT OR REPLACE INTO user_memory 
                    (sender, name, conversation_history, preferences, last_order, last_interaction)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    self.sender,
                    memory.get('name'),
                    json.dumps(memory.get('conversation_history', [])),
                    json.dumps(memory.get('preferences', {})),
                    memory.get('last_order'),
                    datetime.now().isoformat()
                ))
                await conn.commit()
        except Exception as e:
            logger.error(f"Async save failed: {str(e)}")
            raise

    async def get_memory(self) -> Dict[str, Any]:
        """Retrieve user memory asynchronously"""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.execute('''
                    SELECT name, conversation_history, preferences, last_order 
                    FROM user_memory WHERE sender = ?
                ''', (self.sender,))
                result = await cursor.fetchone()

            if result:
                return {
                    'name': result[0],
                    'conversation_history': json.loads(result[1]) if result[1] else [],
                    'preferences': json.loads(result[2]) if result[2] else {},
                    'last_order': result[3]
                }
            return {}
        except Exception as e:
            logger.error(f"Async get_memory failed: {str(e)}")
            return {}

    async def save_name(self, name: str) -> None:
        """Async save user's name to database"""
        sanitized_name = self.sanitize_input(name)
        if not sanitized_name:
            logger.warning(f"Invalid name attempt from {self.sender}: {name}")
            return
    
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute('''
                    INSERT OR REPLACE INTO user_memory 
                    (sender, name, last_interaction)
                    VALUES (?, ?, ?)
                ''', (self.sender, sanitized_name, datetime.now().isoformat()))
                await conn.commit()
            logger.info(f"Saved name for {self.sender}: {sanitized_name}")
        except Exception as e:
            logger.error(f"Failed to save name for {self.sender}: {str(e)}")
            raise

    @staticmethod
    def sanitize_input(text: str) -> str:
        """Security: Clean user input"""
        return re.sub(r"[^\w\s@#\-.,₦]", "", text)[:500]

    @staticmethod
    def extract_name(message: str) -> Optional[str]:
        """Extract Nigerian-style names"""
        patterns = [
            r"(my name|name) (don be|na) (\w+)",  # Pidgin patterns
            r"(call me|i dey) (\w+)",
            r"^(\w+)\s*(here|dey)$",
            r"na (\w+) i be",  # Additional Nigerian Pidgin pattern
            r"make you call me (\w+)"  # Common Nigerian request format
        ]
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(match.lastindex).strip().title()
        return None

    @staticmethod
    async def check_connection() -> bool:
        """Async connection check"""
        try:
            async with aiosqlite.connect('memory.db') as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Connection check failed: {str(e)}")
            return False

async def validate_and_migrate_schema():
    """Async schema validation and migration"""
    expected_columns = {
        "sender": "TEXT PRIMARY KEY",
        "name": "TEXT",
        "conversation_history": "TEXT",
        "preferences": "TEXT",
        "last_order": "TEXT",
        "last_interaction": "TIMESTAMP"
    }

    try:
        async with aiosqlite.connect('memory.db') as conn:
            # Check table existence
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='user_memory'"
            )
            if not await cursor.fetchone():
                columns = ", ".join([f"{col} {dtype}" for col, dtype in expected_columns.items()])
                await conn.execute(f"CREATE TABLE user_memory ({columns})")
                logger.info("Created user_memory table")
                await conn.commit()
                return

            # Check columns
            cursor = await conn.execute("PRAGMA table_info(user_memory)")
            existing_columns = {row[1]: row[2] async for row in cursor}

            # Add missing columns
            for col, dtype in expected_columns.items():
                if col not in existing_columns:
                    await conn.execute(f"ALTER TABLE user_memory ADD COLUMN {col} {dtype}")
                    logger.info(f"Added column {col}")
            
            await conn.commit()
    except Exception as e:
        logger.error(f"Schema migration failed: {str(e)}")

async def build_conversation_history(sender: str) -> List[Dict[str, str]]:
    """Async conversation history builder"""
    clean_sender = sender.replace("whatsapp:", "")
    log_file = f"logs/{clean_sender}_chat_history.json"

    if not os.path.exists(log_file):
        logger.info(f"No history for {clean_sender}")
        return []

    try:
        async with aiofiles.open(log_file, "r", encoding="utf-8") as f:
            content = await f.read()
            # Ensure the content is parsed as JSON and returned as a list
            return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON for {clean_sender}: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"History error for {clean_sender}: {str(e)}")
        return []