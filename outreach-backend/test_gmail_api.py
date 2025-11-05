"""Test Gmail API email sending directly."""
import sys
import os
from pathlib import Path

# Change to the parent directory so relative imports work
parent_dir = Path(__file__).parent.parent
os.chdir(parent_dir)
sys.path.insert(0, str(parent_dir))

# Now import using the package structure
from outreach_backend.email_sender import send_gmail_html

if __name__ == "__main__":
    print("[INFO] Testing Gmail API send to pbryzek@berkeley.edu...")
    try:
        send_gmail_html(
            "pbryzek@berkeley.edu",
            "Gmail API HTML test",
            "<b>Hello</b> world via Gmail API"
        )
        print("[SUCCESS] Test completed!")
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()

