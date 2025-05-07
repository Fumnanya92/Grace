from twilio.rest import Client
import os
from dotenv import load_dotenv

# Replace with your Twilio Account SID and Auth Token
# Load environment variables from a .env file
load_dotenv()

# Retrieve Twilio credentials from environment variables
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")

try:
    # Initialize the Twilio client
    client = Client(account_sid, auth_token)

    # Fetch account details
    account = client.api.accounts(account_sid).fetch()

    # Print account details
    print(f"Account SID: {account.sid}")
    print(f"Account Friendly Name: {account.friendly_name}")
    print("Twilio credentials are valid!")
except Exception as e:
    print(f"Failed to validate Twilio credentials: {e}")