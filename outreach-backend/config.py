# outreach/config.py
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("BASE_URL", "").rstrip("/")
API_TOKEN = os.getenv("API_TOKEN", "")

CAMPAIGN_ID = int(os.getenv("CAMPAIGN_ID", "3"))

TEST_EMAIL = os.getenv("TEST_EMAIL", "").strip()

EMAIL_METHOD = 2        # per your spec
LINKEDIN_METHOD = 1     # per your spec

SEND_MIN_DELAY_MS = int(os.getenv("SEND_MIN_DELAY_MS", "1500"))
SEND_MAX_DELAY_MS = int(os.getenv("SEND_MAX_DELAY_MS", "3500"))

# Playwright storage to persist logins
PLAYWRIGHT_STORAGE = os.getenv(
    "PLAYWRIGHT_STORAGE", "outreach/.storage/gmail.json")
PLAYWRIGHT_STORAGE_LINKEDIN = os.getenv(
    "PLAYWRIGHT_STORAGE_LINKEDIN", "outreach/.storage/linkedin.json")

# Gmail API
GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "token.json")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]