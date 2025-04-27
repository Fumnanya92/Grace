import unittest
from unittest.mock import patch, MagicMock
from modules.payment_module import PaymentHandler
from config import config

class TestPaymentFlow(unittest.TestCase):
    @patch("modules.payment_module.sqlite3.connect")
    @patch("modules.payment_module.Client")
    def test_process_payment_request(self, mock_twilio_client, mock_sqlite_connect):
        """Test processing a payment request"""
        # Mock database connection
        mock_conn = MagicMock()
        mock_sqlite_connect.return_value = mock_conn
        mock_cursor = mock_conn.cursor.return_value
        
        # Mock Twilio client
        mock_twilio = MagicMock()
        mock_twilio_client.return_value = mock_twilio
        
        # Initialize PaymentHandler
        handler = PaymentHandler()
        
        # Simulate a payment request
        sender = "whatsapp:+1234567890"
        message = "Please send me the account details"
        result = handler.process_payment_request(sender, message)
        
        # Assertions
        mock_cursor.execute.assert_called()
        self.assertIn(config.PAYMENT_DETAILS['account_name'], result)
        self.assertIn(config.PAYMENT_DETAILS['account_number'], result)
        self.assertIn(config.PAYMENT_DETAILS['bank_name'], result)

    @patch("modules.payment_module.sqlite3.connect")
    def test_verify_payment(self, mock_sqlite_connect):
        """Test verifying a payment"""
        # Mock database connection
        mock_conn = MagicMock()
        mock_sqlite_connect.return_value = mock_conn
        mock_cursor = mock_conn.cursor.return_value
        
        # Simulate a payment record
        mock_cursor.fetchone.side_effect = [
            {'sender': 'whatsapp:+1234567890', 'deposit_paid': 0},  # Payment record
            {'name': 'John Doe'}  # Customer record
        ]
        
        # Initialize PaymentHandler
        handler = PaymentHandler()
        
        # Simulate payment verification
        verification_code = "1234"
        result = handler.verify_payment(verification_code)
        
        # Assertions
        mock_cursor.execute.assert_called()
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['customer'], 'whatsapp:+1234567890')
        self.assertEqual(result['name'], 'John Doe')

if __name__ == "__main__":
    unittest.main()