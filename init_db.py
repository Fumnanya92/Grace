import sqlite3
import logging
from datetime import datetime

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
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    sender TEXT PRIMARY KEY,
                    deposit_paid BOOLEAN DEFAULT 0,
                    payment_proof TEXT,
                    payment_date TIMESTAMP,
                    verification_code TEXT,
                    FOREIGN KEY (sender) REFERENCES user_memory(sender)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS design_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT,
                    s3_path TEXT,
                    submission_time TIMESTAMP,
                    FOREIGN KEY (sender) REFERENCES user_memory(sender)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS design_catalog (
                    design_id TEXT PRIMARY KEY,
                    name TEXT,
                    price REAL,
                    s3_key TEXT,
                    in_stock BOOLEAN DEFAULT 1,
                    wholesale_eligible BOOLEAN DEFAULT 1
                )
            ''')
            conn.commit()
    except Exception as e:
        logging.error(f"Error initializing database: {e}")
