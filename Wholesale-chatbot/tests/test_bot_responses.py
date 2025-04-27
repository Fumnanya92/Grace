import unittest
from modules.bot_responses import ResponseTemplates
from config import PAYMENT_DETAILS, APP_DETAILS

class TestResponseTemplates(unittest.TestCase):
    def setUp(self):
        self.responses = ResponseTemplates()

    def test_package_details(self):
        """Test the package details response."""
        response = self.responses.get_response("package_details")
        self.assertIn(str(PAYMENT_DETAILS['total_amount']), response)
        self.assertIn("4 designs", response)

    def test_deposit_instructions(self):
        """Test the deposit instructions response."""
        response = self.responses.get_response("deposit_instructions")
        self.assertIn(PAYMENT_DETAILS['account_name'], response)
        self.assertIn(PAYMENT_DETAILS['bank_name'], response)
        self.assertIn(PAYMENT_DETAILS['account_number'], response)

    def test_payment_verification(self):
        """Test the payment verification response."""
        response = self.responses.get_response("payment_verification")
        self.assertIn(PAYMENT_DETAILS.get('contact_number', 'N/A'), response)

    def test_payment_confirmed(self):
        """Test the payment confirmed response."""
        response = self.responses.get_response("payment_confirmed")
        self.assertIn(APP_DETAILS['default_image_link'], response)

    def test_default_response(self):
        """Test the default response."""
        response = self.responses.get_response("non_existent_key")
        self.assertEqual(response, "I'm here to assist you with your wholesale inquiries. How can I help?")

if __name__ == "__main__":
    unittest.main()