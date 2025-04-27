import os
import logging
from dotenv import load_dotenv
from typing import Dict, Any

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO)

class Config:
    """Central configuration class for all application settings"""

    # Twilio/WhatsApp Configuration
    TWILIO_ACCOUNT_SID: str = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN: str = os.getenv('TWILIO_AUTH_TOKEN')
    WHATSAPP_NUMBER: str = os.getenv('WHATSAPP_NUMBER', 'whatsapp:+14155238886')  # Sandbox number

    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        logging.error("Twilio credentials are missing in the environment variables.")
        raise ValueError("Twilio credentials are required.")

    # Payment Configuration
    PAYMENT_DETAILS: Dict[str, Any] = {
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

    if not os.path.exists(DATABASE['path']):
        open(DATABASE['path'], 'w').close()  # Create an empty file
        logging.warning(f"Database file created at: {DATABASE['path']}")

    # AWS S3 Configuration
    AWS: Dict[str, str] = {
        'access_key': os.getenv('AWS_ACCESS_KEY_ID'),
        'secret_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
        'region': os.getenv('AWS_REGION', 'us-east-1'),
        'bucket': os.getenv('S3_BUCKET_NAME', 'default-bucket'),
        'designs_folder': os.getenv('S3_WHOLESALE_PIC', 'designs/')
    }

    if not AWS['access_key'] or not AWS['secret_key']:
        logging.error("AWS credentials are missing in the environment variables.")
        raise ValueError("AWS credentials are required.")

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

    # Wholesale Business Rules
    BUSINESS_RULES: Dict[str, Any] = {
        'max_designs': int(os.getenv('MAX_DESIGNS', '4')),
        'production_days': int(os.getenv('PRODUCTION_DAYS', '10')),
        'accountant_contact': os.getenv('ACCOUNTANT_CONTACT', '08167322603'),
        'wholesale_package': {
            'piece_count': int(os.getenv('PIECE_COUNT', '40')),
            'video_count': int(os.getenv('VIDEO_COUNT', '4')),
            'session_included': os.getenv('SESSION_INCLUDED', 'True').lower() == 'true'
        }
    }

    logging.info("Configuration loaded successfully.")

# Singleton configuration instance
config = Config()