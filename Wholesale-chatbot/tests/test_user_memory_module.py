import unittest
import sqlite3
import os
from unittest.mock import patch
from modules.user_memory_module import save_memory, get_memory, validate_and_migrate_schema

class TestUserMemoryModule(unittest.TestCase):
    def setUp(self):
        """Set up a temporary database for testing."""
        self.db_path = f"test_memory_{os.getpid()}.db"  # Use process ID to create a unique path
        self.conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = self.conn.cursor()
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
        self.conn.commit()

    def tearDown(self):
        """Clean up the temporary database."""
        self.conn.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_save_and_get_memory(self):
        """Test saving and retrieving user memory."""
        sender = "whatsapp:+1234567890"
        name = "John"
        conversation = [{"role": "user", "content": "Hello"}]
        preferences = {"language": "English"}
        last_order = "Order123"

        save_memory(sender, name, conversation, preferences, last_order)

        # Verify the data was saved
        memory = get_memory(sender)
        self.assertEqual(memory['name'], name)
        self.assertEqual(memory['conversation_history'], conversation)
        self.assertEqual(memory['preferences'], preferences)
        self.assertEqual(memory['last_order'], last_order)

    def test_save_memory_duplicate(self):
        """Test saving memory for the same sender multiple times."""
        sender = "whatsapp:+1234567890"
        save_memory(sender, name="John")
        save_memory(sender, name="Jane")  # Update the name

        memory = get_memory(sender)
        self.assertEqual(memory['name'], "Jane")  # Ensure the name is updated

    def test_get_memory_non_existent(self):
        """Test retrieving memory for a non-existent sender."""
        memory = get_memory("whatsapp:+9876543210")
        self.assertEqual(memory, {})  # Should return an empty dictionary

    def test_save_memory_invalid_data(self):
        """Test saving memory with invalid data."""
        sender = "whatsapp:+1234567890"
        with self.assertRaises(TypeError):
            save_memory(sender, conversation="Invalid data")  # Conversation should be a list

    def test_validate_and_migrate_schema(self):
        """Test schema validation and migration."""
        validate_and_migrate_schema()
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(user_memory)")
        columns = {col[1]: col[2] for col in cursor.fetchall()}  # Map column names to data types

        self.assertIn("conversation_history", columns)
        self.assertEqual(columns["conversation_history"], "TEXT")
        self.assertIn("preferences", columns)
        self.assertEqual(columns["preferences"], "TEXT")

    @patch("modules.user_memory_module.sqlite3.connect")
    def test_save_memory_database_error(self, mock_connect):
        """Test handling of database errors in save_memory."""
        mock_connect.side_effect = sqlite3.Error("Database error")
        with self.assertRaises(sqlite3.Error):
            save_memory("whatsapp:+1234567890", name="John")

    @patch("modules.user_memory_module.sqlite3.connect")
    def test_get_memory_database_error(self, mock_connect):
        """Test handling of database errors in get_memory."""
        mock_connect.side_effect = sqlite3.Error("Database error")
        memory = get_memory("whatsapp:+1234567890")
        self.assertEqual(memory, {})  # Should return an empty dictionary

if __name__ == "__main__":
    unittest.main()