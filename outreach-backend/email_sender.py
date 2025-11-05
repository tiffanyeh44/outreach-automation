import base64
from typing import Optional

from email.mime.text import MIMEText

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

from .config import GMAIL_TOKEN_PATH, GMAIL_SCOPES, SENDER_EMAIL
from . import api_client


def _load_gmail_credentials() -> Credentials:
    """
    Load Gmail API credentials from a token json file.
    Assumes the OAuth flow has already been completed and token saved.
    """
    return Credentials.from_authorized_user_file(GMAIL_TOKEN_PATH, GMAIL_SCOPES)


def send_gmail_html(to_email: str, subject: str, html_body: str, sender: Optional[str] = None):
    creds = _load_gmail_credentials()
    service = build("gmail", "v1", credentials=creds)

    msg = MIMEText(html_body, "html")
    msg["To"] = to_email
    msg["From"] = sender or SENDER_EMAIL or "me"
    msg["Subject"] = subject

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    try:
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        print(f"[SUCCESS] Sent email to {to_email}")
    except HttpError as e:
        print(f"[ERROR] Gmail API error for {to_email}: {e}")


def run_campaign_emails(campaign_id: int, contact_method: int = 2):
    """
    Send HTML emails for a campaign using Gmail API.
    contact_method defaults to 2 (email), adjust if your API differs.
    """
    subject, html_body = api_client.get_campaign_email_content(campaign_id)
    contacts = api_client.get_campaign_contacts(campaign_id, contact_method)
    if not contacts:
        print("[WARN] No contacts for this campaign/method")
        return

    for item in contacts:
        contact_id = item.get("contact") or item.get("contact_id")
        if not contact_id:
            print("[WARN] Skipping item without contact id", item)
            continue
        contact = api_client.get_contact(contact_id)

        # Resolve an email field from common keys
        to_email = None
        for key in ("email", "email_address", "primary_email"):
            val = contact.get(key)
            if isinstance(val, str) and "@" in val:
                to_email = val
                break
        if not to_email:
            print(f"[WARN] No email for contact {contact_id}, skipping")
            continue

        send_gmail_html(to_email, subject, html_body)

if __name__ == "__main__":
    # Simple smoke test: send a short HTML email to TEST_EMAIL if provided
    from .config import TEST_EMAIL
    if not TEST_EMAIL:
        print("[INFO] TEST_EMAIL not set. Set env var TEST_EMAIL to run the smoke test.")
    else:
        print(f"[INFO] Sending Gmail API smoke test to {TEST_EMAIL}...")
        send_gmail_html(TEST_EMAIL, "Gmail API HTML test", "<b>Hello</b> world via Gmail API")
# outreach/email_sender.py
import os
import re
import time
import json
import urllib.parse
import requests
import signal
import random
import pyperclip
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from playwright.sync_api import sync_playwright
from .config import TEST_EMAIL
from .api_client import get_campaign_email_content

# ===== Config =====
EMAIL_METHOD = 2
LINKEDIN_METHOD = 4
DEFAULT_BASE_URL = "https://d21bevdvb0ruaa.cloudfront.net/"

API_BASE_URL = os.getenv("API_BASE_URL", DEFAULT_BASE_URL).strip()
API_TOKEN = os.getenv("API_TOKEN")  # optional; set if your API requires auth

# jitter between sends (ms)
SEND_MIN_DELAY_MS = int(os.getenv("SEND_MIN_DELAY_MS", "800"))
SEND_MAX_DELAY_MS = int(os.getenv("SEND_MAX_DELAY_MS", "1800"))

# Playwright / Gmail settings
PLAYWRIGHT_BROWSER = os.getenv(
    "PLAYWRIGHT_BROWSER", "chromium")  # chromium|firefox|webkit
# default headed for debugging; set PLAYWRIGHT_HEADLESS=1 to run headless once stable
PLAYWRIGHT_HEADLESS = os.getenv(
    "PLAYWRIGHT_HEADLESS", "0") in ("1", "true", "yes")
PLAYWRIGHT_STORAGE = os.getenv(
    "PLAYWRIGHT_STORAGE", "outreach/.storage/gmail.json")

# If you want to dry-run the email send without clicking "Send", set to 1
DRY_RUN_EMAIL = os.getenv("DRY_RUN_EMAIL", "0") in ("1", "true", "yes")

# Choose Gmail account index (0 = first account)
GMAIL_ACCOUNT_INDEX = int(os.getenv("GMAIL_ACCOUNT_INDEX", "0"))

