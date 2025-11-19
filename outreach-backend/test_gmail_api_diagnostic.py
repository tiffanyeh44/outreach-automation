#!/usr/bin/env python3
"""
Diagnostic script to test Gmail API and identify issues.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError as e:
    print(f"[ERROR] Missing required Google API libraries: {e}")
    print("[INFO] Please install: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
    sys.exit(1)

# Configuration
GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "token.json")
GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
TEST_EMAIL = os.getenv("TEST_EMAIL", "")

def check_files():
    """Check if required files exist."""
    print("=" * 60)
    print("Checking for required files...")
    print("=" * 60)
    
    token_exists = os.path.exists(GMAIL_TOKEN_PATH)
    creds_exists = os.path.exists(GMAIL_CREDENTIALS_PATH)
    
    print(f"Token file ({GMAIL_TOKEN_PATH}): {'✓ EXISTS' if token_exists else '✗ NOT FOUND'}")
    print(f"Credentials file ({GMAIL_CREDENTIALS_PATH}): {'✓ EXISTS' if creds_exists else '✗ NOT FOUND'}")
    
    if not creds_exists:
        print("\n[WARNING] credentials.json not found!")
        print("[INFO] You need to:")
        print("  1. Go to https://console.cloud.google.com/")
        print("  2. Create a project (or select existing)")
        print("  3. Enable Gmail API")
        print("  4. Create OAuth 2.0 credentials (Desktop app)")
        print("  5. Download credentials.json and place it in outreach-backend/")
        return False
    
    if not token_exists:
        print("\n[WARNING] token.json not found!")
        print("[INFO] You need to run the OAuth flow to create token.json")
        return False
    
    return True

def load_or_refresh_credentials():
    """Load credentials from token.json or refresh if expired."""
    print("\n" + "=" * 60)
    print("Loading Gmail credentials...")
    print("=" * 60)
    
    creds = None
    
    # Check if token exists
    if os.path.exists(GMAIL_TOKEN_PATH):
        try:
            print(f"[INFO] Loading token from {GMAIL_TOKEN_PATH}...")
            creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_PATH, GMAIL_SCOPES)
            print("[SUCCESS] Token loaded successfully")
        except Exception as e:
            print(f"[ERROR] Failed to load token: {e}")
            return None
    
    # If no valid credentials, try to get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("[INFO] Token expired, attempting to refresh...")
                creds.refresh(Request())
                print("[SUCCESS] Token refreshed successfully")
                
                # Save the refreshed token
                with open(GMAIL_TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
                print(f"[INFO] Refreshed token saved to {GMAIL_TOKEN_PATH}")
            except Exception as e:
                print(f"[ERROR] Failed to refresh token: {e}")
                print("[INFO] You may need to re-authenticate")
                creds = None
        
        # If still no credentials, start OAuth flow
        if not creds:
            if not os.path.exists(GMAIL_CREDENTIALS_PATH):
                print(f"[ERROR] credentials.json not found at {GMAIL_CREDENTIALS_PATH}")
                return None
            
            try:
                print("[INFO] Starting OAuth flow...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    GMAIL_CREDENTIALS_PATH, GMAIL_SCOPES
                )
                creds = flow.run_local_server(port=0)
                print("[SUCCESS] OAuth flow completed")
                
                # Save the token for future use
                with open(GMAIL_TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
                print(f"[INFO] Token saved to {GMAIL_TOKEN_PATH}")
            except Exception as e:
                print(f"[ERROR] OAuth flow failed: {e}")
                import traceback
                traceback.print_exc()
                return None
    
    return creds

def test_gmail_api(creds):
    """Test Gmail API by sending a test email."""
    print("\n" + "=" * 60)
    print("Testing Gmail API...")
    print("=" * 60)
    
    if not TEST_EMAIL:
        print("[WARNING] TEST_EMAIL not set in environment variables")
        print("[INFO] Set TEST_EMAIL environment variable to test sending")
        return False
    
    try:
        # Build Gmail service
        print("[INFO] Building Gmail service...")
        service = build("gmail", "v1", credentials=creds)
        print("[SUCCESS] Gmail service created")
        
        # Get user profile to verify connection
        print("[INFO] Verifying Gmail connection...")
        profile = service.users().getProfile(userId="me").execute()
        email_address = profile.get("emailAddress")
        print(f"[SUCCESS] Connected to Gmail account: {email_address}")
        
        # Create test message
        from email.mime.text import MIMEText
        import base64
        
        print(f"[INFO] Creating test email to {TEST_EMAIL}...")
        message = MIMEText("This is a test email from Gmail API diagnostic script.", "plain")
        message["To"] = TEST_EMAIL
        message["From"] = SENDER_EMAIL or email_address
        message["Subject"] = "Gmail API Test - Diagnostic"
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        # Send message
        print("[INFO] Sending test email...")
        send_result = service.users().messages().send(
            userId="me",
            body={"raw": raw_message}
        ).execute()
        
        message_id = send_result.get("id")
        print(f"[SUCCESS] Email sent successfully! Message ID: {message_id}")
        print(f"[INFO] Check {TEST_EMAIL} inbox for the test email")
        return True
        
    except HttpError as e:
        print(f"[ERROR] Gmail API error: {e}")
        error_details = e.error_details if hasattr(e, 'error_details') else str(e)
        print(f"[ERROR] Error details: {error_details}")
        
        if e.resp.status == 403:
            print("[ERROR] Permission denied. Check:")
            print("  1. Gmail API is enabled in Google Cloud Console")
            print("  2. OAuth scopes include 'gmail.send'")
            print("  3. Your account has permission to send emails")
        elif e.resp.status == 401:
            print("[ERROR] Authentication failed. Token may be invalid or expired.")
            print("[INFO] Try deleting token.json and re-running this script")
        
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main diagnostic function."""
    print("Gmail API Diagnostic Tool")
    print("=" * 60)
    print(f"Token path: {GMAIL_TOKEN_PATH}")
    print(f"Credentials path: {GMAIL_CREDENTIALS_PATH}")
    print(f"Test email: {TEST_EMAIL or 'NOT SET'}")
    print(f"Sender email: {SENDER_EMAIL or 'NOT SET (will use Gmail account)'}")
    print()
    
    # Check files
    if not check_files():
        print("\n[ERROR] Required files are missing. Please set them up first.")
        return 1
    
    # Load credentials
    creds = load_or_refresh_credentials()
    if not creds:
        print("\n[ERROR] Failed to load or obtain credentials")
        return 1
    
    # Test Gmail API
    if TEST_EMAIL:
        success = test_gmail_api(creds)
        if success:
            print("\n" + "=" * 60)
            print("[SUCCESS] Gmail API test completed successfully!")
            print("=" * 60)
            return 0
        else:
            print("\n" + "=" * 60)
            print("[ERROR] Gmail API test failed")
            print("=" * 60)
            return 1
    else:
        print("\n[INFO] Skipping email send test (TEST_EMAIL not set)")
        print("[INFO] Credentials are valid and ready to use")
        return 0

if __name__ == "__main__":
    sys.exit(main())




