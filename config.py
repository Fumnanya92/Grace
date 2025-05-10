import os
import logging
from dotenv import load_dotenv
from typing import Dict, Any

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO').upper())

class Config:
    """Central configuration class for all application settings"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Config, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        self._validate_twilio_config()
        self._validate_aws_config()
        self._validate_openai_config()
        self._ensure_database_file()

        # Add direct attributes for Twilio credentials
        self.TWILIO_ACCOUNT_SID = self.TWILIO['account_sid']
        self.TWILIO_AUTH_TOKEN = self.TWILIO['auth_token']
        self.AWS_ACCESS_KEY = self.AWS['access_key']
        self.AWS_SECRET_KEY = self.AWS['secret_key']
        self.OPENAI_API_KEY = self.OPENAI['api_key']

    # Twilio/WhatsApp Configuration
    TWILIO: Dict[str, str] = {
        'account_sid': os.getenv('TWILIO_ACCOUNT_SID'),
        'auth_token': os.getenv('TWILIO_AUTH_TOKEN'),
        'whatsapp_number': os.getenv('WHATSAPP_NUMBER', 'whatsapp:+14155238886')
    }

    # Payment Configuration
    PAYMENT: Dict[str, Any] = {
        'account_name': os.getenv('ACCOUNT_NAME', 'Atuchewoman Empire'),
        'account_number': os.getenv('ACCOUNT_NUMBER', '5401973359'),
        'bank_name': os.getenv('BANK_NAME', 'Providus Bank'),
        'deposit_percentage': float(os.getenv('DEPOSIT_PERCENTAGE', '0.5')),
        'total_amount': int(os.getenv('TOTAL_AMOUNT', '600000')),
        'verification_code_length': int(os.getenv('VERIFICATION_CODE_LENGTH', '4'))
    }

    # Database Configuration
    DATABASE: Dict[str, Any] = {
        'path': os.getenv('DB_PATH', 'memory.db'),
        'tables': {
            'users': 'user_memory',
            'payments': 'payments',
            'designs': 'design_submissions'
        }
    }

    # AWS S3 Configuration
    AWS: Dict[str, str] = {
        'access_key': os.getenv('AWS_ACCESS_KEY_ID'),
        'secret_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
        'region': os.getenv('AWS_REGION', 'us-east-1'),
        'bucket': os.getenv('S3_BUCKET_NAME', 'default-bucket'),
        'designs_folder': os.getenv('S3_WHOLESALE_PIC', 'designs/')
    }

    # OpenAI Configuration
    OPENAI: Dict[str, Any] = {
        'api_key': os.getenv('OPENAI_API_KEY'),
        'model': os.getenv('OPENAI_MODEL', 'gpt-4'),
        'temperature': float(os.getenv('OPENAI_TEMPERATURE', '0.7'))
    }

    # Application Settings
    APP: Dict[str, Any] = {
        'debug': os.getenv('DEBUG', 'False').lower() == 'true',
        'port': int(os.getenv('PORT', '5000')),
        'ngrok_auth_token': os.getenv('NGROK_AUTH_TOKEN'),
        'log_days_to_keep': int(os.getenv('LOG_DAYS_TO_KEEP', '7')),
        'default_image_link': os.getenv('DEFAULT_IMAGE_LINK', 'https://example.com/catalog')
    }

    def _validate_twilio_config(self):
        """Validate Twilio configuration."""
        if not self.TWILIO['account_sid'] or not self.TWILIO['auth_token']:
            logging.error("Twilio credentials are missing in the environment variables.")
            raise ValueError("Twilio credentials are required.")

    def _validate_aws_config(self):
        """Validate AWS S3 configuration."""
        if not self.AWS['access_key'] or not self.AWS['secret_key']:
            logging.error("AWS credentials are missing in the environment variables.")
            raise ValueError("AWS credentials are required.")

    def _validate_openai_config(self):
        """Validate OpenAI configuration."""
        if not self.OPENAI['api_key']:
            logging.error("OpenAI API key is missing in the environment variables.")
            raise ValueError("OpenAI API key is required.")

    def _ensure_database_file(self):
        """Ensure the database file exists."""
        if not os.path.exists(self.DATABASE['path']):
            open(self.DATABASE['path'], 'w').close()  # Create an empty file
            logging.warning(f"Database file created at: {self.DATABASE['path']}")

    def log_configuration(self):
        """Log the loaded configuration for debugging purposes."""
        logging.info("Configuration loaded successfully.")
        logging.debug(f"Twilio Config: {self.TWILIO}")
        logging.debug(f"Payment Config: {self.PAYMENT}")
        logging.debug(f"Database Config: {self.DATABASE}")
        logging.debug(f"AWS Config: {self.AWS}")
        logging.debug(f"OpenAI Config: {self.OPENAI}")
        logging.debug(f"App Settings: {self.APP}")


# Singleton configuration instance
config = Config()
config.log_configuration()