import asyncio
from modules.utils import match_intent
from modules.utils import get_canned_response
from modules.bot_responses import BotResponses

# Test cases
print(match_intent("hello"))  # Expected: "greetings"
print(match_intent("what's your account details"))  # Expected: "account_details"

print(get_canned_response("greetings"))  # Expected: "Hi there! How can I assist you today?"
print(get_canned_response("account_details"))  # Expected: "Our account details are XYZ Bank, Account Number: 123456789."

async def test_grace():
    bot = BotResponses()
    history = [{"role": "user", "content": "Hello"}]

    # Test basic conversation
    response = await bot.handle_text_message("whatsapp:+1234567890", "Hello", history)
    print(response)  # Expected: "Hi there! How can I assist you today?"

    # Test dynamic question
    response = await bot.handle_text_message("whatsapp:+1234567890", "What are your business hours?", history)
    print(response)  # Expected: "We're open from 9 AM to 5 PM, Monday to Friday."

    # Test unknown query
    response = await bot.handle_text_message("whatsapp:+1234567890", "Tell me something interesting", history)
    print(response)  # Expected: A GPT-generated response.

asyncio.run(test_grace())