# Timeouts (ms) - Increased for better reliability
PW_SHORT_TIMEOUT = int(os.getenv("PW_SHORT_TIMEOUT", "10000"))
PW_LONG_TIMEOUT = int(os.getenv("PW_LONG_TIMEOUT", "30000"))
PW_XLONG_TIMEOUT = int(os.getenv("PW_XLONG_TIMEOUT", "60000"))

# Overall operation timeout (seconds)
OPERATION_TIMEOUT = int(os.getenv("OPERATION_TIMEOUT", "120"))

# ===== Helpers =====


def _normalize_base(url: str) -> str:
    if not re.match(r"^https?://", url):
        url = "https://" + url
    return url.rstrip("/")


BASE = _normalize_base(API_BASE_URL)


def _abs_url(path: str) -> str:
    return f"{BASE}/{path.lstrip('/')}"


def _headers() -> Dict[str, str]:
    h = {"Accept": "application/json"}
    if API_TOKEN:
        h["Authorization"] = f"Token {API_TOKEN}"
    return h


def _get(url_or_path: str, timeout: int = 20) -> requests.Response:
    url = url_or_path if url_or_path.startswith(
        "http") else _abs_url(url_or_path)
    r = requests.get(url, headers=_headers(), timeout=timeout)
    r.raise_for_status()
    return r


def _get_json(url_or_path: str) -> dict:
    return _get(url_or_path).json()


def _paginate(path: str) -> Iterable[dict]:
    """Yield items from a DRF-style paginated endpoint."""
    url = _abs_url(path)
    while url:
        data = _get(url).json()
        for item in data.get("results", []):
            yield item
        url = data.get("next")


def _ensure_dir(path: str):
    """Ensure directory exists for storage files."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _sleep_jitter():
    # simple bounded jitter
    ms = random.randint(SEND_MIN_DELAY_MS, SEND_MAX_DELAY_MS)
    time.sleep(ms / 1000.0)


class TimeoutError(Exception):
    """Custom timeout error for email operations."""
    pass


def _timeout_handler(signum, frame):
    """Signal handler for timeout."""
    raise TimeoutError(f"Operation timed out after {OPERATION_TIMEOUT} seconds")


def _with_timeout(func, *args, **kwargs):
    """Execute function with timeout protection."""
    if hasattr(signal, 'SIGALRM'):  # Unix systems
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(OPERATION_TIMEOUT)
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    else:  # Windows - use threading timeout
        import threading
        import queue
        
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        
        def target():
            try:
                result = func(*args, **kwargs)
                result_queue.put(result)
            except Exception as e:
                exception_queue.put(e)
        
        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(timeout=OPERATION_TIMEOUT)
        
        if thread.is_alive():
            raise TimeoutError(f"Operation timed out after {OPERATION_TIMEOUT} seconds")
        
        if not exception_queue.empty():
            raise exception_queue.get()
        
        if not result_queue.empty():
            return result_queue.get()
        
        raise RuntimeError("Function execution failed without exception")


# ===== API wrappers =====
def get_campaign(campaign_id: int) -> dict:
    # Called ONCE per run; do NOT call inside loops.
    return _get_json(f"outreach/campaigns/{campaign_id}/")


def get_campaign_contact_methods(campaign_id: int, method_id: int) -> List[dict]:
    path = f"outreach/campaign-contact-methods/?campaign={campaign_id}&contact_method={method_id}"
    return list(_paginate(path))


def get_contact(contact_id: int) -> dict:
    return _get_json(f"outreach/contacts/{contact_id}/")


# ===== Your template hooks (replace with your real logic) =====
def render_email(campaign: dict, contact: dict) -> (str, str):
    subject = f"{campaign.get('name')} — Quick Intro"
    body = (
        f"Hi {contact.get('first_name') or 'there'},\n\n"
        f"…your email body…\n"
    )
    return subject, body


def render_linkedin(campaign: dict, contact: dict) -> str:
    return f"Hi {contact.get('first_name') or ''} — loved {campaign.get('name')}. Would you be open to a quick chat?"


# ===== Playwright Gmail sender =====
def _ensure_storage_state_exists():
    """Ensure storage directory exists for Gmail authentication."""
    _ensure_dir(PLAYWRIGHT_STORAGE)



def _is_logged_in_to_gmail(page) -> bool:
    """Check if we're properly logged into Gmail."""
    try:
        # Look for Gmail inbox elements that indicate we're logged in
        inbox_indicators = [
            "input[aria-label='Search mail']",
            "div[role=button][gh='cm']",  # Compose button
            "div[role='button'][data-tooltip^='Compose']",
            "table[role='grid']",  # Email list
            "div[gh='tm']"  # Toolbar area
        ]
        
        for indicator in inbox_indicators:
            if page.locator(indicator).count() > 0:
                return True
        
        # Also check if we're on a login page
        login_indicators = [
        "input[type='email'][name='identifier']",
        "div#identifierNext",
        "input[type='password'][name='Passwd']",
        "div#passwordNext",
        "div[role='heading']:has-text('Sign in')",
            "div[role='heading']:has-text('Choose an account')"
        ]
        
        for indicator in login_indicators:
            if page.locator(indicator).count() > 0:
                return False
                
        return False
    except Exception:
        return False


