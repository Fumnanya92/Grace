import os
import logging
import json
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())

class Config:
    """Central configuration class for all application settings."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Config, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        # Validate configurations
        self._validate_twilio_config()
        self._validate_aws_config()
        self._validate_openai_config()
        self._validate_shopify_config()
        self._ensure_database_file()
        self._load_business_config()

        # Add direct attributes for frequently accessed credentials
        self.TWILIO_ACCOUNT_SID = self.TWILIO["account_sid"]
        self.TWILIO_AUTH_TOKEN = self.TWILIO["auth_token"]
        self.AWS_ACCESS_KEY = self.AWS["access_key"]
        self.AWS_SECRET_KEY = self.AWS["secret_key"]
        self.OPENAI_API_KEY = self.OPENAI["api_key"]

    # ---------------------------------------------------------------------
    # Twilio/WhatsApp Configuration
    # ---------------------------------------------------------------------
    TWILIO: Dict[str, str] = {
        "account_sid": os.getenv("TWILIO_ACCOUNT_SID"),
        "auth_token": os.getenv("TWILIO_AUTH_TOKEN"),
        "whatsapp_number": os.getenv("WHATSAPP_NUMBER", "whatsapp:+14155238886"),
    }

    # ---------------------------------------------------------------------
    # Database Configuration
    # ---------------------------------------------------------------------
    DATABASE: Dict[str, Any] = {
        "path": os.getenv("DB_PATH", "data/memory.db"),
        "tables": {
            "users": "user_memory",
            "payments": "payments",
            "designs": "design_submissions",
        },
    }

    DATA_DIR = "data"  # Directory for database files

    # ---------------------------------------------------------------------
    # AWS S3 Configuration
    # ---------------------------------------------------------------------
    AWS: Dict[str, str] = {
        "access_key": os.getenv("AWS_ACCESS_KEY_ID"),
        "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
        "region": os.getenv("AWS_REGION", "us-east-1"),
        "bucket": os.getenv("S3_BUCKET_NAME", "default-bucket"),
        "designs_folder": os.getenv("S3_WHOLESALE_PIC", "designs/"),
    }

    # ---------------------------------------------------------------------
    # OpenAI Configuration
    # ---------------------------------------------------------------------
    OPENAI: Dict[str, Any] = {
        "api_key": os.getenv("OPENAI_API_KEY"),
        "model": os.getenv("OPENAI_MODEL", "gpt-4"),
        "temperature": float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
    }

    # ---------------------------------------------------------------------
    # Shopify Configuration
    # ---------------------------------------------------------------------
    SHOPIFY: Dict[str, str] = {
        "api_key": os.getenv("SHOPIFY_API_KEY"),
        "password": os.getenv("SHOPIFY_PASSWORD"),
        "store_name": os.getenv("SHOPIFY_STORE_NAME"),
    }

    # ---------------------------------------------------------------------
    # Application Settings
    # ---------------------------------------------------------------------
    APP: Dict[str, Any] = {
        "debug": os.getenv("DEBUG", "False").lower() == "true",
        "port": int(os.getenv("PORT", "8000")),
        "ngrok_auth_token": os.getenv("NGROK_AUTH_TOKEN"),
        "log_days_to_keep": int(os.getenv("LOG_DAYS_TO_KEEP", "7")),
        "default_image_link": os.getenv(
            "DEFAULT_IMAGE_LINK", "https://example.com/catalog"
        ),
    }

    # ---------------------------------------------------------------------
    # Validation Methods
    # ---------------------------------------------------------------------
    def _validate_twilio_config(self):
        """Validate Twilio configuration."""
        if not self.TWILIO["account_sid"] or not self.TWILIO["auth_token"]:
            logging.error("Twilio credentials are missing in the environment variables.")
            raise ValueError("Twilio credentials are required.")

    def _validate_aws_config(self):
        """Validate AWS S3 configuration."""
        if not self.AWS["access_key"] or not self.AWS["secret_key"]:
            logging.error("AWS credentials are missing in the environment variables.")
            raise ValueError("AWS credentials are required.")

    def _validate_openai_config(self):
        """Validate OpenAI configuration."""
        if not self.OPENAI["api_key"]:
            logging.error("OpenAI API key is missing in the environment variables.")
            raise ValueError("OpenAI API key is required.")

    def _validate_shopify_config(self):
        """Validate Shopify configuration."""
        if not self.SHOPIFY["api_key"] or not self.SHOPIFY["password"] or not self.SHOPIFY["store_name"]:
            logging.error("Shopify credentials are missing in the environment variables.")
            raise ValueError("Shopify credentials are required.")

    def _ensure_database_file(self):
        """Ensure the database file exists."""
        db_path = self.DATABASE["path"]
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        if not os.path.exists(db_path):
            open(db_path, "w").close()  # Create an empty file
            logging.warning(f"Database file created at: {db_path}")

    def _load_business_config(self):
        """Load business configuration from a JSON file."""
        config_path = Path("config/config.json")
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Dynamically set all keys from config.json as uppercase attributes
                for key, value in data.items():
                    setattr(self, key.upper(), value)
        else:
            logging.warning("config/config.json not found. Business config not loaded.")
            raise FileNotFoundError("config/config.json not found.")

    # ---------------------------------------------------------------------
    # Logging Configuration
    # ---------------------------------------------------------------------
    def log_configuration(self):
        """Log the loaded configuration for debugging purposes."""
        logging.info("Configuration loaded successfully.")
        logging.debug(f"Twilio Config: {self.TWILIO}")
        logging.debug(f"Database Config: {self.DATABASE}")
        logging.debug(f"AWS Config: {self.AWS}")
        logging.debug(f"OpenAI Config: {self.OPENAI}")
        logging.debug(f"Shopify Config: {self.SHOPIFY}")
        logging.debug(f"App Settings: {self.APP}")
        # Log all business config keys
        for attr in dir(self):
            if attr.isupper() and attr not in [
                "TWILIO", "DATABASE", "AWS", "OPENAI", "SHOPIFY", "APP", "DATA_DIR"
            ]:
                logging.debug(f"{attr}: {getattr(self, attr)}")

# ---------------------------------------------------------------------
# Singleton Configuration Instance
# ---------------------------------------------------------------------
config = Config()
config.log_configuration()