# tests/test_intent_recognition.py

import unittest
from modules.intent_recognition_module import recognize_intent

class TestIntentRecognition(unittest.TestCase):

    def test_greeting_intent(self):
        self.assertEqual(recognize_intent("Hello there!")[0], "greeting")
        self.assertEqual(recognize_intent("Good morning!")[0], "greeting")

    def test_payment_intent(self):
        self.assertEqual(recognize_intent("I have made the payment")[0], "payment")
        self.assertEqual(recognize_intent("Here is the proof of payment")[0], "payment")

    def test_product_inquiry_intent(self):
        self.assertEqual(recognize_intent("What are the prices?")[0], "product_inquiry")
        self.assertEqual(recognize_intent("Show me the catalog")[0], "product_inquiry")

    def test_order_confirmation_intent(self):
        self.assertEqual(recognize_intent("I want to confirm order")[0], "order_confirmation")
        self.assertEqual(recognize_intent("I'm ready to buy now")[0], "order_confirmation")

    def test_off_topic_intent(self):
        self.assertEqual(recognize_intent("What's the weather like?")[0], "off_topic")
        self.assertEqual(recognize_intent("Tell me a joke")[0], "off_topic")

    def test_unknown_intent(self):
        self.assertEqual(recognize_intent("Blah blah blah")[0], "unknown")
        self.assertEqual(recognize_intent("I love pizza")[0], "unknown")

if __name__ == '__main__':
    unittest.main()
