import unittest
from unittest.mock import patch
from config import Config

class TestEnvironmentValidation(unittest.TestCase):
    @patch.dict('os.environ', {}, clear=True)
    def test_missing_twilio_credentials(self):
        """Test missing Twilio credentials"""
        with self.assertRaises(ValueError) as context:
            Config()
        self.assertIn("Twilio credentials are missing", str(context.exception))

    @patch.dict('os.environ', {'TWILIO_ACCOUNT_SID': 'test_sid'}, clear=True)
    def test_missing_twilio_auth_token(self):
        """Test missing Twilio Auth Token"""
        with self.assertRaises(ValueError) as context:
            Config()
        self.assertIn("Twilio credentials are missing", str(context.exception))

    @patch.dict('os.environ', {'TWILIO_ACCOUNT_SID': 'test_sid', 'TWILIO_AUTH_TOKEN': 'test_token'}, clear=True)
    def test_valid_environment(self):
        """Test valid environment variables"""
        try:
            config = Config()
            self.assertIsNotNone(config.TWILIO_ACCOUNT_SID)
            self.assertIsNotNone(config.TWILIO_AUTH_TOKEN)
        except Exception as e:
            self.fail(f"Config initialization failed with valid environment variables: {e}")

if __name__ == "__main__":
    unittest.main()