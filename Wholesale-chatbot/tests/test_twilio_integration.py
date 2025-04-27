import unittest
from unittest.mock import patch, MagicMock
from modules.payment_module import PaymentHandler
from config import config

class TestTwilioIntegration(unittest.TestCase):
    @patch("modules.payment_module.Client")
    def test_twilio_message_sending(self, mock_twilio_client):
        """Test Twilio message sending"""
        # Mock Twilio client
        mock_twilio = MagicMock()
        mock_twilio_client.return_value = mock_twilio
        
        # Initialize PaymentHandler
        handler = PaymentHandler()
        
        # Simulate sending a payment confirmation
        sender = "whatsapp:+1234567890"
        handler._send_payment_confirmation(sender, "John Doe")
        
        # Assertions
        mock_twilio.messages.create.assert_called_once_with(
            body=f"Dear John Doe,\n\n{config.RESPONSES['payment']['confirmed']}",
            from_=config.WHATSAPP_NUMBER,
            to=sender
        )

    @patch("modules.payment_module.Client")
    def test_twilio_accountant_alert(self, mock_twilio_client):
        """Test Twilio accountant alert"""
        # Mock Twilio client
        mock_twilio = MagicMock()
        mock_twilio_client.return_value = mock_twilio
        
        # Initialize PaymentHandler
        handler = PaymentHandler()
        
        # Simulate sending an accountant alert
        sender = "whatsapp:+1234567890"
        verification_code = "1234"
        handler._alert_accountant(sender, verification_code)
        
        # Assertions
        mock_twilio.messages.create.assert_called_once()
        args, kwargs = mock_twilio.messages.create.call_args
        self.assertIn(config.BUSINESS_RULES['accountant_contact'], kwargs['to'])
        self.assertIn(verification_code, kwargs['body'])

if __name__ == "__main__":
    unittest.main()