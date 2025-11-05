#!/usr/bin/env python3
"""
Direct test of the email sender functionality without API dependencies.
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the email sender directly
from outreach.email_sender import send_email_gmail

def test_email_sender_direct():
    """Test the email sender directly without API calls."""
    print("Testing Email Sender Directly...")
    print("=" * 50)
    
    try:
        print("Testing Gmail email sender...")
        
        # Test email details
        subject = "Test Email - Climate Reach Finder"
        body = """
        Hi there,
        
        This is a test email from the Climate Reach Finder automation system.
        
        If you're seeing this, the email sender is working correctly!
        
        Best regards,
        Climate Reach Finder Team
        """
        
        # Use a test email address
        test_email = "test@example.com"
        
        print(f"Attempting to send email to: {test_email}")
        print(f"Subject: {subject}")
        print("Body preview:", body.strip()[:100] + "...")
        print()
        print("This will open Gmail in your browser for authentication...")
        print("Note: This is a test - the email won't actually be sent.")
        print()
        
        # Call the email sender function
        send_email_gmail(subject, body, test_email)
        
        print("Email sender function completed!")
        print("If Gmail opened successfully, the email sender is working!")
        
        return True
        
    except Exception as e:
        print(f"Error testing email sender: {e}")
        print("This might be expected if Gmail credentials aren't set up yet.")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_email_sender_direct()
    if success:
        print("\nEmail sender test completed!")
    else:
        print("\nEmail sender test had issues.")
        print("   This might be normal if Gmail setup is needed.")
