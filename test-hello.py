from modules.utils import match_intent
from modules.utils import get_canned_response

# Test cases
print(match_intent("hello"))  # Expected: "greetings"
print(match_intent("what's your account details"))  # Expected: "account_details"

print(get_canned_response("greetings"))  # Expected: "Hi there! How can I assist you today?"
print(get_canned_response("account_details"))  # Expected: "Our account details are XYZ Bank, Account Number: 123456789."