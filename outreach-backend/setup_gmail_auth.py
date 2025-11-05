#!/usr/bin/env python3
"""
Gmail Authentication Setup Script
This script will open a browser window for Gmail login and save the authentication state.
"""

import os
import sys
from playwright.sync_api import sync_playwright

def setup_gmail_auth():
    """Setup Gmail authentication by opening browser and saving login state."""
    print("Setting up Gmail Authentication...")
    print("=" * 50)
    
    # Ensure the storage directory exists
    storage_dir = "outreach/.storage"
    if not os.path.exists(storage_dir):
        os.makedirs(storage_dir)
        print(f"Created storage directory: {storage_dir}")
    
    storage_path = "outreach/.storage/gmail.json"
    
    try:
        with sync_playwright() as p:
            print("Launching browser for Gmail authentication...")
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            
            print("Opening Gmail login page...")
            page.goto('https://mail.google.com/')
            
            print("\n" + "="*50)
            print("IMPORTANT: Complete the Gmail login process in the browser window")
            print("1. Log in to your Gmail account")
            print("2. Complete any 2FA if prompted")
            print("3. Make sure you can access Gmail normally")
            print("4. Then come back here and press Enter")
            print("="*50)
            
            try:
                input("\nPress Enter after you've successfully logged into Gmail...")
            except EOFError:
                print("\nInput interrupted. Saving current state...")
            
            print("Saving authentication state...")
            context.storage_state(path=storage_path)
            print(f"Authentication saved to: {storage_path}")
            
            print("Closing browser...")
            browser.close()
            
            print("\nGmail authentication setup completed!")
            print("The email sender can now automatically authenticate with Gmail.")
            
            return True
            
    except Exception as e:
        print(f"Error setting up Gmail authentication: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = setup_gmail_auth()
    if success:
        print("\nGmail setup completed successfully!")
        print("You can now run the email sender automation.")
    else:
        print("\nGmail setup failed. Please try again.")