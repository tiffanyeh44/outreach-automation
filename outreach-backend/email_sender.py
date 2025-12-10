#!/usr/bin/env python3
"""
Email sender module for outreach campaigns.
Sends HTML emails using Gmail API and logs each send to the API.
"""
import os
import time
import random
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from config import (
    GMAIL_CREDENTIALS_PATH,
    GMAIL_TOKEN_PATH,
    GMAIL_SCOPES,
    SENDER_EMAIL,
    SEND_MIN_DELAY_MS,
    SEND_MAX_DELAY_MS
)

import api_client


class EmailSender:
    """
    Handles email sending via Gmail API.
    Manages authentication, personalization, and delivery tracking.
    """
    
    def __init__(
        self,
        credentials_path: str = GMAIL_CREDENTIALS_PATH,
        token_path: str = GMAIL_TOKEN_PATH,
        scopes: list = None,
        sender_email: str = SENDER_EMAIL,
        send_min_delay_ms: int = SEND_MIN_DELAY_MS,
        send_max_delay_ms: int = SEND_MAX_DELAY_MS
    ):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.scopes = scopes or GMAIL_SCOPES
        self.sender_email = sender_email
        self.send_min_delay_ms = send_min_delay_ms
        self.send_max_delay_ms = send_max_delay_ms
        self._service = None

    # ----------------- Private Helper Methods -----------------

    def _sleep_jitter(self):
        """Sleep for a random duration between configured min/max delay."""
        delay_ms = random.randint(self.send_min_delay_ms, self.send_max_delay_ms)
        time.sleep(delay_ms / 1000.0)

    def _get_gmail_service(self):
        """Authenticate and return Gmail API service (cached)."""
        if self._service:
            return self._service
        
        creds = None
        
        # Check if token.json exists (saved credentials)
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)
        
        # If no valid credentials, let user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("[INFO] Refreshing expired Gmail credentials...")
                creds.refresh(Request())
            else:
                print("[INFO] No valid Gmail credentials found. Starting OAuth flow...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.scopes
                )
                creds = flow.run_local_server(port=0)
            
            # Save credentials for future use
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
            print(f"[INFO] Gmail credentials saved to {self.token_path}")
        
        self._service = build('gmail', 'v1', credentials=creds)
        return self._service

    def _get_email_from_contact(self, contact: dict) -> str:
        """Extract email address from contact data."""
        # Try direct email field first
        email = contact.get("email")
        if isinstance(email, str) and "@" in email:
            return email.strip()
        
        # Try other common field names
        for key in ("email_address", "primary_email", "work_email"):
            val = contact.get(key)
            if isinstance(val, str) and "@" in val:
                return val.strip()
        
        raise ValueError(f"No email address found in contact {contact.get('id')}")

    def _personalize_html(self, html_body: str, contact: dict) -> str:
        """Personalize HTML email body with contact information."""
        personalized = html_body
        
        # Replace common placeholders
        first_name = contact.get("first_name", "")
        last_name = contact.get("last_name", "")
        full_name = f"{first_name} {last_name}".strip()
        
        if first_name:
            personalized = personalized.replace("{{first_name}}", first_name)
            personalized = personalized.replace("{first_name}", first_name)
        
        if last_name:
            personalized = personalized.replace("{{last_name}}", last_name)
            personalized = personalized.replace("{last_name}", last_name)
        
        if full_name:
            personalized = personalized.replace("{{full_name}}", full_name)
            personalized = personalized.replace("{full_name}", full_name)
        
        return personalized

    # ----------------- Core Email Sending -----------------

    def send_email(self, to_email: str, subject: str, html_body: str) -> bool:
        """
        Send an HTML email using Gmail API.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML email body
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            service = self._get_gmail_service()
            
            # Create message
            message = MIMEMultipart('alternative')
            message['To'] = to_email
            message['From'] = self.sender_email
            message['Subject'] = subject
            
            # Attach HTML body
            html_part = MIMEText(html_body, 'html')
            message.attach(html_part)
            
            # Encode and send
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            body = {'raw': raw_message}
            
            result = service.users().messages().send(userId='me', body=body).execute()
            
            print(f"[SUCCESS] Email sent! Message ID: {result.get('id')}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to send email: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ----------------- Campaign Methods -----------------

    def send_to_contact(self, contact_id: int, campaign_id: int) -> bool:
        """
        Send email to a specific contact.
        
        Args:
            contact_id: Contact ID from API
            campaign_id: Campaign ID to get email content
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # STEP 1: Check if already contacted
            print(f"[CHECK] Checking if contact {contact_id} already contacted...")
            if api_client.check_if_already_contacted(campaign_id, contact_id, "email"):
                print(f"[SKIP] Contact {contact_id} already has outbound email log. Skipping.")
                return False
            
            # Get contact details from API
            print(f"[INFO] Fetching contact {contact_id}...")
            contact = api_client.get_contact(contact_id)
            
            # Extract email address
            to_email = self._get_email_from_contact(contact)
            print(f"[INFO] Email: {to_email}")
            
            # Get campaign email content
            subject, html_body = api_client.get_campaign_email_content(campaign_id)
            
            # Personalize email body
            personalized_body = self._personalize_html(html_body, contact)
            
            # Send email
            success = self.send_email(to_email, subject, personalized_body)
            
            # Log to API if sent successfully
            if success:
                try:
                    api_client.log_contact_outreach(
                        campaign_id=campaign_id,
                        contact_id=contact_id,
                        channel="email",
                        subject=subject,
                        body=personalized_body,
                        sender_email=self.sender_email
                    )
                    print(f"[LOG] Successfully logged outreach for contact {contact_id}")
                except Exception as log_error:
                    print(f"[WARN] Failed to log outreach: {log_error}")
            
            return success
            
        except Exception as e:
            print(f"[ERROR] Failed to send to contact {contact_id}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run_campaign(self, campaign_id: int, contact_ids: list) -> int:
        """
        Run email campaign for multiple contacts.
        
        Args:
            campaign_id: Campaign ID
            contact_ids: List of contact IDs to email
        
        Returns:
            Number of emails successfully sent
        """
        print("=" * 60)
        print(f"Starting Email Campaign {campaign_id}")
        print(f"Contacts to email: {len(contact_ids)}")
        print("=" * 60)
        
        # Get campaign details
        try:
            campaign = api_client.get_campaign(campaign_id)
            print(f"Campaign: {campaign.get('name')}")
        except Exception as e:
            print(f"[ERROR] Failed to fetch campaign: {e}")
            return 0
        
        # Get email subject and HTML body from campaign
        try:
            subject, html_body = api_client.get_campaign_email_content(campaign_id)
            print(f"Subject: {subject}")
            print(f"Body length: {len(html_body)} characters")
        except Exception as e:
            print(f"[ERROR] Failed to get email content: {e}")
            return 0
        
        print(f"\nSending to {len(contact_ids)} contacts...\n")
        
        # Send emails to contacts
        sent_count = 0
        for idx, contact_id in enumerate(contact_ids, 1):
            print(f"[{idx}/{len(contact_ids)}] Processing contact {contact_id}...")
            
            success = self.send_to_contact(contact_id, campaign_id)
            if success:
                sent_count += 1
            
            # Add jitter between sends (except for last email)
            if idx < len(contact_ids):
                self._sleep_jitter()
        
        print("\n" + "=" * 60)
        print(f"Campaign Complete: {sent_count}/{len(contact_ids)} emails sent successfully")
        print("=" * 60)
        
        return sent_count


# For backward compatibility - keep old function name
def run_campaign_emails_for_contacts(campaign_id: int, contact_ids: list, contact_method: int = 2) -> int:
    """
    Backward compatibility wrapper for existing code.
    """
    sender = EmailSender()
    return sender.run_campaign(campaign_id, contact_ids)


# For testing
if __name__ == "__main__":
    sender = EmailSender()
    print("[TEST] Email sender module loaded successfully")
    print(f"[TEST] Sender email: {sender.sender_email}")
    print(f"[TEST] Credentials path: {sender.credentials_path}")