def _gmail_send_with_playwright(to_email: str, subject: str, body: str):
    """
    Opens Gmail, composes, and sends using the working method.
    Includes proper authentication handling and timeout tracking.
    """
    start_time = time.time()
    storage = PLAYWRIGHT_STORAGE
    _ensure_storage_state_exists()

    with sync_playwright() as p:
        print(f"[TIMEOUT] Starting Gmail send process for {to_email}...")
        
        # Check if we have existing authentication
        first_run = not os.path.exists(storage)
        print(f"[TIMEOUT] {'First run - authentication required' if first_run else 'Using saved authentication'}")
        
        browser = p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
        context = browser.new_context(
            storage_state=storage if not first_run else None,
            viewport={"width": 1440, "height": 900}
        )
        page = context.new_page()

        try:
            print("[TIMEOUT] Navigating to Gmail...")
            page.goto("https://mail.google.com/", timeout=120_000, wait_until="domcontentloaded")
            print(f"[TIMEOUT] Gmail loaded ({time.time() - start_time:.1f}s)")
            
            # Check if we need to log in
            time.sleep(2)  # Give page time to load
            is_logged_in = _is_logged_in_to_gmail(page)
            
            if not is_logged_in:
                print(">>> Gmail authentication required!")
                print(">>> Please log in to Gmail in the opened browser window.")
                print(">>> Complete any 2FA or security prompts.")
                print(">>> Make sure you can see your Gmail inbox.")
                print(">>> Then press ENTER here to continue...")
                
                # Wait for user to complete login
                try:
                    input()
                except (EOFError, KeyboardInterrupt):
                    print("\nLogin setup interrupted.")
                    raise RuntimeError("Gmail authentication was interrupted")
                
                # Save authentication state
                try:
                    context.storage_state(path=storage)
                    print("[TIMEOUT] Authentication saved successfully")
                except Exception as e:
                    print(f"[WARNING] Could not save authentication: {e}")
            else:
                print("[TIMEOUT] Already logged in to Gmail")

            # Wait a moment for Gmail to fully load
            time.sleep(1)

            if DRY_RUN_EMAIL:
                print(f"[DRY-RUN] Would send Gmail to {to_email}: {subject}")
            else:
                print("[TIMEOUT] Starting compose process...")
                
                # Compose new message using working method
                try:
                    print("[TIMEOUT] Clicking Compose button...")
                    page.click("text=Compose")
                    time.sleep(1)  # Wait for compose window to open
                    print(f"[TIMEOUT] Compose clicked ({time.time() - start_time:.1f}s)")
                except Exception as e:
                    raise RuntimeError(f"Failed to click Compose button after {time.time() - start_time:.1f}s: {e}")

                # Use test override if defined
                recipient = TEST_EMAIL or to_email
                print(f"[TIMEOUT] Setting recipient: {recipient}")
                
                try:
                    # Wait for recipient field to be ready
                    time.sleep(0.5)
                    page.keyboard.insert_text(recipient)
                    page.keyboard.press('Enter')
                    time.sleep(0.5)
                    print(f"[TIMEOUT] Recipient set ({time.time() - start_time:.1f}s)")
                except Exception as e:
                    raise RuntimeError(f"Failed to set recipient after {time.time() - start_time:.1f}s: {e}")
                
                try:
                    print("[TIMEOUT] Setting subject...")
                    page.fill("input[name='subjectbox']", subject)
                    time.sleep(0.5)
                    print(f"[TIMEOUT] Subject set ({time.time() - start_time:.1f}s)")
                except Exception as e:
                    raise RuntimeError(f"Failed to set subject after {time.time() - start_time:.1f}s: {e}")
                
            
                try:
                    print("[TIMEOUT] Setting message body...")
                    body_div = page.locator("div[aria-label='Message Body']")
                    body_div.click()
                    time.sleep(1)

                    page.evaluate("""
                        const editor = document.querySelector('div[aria-label="Message Body"]');
                        if (editor) {
                            editor.focus();
                            document.execCommand('insertHTML', false,
                                '<b>Hello</b> <i>world</i> <br><a href="https://carbonsustain.io">Visit site</a>');
                        }
                    """)
                
                    """ if "<" in body and ">" in body:
                        pyperclip.copy(body)
                        page.keyboard.press("Control+v")
                    else:
                        page.keyboard.type(body) """
                    print(f"[TIMEOUT] Body set ({time.time() - start_time:.1f}s)")
                except Exception as e:
                    raise RuntimeError(f"Failed to set body after {time.time() - start_time:.1f}s: {e}")
                
                # Random human-like delay
                delay = random.uniform(SEND_MIN_DELAY_MS/1000, SEND_MAX_DELAY_MS/1000)
                print(f"[TIMEOUT] Waiting {delay:.1f}s before sending...")
                time.sleep(delay)

                try:
                    print("[TIMEOUT] Sending email...")
                    page.keyboard.press('Control+Enter')
                    time.sleep(2)  # Wait for send confirmation
                    print(f"[EMAIL] Sent email to {recipient}")
                    print(f"[TIMEOUT] Email sent successfully ({time.time() - start_time:.1f}s)")
                except Exception as e:
                    raise RuntimeError(f"Failed to send email after {time.time() - start_time:.1f}s: {e}")
                
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[ERROR] Gmail send failed after {elapsed:.1f}s: {e}")
            raise

            # Always save authentication state before closing
        """ try:
                context.storage_state(path=storage)
        except Exception:
            pass
        context.close()
        browser.close() """


