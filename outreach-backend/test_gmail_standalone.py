"""Standalone Gmail API test - no relative imports."""
import base64
import os
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv

load_dotenv()

# Get config from environment
GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "token.json")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def send_gmail_html(to_email: str, subject: str, html_body: str, sender: str = None):
    """Send HTML email via Gmail API."""
    creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_PATH, GMAIL_SCOPES)
    service = build("gmail", "v1", credentials=creds)

    msg = MIMEText(html_body, "html")
    msg["To"] = to_email
    msg["From"] = sender or SENDER_EMAIL or "me"
    msg["Subject"] = subject

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    try:
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        print(f"[SUCCESS] Sent email to {to_email}")
        return True
    except HttpError as e:
        print(f"[ERROR] Gmail API error for {to_email}: {e}")
        return False

if __name__ == "__main__":
    print("[INFO] Testing Gmail API send to pbryzek@berkeley.edu...")
    print(f"[INFO] Using token file: {GMAIL_TOKEN_PATH}")
    
    # Check if token exists
    if not os.path.exists(GMAIL_TOKEN_PATH):
        print(f"[ERROR] Token file not found at {GMAIL_TOKEN_PATH}")
        print("[INFO] Please run setup_gmail_auth.py first to create token.json")
        exit(1)
    
    success = send_gmail_html(
        "pbryzek@berkeley.edu",
        "Gmail API HTML test",
        "<b>Hello</b> world via Gmail API"
    )
    
    if success:
        print("[SUCCESS] Test completed successfully!")
    else:
        print("[ERROR] Test failed - check error messages above")

