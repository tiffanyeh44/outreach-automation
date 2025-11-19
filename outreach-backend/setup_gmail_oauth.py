#!/usr/bin/env python3
"""
Setup Gmail OAuth and create token.json
Run this once to authenticate and create token.json
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

load_dotenv()

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

# Paths
CREDENTIALS_FILE = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")
TOKEN_FILE = os.getenv("GMAIL_TOKEN_PATH", ".storage/token.json")

def setup_gmail_oauth():
    """Run OAuth flow to create token.json"""
    print("=" * 60)
    print("Gmail OAuth Setup")
    print("=" * 60)
    
    # Check if credentials file exists
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"[ERROR] credentials.json not found at {CREDENTIALS_FILE}")
        print("[INFO] Please make sure credentials.json is in the outreach-backend directory")
        return False
    
    print(f"[INFO] Using credentials from: {CREDENTIALS_FILE}")
    
    # Ensure .storage directory exists
    token_dir = os.path.dirname(TOKEN_FILE) if os.path.dirname(TOKEN_FILE) else "."
    if token_dir and not os.path.exists(token_dir):
        os.makedirs(token_dir, exist_ok=True)
        print(f"[INFO] Created directory: {token_dir}")
    
    creds = None
    
    # Check if token already exists
    if os.path.exists(TOKEN_FILE):
        try:
            from google.oauth2.credentials import Credentials
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            print(f"[INFO] Found existing token at {TOKEN_FILE}")
            
            # Check if token is valid
            if creds.valid:
                print("[SUCCESS] Existing token is valid!")
                return True
            
            # Try to refresh if expired
            if creds.expired and creds.refresh_token:
                print("[INFO] Token expired, attempting to refresh...")
                try:
                    creds.refresh(Request())
                    # Save the refreshed token
                    with open(TOKEN_FILE, 'w') as token:
                        token.write(creds.to_json())
                    print("[SUCCESS] Token refreshed successfully!")
                    return True
                except Exception as e:
                    print(f"[WARN] Could not refresh token: {e}")
                    print("[INFO] Will run new OAuth flow...")
                    creds = None
        except Exception as e:
            print(f"[WARN] Could not load existing token: {e}")
            print("[INFO] Will run new OAuth flow...")
            creds = None
    
    # If no valid credentials, run OAuth flow
    if not creds:
        print("\n[INFO] Starting OAuth flow...")
        print("[INFO] A browser window will open for you to sign in to Google")
        print("[INFO] Make sure you're signed in to the correct Gmail account\n")
        
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)
            
            # Save the token for future use
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
            
            print(f"\n[SUCCESS] Token saved to {TOKEN_FILE}")
            print("[SUCCESS] Gmail OAuth setup completed!")
            return True
            
        except Exception as e:
            print(f"\n[ERROR] OAuth flow failed: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = setup_gmail_oauth()
    if success:
        print("\n" + "=" * 60)
        print("Setup completed successfully!")
        print("You can now use the Gmail API to send emails.")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("Setup failed. Please check the error messages above.")
        print("=" * 60)
        sys.exit(1)
