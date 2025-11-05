#!/usr/bin/env python3
"""
Simple Gmail Login Setup
Uses the exact code from the error message to set up Gmail authentication.
"""

import os
from playwright.sync_api import sync_playwright

def setup_gmail_login():
    """Setup Gmail login using the exact method from the error message."""
    print("Setting up Gmail authentication...")
    
    # Create storage directory if it doesn't exist
    storage_dir = "outreach/.storage"
    if not os.path.exists(storage_dir):
        os.makedirs(storage_dir)
        print(f"Created directory: {storage_dir}")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            page.goto('https://mail.google.com/')
            
            print("\nBrowser opened! Please:")
            print("1. Log in to Gmail completely")
            print("2. Make sure you can see your inbox")
            print("3. Then press Enter here to save the login state")
            
            input('Log in to Gmail fully, then press Enter to save storage state: ')
            context.storage_state(path='outreach/.storage/gmail.json')
            browser.close()
            
            print("Gmail authentication saved successfully!")
            print("You can now use the email sender automation.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    setup_gmail_login()
