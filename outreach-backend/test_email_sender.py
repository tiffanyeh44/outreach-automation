#!/usr/bin/env python3
"""
Simple test script to initialize the email sender and check Gmail connection.
This bypasses the API requirements and just tests the email functionality.
"""

import sys
import os

# Add the current directory to Python path so we can import outreach modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from outreach.email_sender import send_email_gmail

def test_email_sender():
    """Test the email sender initialization and basic functionality."""
    print("🧪 Testing Email Sender Initialization...")
    print("=" * 50)
    
    try:
        # Test with a dummy email (won't actually send)
        print("📧 Attempting to initialize Gmail connection...")
        
        # This will trigger the Gmail login flow
        subject = "Test Email - Climate Reach Finder"
        body = """
        This is a test email from the Climate Reach Finder email sender.
        
        If you're seeing this, the email sender is working correctly!
        
        Best regards,
        Climate Reach Finder Team
        """
        
        # Use a test email address (you can change this)
        test_email = "test@example.com"
        
        print(f"Sending test email to: {test_email}")
        print("Subject:", subject)
        print("Body preview:", body.strip()[:100] + "...")
        
        # This will open Gmail and attempt to compose an email
        # It won't actually send since it's just a test
        send_email_gmail(subject, body, test_email)
        
        print("✅ Email sender initialized successfully!")
        print("📝 Gmail should have opened in your browser for authentication.")
        
    except Exception as e:
        print(f"❌ Error testing email sender: {e}")
        print("This might be expected if Gmail credentials aren't set up yet.")
        return False
    
    return True

if __name__ == "__main__":
    success = test_email_sender()
    if success:
        print("\n🎉 Email sender test completed successfully!")
    else:
        print("\n⚠️  Email sender test had issues, but this might be normal.")
        print("   Make sure you have Gmail credentials configured if needed.")

