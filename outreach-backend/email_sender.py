#!/usr/bin/env python3
"""
Gmail API Email Sender
Sends HTML emails using Gmail API 
"""
import os
import base64
import time
import random
from email.mime.text import MIMEText
from typing import Optional
from api_client import get_campaign_email_content

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

from config import (
    GMAIL_TOKEN_PATH,
    GMAIL_CREDENTIALS_PATH, 
    GMAIL_SCOPES,
    SENDER_EMAIL,
    TEST_EMAIL,
    SEND_MIN_DELAY_MS,
    SEND_MAX_DELAY_MS,
    EMAIL_METHOD,
    CAMPAIGN_ID
)
from api_client import (
    get_campaign,
    get_campaign_email_content,
    get_campaign_contacts,
    get_contact
)

def render_email(campaign_id: int, contact: dict) -> tuple[str, str]:
    subject, html_body = get_campaign_email_content(campaign_id)
    first = contact.get("first_name") or "there"
    return subject, html_body.replace("{{first_name}}", first)

def _load_gmail_credentials() -> Credentials:
    """
    Load Gmail API credentials from token.json.
    Automatically refreshes expired tokens if refresh_token is available.
    """
    # Get absolute paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    if not os.path.isabs(GMAIL_TOKEN_PATH):
        token_path = os.path.join(script_dir, GMAIL_TOKEN_PATH)
    else:
        token_path = GMAIL_TOKEN_PATH
    
    if not os.path.isabs(GMAIL_CREDENTIALS_PATH):
        creds_path = os.path.join(script_dir, GMAIL_CREDENTIALS_PATH)
    else:
        creds_path = GMAIL_CREDENTIALS_PATH
    
    creds = None
    
    # Load existing token if it exists
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, GMAIL_SCOPES)
            print(f"[INFO] Loaded token from {token_path}")
        except Exception as e:
            print(f"[WARN] Failed to load token: {e}")
            creds = None
    
    # If no valid credentials, try to refresh or get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("[INFO] Token expired, refreshing...")
                creds.refresh(Request())
                # Save refreshed token
                os.makedirs(os.path.dirname(token_path) or ".", exist_ok=True)
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
                print("[SUCCESS] Token refreshed and saved")
            except Exception as e:
                print(f"[WARN] Failed to refresh token: {e}")
                creds = None
        
        # If still no credentials, start OAuth flow
        if not creds:
            if not os.path.exists(creds_path):
                raise FileNotFoundError(
                    f"credentials.json not found at {creds_path}.\n"
                    f"Please run: python setup_gmail_oauth.py"
                )
            
            print("[INFO] No valid token found. Starting OAuth flow...")
            print("[INFO] A browser window will open for Gmail authentication...")
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
            
            # Save the token for future use
            os.makedirs(os.path.dirname(token_path) or ".", exist_ok=True)
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
            print(f"[SUCCESS] Token saved to {token_path}")
    
    return creds


