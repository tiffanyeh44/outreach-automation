import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
BASE_URL = os.getenv("BASE_URL", "").strip()
API_TOKEN = os.getenv("API_TOKEN", "").strip()

# Gmail API Configuration
GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", ".storage/credentials.json").strip()
GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", ".storage/token.json").strip()
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "").strip()

# Test Configuration
TEST_EMAIL = os.getenv("TEST_EMAIL", "").strip()
CAMPAIGN_ID = int(os.getenv("TEST_CAMPAIGN_ID", "3"))

# Contact Methods
EMAIL_METHOD = 2
LINKEDIN_METHOD = 4

# Timing Configuration (milliseconds)
SEND_MIN_DELAY_MS = int(os.getenv("SEND_MIN_DELAY_MS", "1500"))
SEND_MAX_DELAY_MS = int(os.getenv("SEND_MAX_DELAY_MS", "3500"))

# LinkedIn Configuration
PLAYWRIGHT_STORAGE_LINKEDIN = ".storage/linkedin_state.json"

# Validation
if not BASE_URL:
    raise ValueError("BASE_URL is not set in .env file")

if not API_TOKEN or API_TOKEN == "your_api_token_here":
    print("[WARN] API_TOKEN is not set or is using placeholder value")
    print("[WARN] API calls may fail if authentication is required")

print(f"[CONFIG] BASE_URL: {BASE_URL}")
print(f"[CONFIG] API_TOKEN: {'*' * len(API_TOKEN) if API_TOKEN else 'NOT SET'}")
print(f"[CONFIG] SENDER_EMAIL: {SENDER_EMAIL}")
print(f"[CONFIG] TEST_EMAIL: {TEST_EMAIL}")