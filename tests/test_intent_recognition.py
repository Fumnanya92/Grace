# tests/test_intent_recognition.py

import unittest
from modules.intent_recognition_module import recognize_intent

class TestIntentRecognition(unittest.TestCase):

    def test_greeting_intent(self):
        self.assertEqual(recognize_intent("Hello there!"), "greeting")
        self.assertEqual(recognize_intent("Good morning!"), "greeting")

    def test_payment_intent(self):
        self.assertEqual(recognize_intent("I have made the payment"), "payment")
        self.assertEqual(recognize_intent("Here is the proof of payment"), "payment")

    def test_product_inquiry_intent(self):
        self.assertEqual(recognize_intent("What are the prices?"), "product_inquiry")
        self.assertEqual(recognize_intent("Show me the catalog"), "product_inquiry")

    def test_order_confirmation_intent(self):
        self.assertEqual(recognize_intent("I want to confirm order"), "order_confirmation")
        self.assertEqual(recognize_intent("I'm ready to buy now"), "order_confirmation")

    def test_off_topic_intent(self):
        self.assertEqual(recognize_intent("What's the weather like?"), "off_topic")
        self.assertEqual(recognize_intent("Tell me a joke"), "off_topic")

    def test_unknown_intent(self):
        self.assertEqual(recognize_intent("Blah blah blah"), "unknown")
        self.assertEqual(recognize_intent("I love pizza"), "unknown")

if __name__ == '__main__':
    unittest.main()