def send_gmail_html(to_email: str, subject: str, html_body: str, sender: Optional[str] = None) -> bool:
    """
    Send HTML email via Gmail API.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_body: HTML email body
        sender: Sender email (optional, uses SENDER_EMAIL from config or Gmail account)
    
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        creds = _load_gmail_credentials()
        service = build("gmail", "v1", credentials=creds)

        # Create HTML email
        msg = MIMEText(html_body, "html")
        msg["To"] = to_email
        msg["From"] = sender or SENDER_EMAIL or "me"
        msg["Subject"] = subject

        # Encode and send
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        result = service.users().messages().send(
            userId="me", 
            body={"raw": raw}
        ).execute()
        
        message_id = result.get("id")
        print(f"[SUCCESS] ✓ Sent email to {to_email} (Message ID: {message_id})")
        return True
        
    except HttpError as e:
        error_msg = str(e)
        print(f"[ERROR] Gmail API error for {to_email}: {error_msg}")
        
        # Provide helpful error messages
        if e.resp.status == 403:
            print("[ERROR] Permission denied. Check:")
            print("  1. Gmail API is enabled in Google Cloud Console")
            print("  2. OAuth scopes include 'gmail.send'")
            print("  3. Your account has permission to send emails")
        elif e.resp.status == 401:
            print("[ERROR] Authentication failed. Token may be invalid.")
            print("[INFO] Try running: python setup_gmail_oauth.py")
        elif e.resp.status == 400:
            print("[ERROR] Bad request. Check email addresses and message format")
        
        return False
        
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        return False
        
    except Exception as e:
        print(f"[ERROR] Unexpected error sending email: {e}")
        import traceback
        traceback.print_exc()
        return False


def _sleep_jitter():
    """Sleep a random time between SEND_MIN_DELAY_MS and SEND_MAX_DELAY_MS."""
    ms = random.randint(SEND_MIN_DELAY_MS, SEND_MAX_DELAY_MS)
    time.sleep(ms / 1000.0)


def run_campaign_emails(campaign_id: int, contact_method: int = EMAIL_METHOD) -> int:
    """
    Send HTML emails for a campaign using Gmail API.
    
    Args:
        campaign_id: Campaign ID to send emails for
        contact_method: Contact method ID (defaults to EMAIL_METHOD from config)
    
    Returns:
        Number of emails successfully sent
    """
    print("=" * 60)
    print(f"Starting Email Campaign {campaign_id}")
    print("=" * 60)
    
    # Get campaign details
    try:
        campaign = get_campaign(campaign_id)
        print(f"Campaign: {campaign.get('name')}")
    except Exception as e:
        print(f"[ERROR] Failed to fetch campaign: {e}")
        return 0
    
    # Get email subject and HTML body from campaign
    try:
        subject, html_body = get_campaign_email_content(campaign_id)
        print(f"Subject: {subject}")
        print(f"Body length: {len(html_body)} characters")
    except Exception as e:
        print(f"[ERROR] Failed to get email content: {e}")
        return 0
    
    # Get contacts for this campaign
    print(f"\nFetching contacts for campaign {campaign_id}...")
    contacts = get_campaign_contacts(campaign_id, contact_method)
    
    if not contacts:
        print("[WARN] No contacts found for this campaign/method")
        return 0
    
    print(f"Found {len(contacts)} contacts to email\n")
    
    # Send emails
    sent_count = 0
    for idx, item in enumerate(contacts, 1):
        contact_id = item.get("contact") or item.get("contact_id")
        if not contact_id:
            print(f"[{idx}/{len(contacts)}] [WARN] Skipping item without contact id")
            continue
        
        try:
            contact = get_contact(contact_id)
        except Exception as e:
            print(f"[{idx}/{len(contacts)}] [ERROR] Failed to fetch contact {contact_id}: {e}")
            continue

        # Get email address from contact
        to_email = None
        for key in ("email", "email_address", "primary_email"):
            val = contact.get(key)
            if isinstance(val, str) and "@" in val:
                to_email = val.strip()
                break
        
        if not to_email:
            print(f"[{idx}/{len(contacts)}] [WARN] No email for contact {contact_id}, skipping")
            continue

        # Personalize email if needed (replace {{first_name}} placeholder)
        personalized_body = html_body
        first_name = contact.get("first_name", "")
        if first_name:
            personalized_body = html_body.replace("{{first_name}}", first_name)
        
        # Use TEST_EMAIL override if set
        actual_recipient = TEST_EMAIL if TEST_EMAIL else to_email
        if TEST_EMAIL:
            print(f"[{idx}/{len(contacts)}] [TEST MODE] Sending to {TEST_EMAIL} (instead of {to_email})")
        else:
            print(f"[{idx}/{len(contacts)}] Sending to {to_email}...")
        
        # Send the email
        success = send_gmail_html(actual_recipient, subject, personalized_body)
        
        if success:
            sent_count += 1
        
        # Add jitter between sends (except for last email)
        if idx < len(contacts):
            _sleep_jitter()
    
    print("\n" + "=" * 60)
    print(f"Campaign Complete: {sent_count}/{len(contacts)} emails sent successfully")
    print("=" * 60)
    
    return sent_count


def test_send():
    """Send a test email to TEST_EMAIL."""
    if not TEST_EMAIL:
        print("[ERROR] TEST_EMAIL not set in .env file")
        print("Please set TEST_EMAIL=your-email@example.com in your .env file")
        return False
    
    print(f"[INFO] Sending test email to {TEST_EMAIL}...")
    
    subject = "Gmail API HTML Test"
    html_body = """
    <html>
        <body>
            <h1>Hello from Gmail API!</h1>
            <p>This is a <b>test email</b> with <i>HTML formatting</i>.</p>
            <ul>
                <li>Gmail API works! ✓</li>
                <li>HTML emails work! ✓</li>
                <li>Ready for campaigns! ✓</li>
            </ul>
            <p>Best regards,<br>Your Email Automation</p>
        </body>
    </html>
    """
    
    return send_gmail_html(TEST_EMAIL, subject, html_body)


def setup_oauth():
    """Run OAuth flow to generate token.json - only needed once!"""
    print("=" * 60)
    print("Gmail OAuth Setup")
    print("=" * 60)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    creds_path = os.path.join(script_dir, GMAIL_CREDENTIALS_PATH)
    token_path = os.path.join(script_dir, GMAIL_TOKEN_PATH)
    
    if not os.path.exists(creds_path):
        print(f"[ERROR] credentials.json not found at: {creds_path}")
        print("\nPlease create credentials.json with your OAuth client credentials")
        print("from Google Cloud Console")
        return False
    
    print(f"[INFO] Using credentials from: {creds_path}")
    print("[INFO] Starting OAuth flow...")
    print("[INFO] A browser window will open for Gmail authentication\n")
    
    try:
        flow = InstalledAppFlow.from_client_secrets_file(creds_path, GMAIL_SCOPES)
        creds = flow.run_local_server(port=0)
        
        # Save the token
        os.makedirs(os.path.dirname(token_path) or ".", exist_ok=True)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
        
        print(f"\n[SUCCESS] ✓ Token saved to: {token_path}")
        print("[SUCCESS] ✓ Gmail OAuth setup completed!")
        print("\nYou can now send emails using: python email_sender.py test")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] OAuth flow failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "setup":
            # Setup OAuth
            setup_oauth()
        elif sys.argv[1] == "test":
            # Test mode: send test email
            test_send()
        elif sys.argv[1].isdigit():
            # Campaign mode: send campaign emails
            campaign_id = int(sys.argv[1])
            run_campaign_emails(campaign_id)
        else:
            print("Usage:")
            print("  python email_sender.py setup         # Setup Gmail OAuth (first time)")
            print("  python email_sender.py test          # Send test email")
            print("  python email_sender.py <campaign_id> # Run campaign")
    else:
        # Default: use CAMPAIGN_ID from config
        if TEST_EMAIL:
            print(f"[INFO] TEST_EMAIL is set: {TEST_EMAIL}")
            print("[INFO] All emails will be sent to this address for testing")
        
        run_campaign_emails(CAMPAIGN_ID)