# ===== Orchestration senders =====
def send_email_gmail(subject: str, body: str, to_email: str) -> None:
    """
    Sends the email using your Gmail **client** (web UI) automated by Playwright.
    Uses the working method with proper selectors and timeout handling.
    """
    print(f"[TIMEOUT] Starting email send to {to_email} with {OPERATION_TIMEOUT}s timeout...")
    
    try:
        _with_timeout(_gmail_send_with_playwright, to_email=to_email, subject=subject, body=body)
        print(f"[SUCCESS] Email send completed successfully")
    except Exception as e:
        print(f"[ERROR] Email send failed: {e}")
        raise


def send_linkedin_message(linkedin_url: str, message: str, actually_send: bool = False) -> None:
    # Your existing LI flow (stubbed)
    action = "SEND" if actually_send else "DRY-RUN"
    print(f"🔗 [{action}] LI DM to {linkedin_url}: {message[:80]}…")



def render_email_from_campaign(campaign_id: int, contact: dict) -> tuple[str, str]:
    """
    Pull the real HTML email content from the API campaign.
    """
    subject, body_html = get_campaign_email_content(campaign_id)
    # Personalize first name placeholder if it exists
    first_name = contact.get("first_name", "there")
    body_html = body_html.replace("{{first_name}}", first_name)
    return subject, body_html

# ===== Orchestration =====
def run_campaign(campaign_id: int, do_email: bool = True, do_linkedin: bool = True, actually_send_li: bool = False) -> None:
    # 1) Fetch campaign ONCE (per your requirement)
    campaign = get_campaign(campaign_id)
    print(f"🎯 Campaign: {campaign.get('name')}")

    # 2) Email flow
    if do_email:
        print("📬 Fetching email contacts…")
        email_rows = get_campaign_contact_methods(campaign_id, EMAIL_METHOD)
        print(f"… got {len(email_rows)} campaign-contact-method rows (email).")
        for row in email_rows:
            contact = get_contact(row["contact"])
            to_email = (contact.get("email") or "").strip()
            if not to_email:
                print(
                    f"⏭️  No email for contact id {contact.get('id')}, skipping.")
                continue
            subject, body = render_email_from_campaign(campaign_id, contact)
            send_email_gmail(subject, body, to_email)
            _sleep_jitter()

    # 3) LinkedIn flow
    if do_linkedin:
        print("🔗 Fetching LinkedIn contacts…")
        li_rows = get_campaign_contact_methods(campaign_id, LINKEDIN_METHOD)
        print(f"… got {len(li_rows)} campaign-contact-method rows (linkedin).")
        for row in li_rows:
            contact = get_contact(row["contact"])
            li = (contact.get("linkedin") or contact.get(
                "linkedin_url") or "").strip()
            if not li:
                print(
                    f"⏭️  No LinkedIn for contact id {contact.get('id')}, skipping.")
                continue
            msg = render_linkedin(campaign, contact)
            send_linkedin_message(li, msg, actually_send=actually_send_li)
            _sleep_jitter()


# ===== CLI entry =====
if __name__ == "__main__":
    # Example: run both flows for campaign 3
    run_campaign(3, do_email=True, do_linkedin=True, actually_send_li=False)
