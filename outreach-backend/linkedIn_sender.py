#!/usr/bin/env python3
"""
LinkedIn sender module for outreach campaigns.
Sends LinkedIn messages using Playwright automation.
"""
import os
import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright

try:
    import pyperclip
except Exception:
    pyperclip = None

from config import PLAYWRIGHT_STORAGE_LINKEDIN, SEND_MIN_DELAY_MS, SEND_MAX_DELAY_MS
import api_client


class LinkedInSender:
    """
    Handles LinkedIn message sending via Playwright automation.
    Manages browser sessions, login state, and message delivery.
    """
    
    def __init__(
        self,
        storage_path: str = PLAYWRIGHT_STORAGE_LINKEDIN,
        send_min_delay_ms: int = SEND_MIN_DELAY_MS,
        send_max_delay_ms: int = SEND_MAX_DELAY_MS,
    ):
        # Normalize storage path to absolute path
        if not os.path.isabs(storage_path):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            storage_path = os.path.join(script_dir, storage_path)

        self.storage_path = os.path.abspath(storage_path)
        self.send_min_delay_ms = send_min_delay_ms
        self.send_max_delay_ms = send_max_delay_ms

        # Ensure storage directory exists
        self._ensure_dir(self.storage_path)

    # ----------------- Private Helper Methods -----------------

    def _ensure_dir(self, path: str):
        """Create parent directory if it doesn't exist."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    def _is_logged_in(self, page) -> bool:
        """Detect if user is logged into LinkedIn."""
        try:
            # Check for multiple indicators that user is logged in
            indicators = [
                "nav.global-nav",
                "div[data-test-id='nav-global-nav']",
                "div[data-test-app-aware-link='feed']",
                "button[aria-label*='Messaging']",
            ]
            for indicator in indicators:
                if page.locator(indicator).count() > 0:
                    return True

            # Check URL - if we're on login page, not logged in
            current_url = page.url.lower()
            if "login" in current_url or "challenge" in current_url:
                return False
            
            # If we're on a profile page (has /in/ in URL), likely logged in
            if "/in/" in current_url and "login" not in current_url:
                return True
            
            return False
        except Exception as e:
            print(f"[DEBUG] Login check error: {e}")
            return False

    def _wait_for_login(self, page, max_wait_seconds: int = 600) -> bool:
        """Wait for user to manually log in to LinkedIn."""
        print("\n[LOGIN] Please log in manually in the opened browser window.")
        print(f"[LOGIN] You have {max_wait_seconds // 60} minutes to complete login (2FA, verification, etc.)")
        print("[LOGIN] The script will automatically detect when you're logged in...")

        start_time = time.time()
        check_interval = 3  # Check every 3 seconds
        last_status_message = 0
        status_interval = 15  # Print status every 15 seconds

        while time.time() - start_time < max_wait_seconds:
            try:
                elapsed = time.time() - start_time
                remaining = max_wait_seconds - elapsed
                current_url = page.url

                # Check if logged in
                if self._is_logged_in(page):
                    print(f"\n[SUCCESS] Login detected after {int(elapsed)} seconds! Proceeding...")
                    time.sleep(3)  # Let page settle
                    return True

                # Print status periodically
                if elapsed - last_status_message >= status_interval:
                    minutes_remaining = int(remaining // 60)
                    seconds_remaining = int(remaining % 60)

                    if "login" in current_url.lower() or "challenge" in current_url.lower():
                        print(f"[LOGIN] Still waiting for login... ({minutes_remaining}m {seconds_remaining}s remaining)")
                    elif "linkedin.com/in/" in current_url.lower():
                        print(f"[LOGIN] On profile page, checking login status... ({minutes_remaining}m {seconds_remaining}s remaining)")
                    else:
                        print(f"[LOGIN] Monitoring login status... ({minutes_remaining}m {seconds_remaining}s remaining)")

                    last_status_message = elapsed

                time.sleep(check_interval)
            except Exception as e:
                print(f"[DEBUG] Error checking login status: {e}")
                time.sleep(check_interval)

        elapsed_total = int(time.time() - start_time)
        print(f"\n[WARN] Login wait timeout reached after {elapsed_total // 60} minutes.")
        print("[WARN] Proceeding anyway - please ensure you are logged in...")
        return False

    def _extract_first_name_from_url(self, profile_url: str) -> str:
        """Extract first name from LinkedIn profile URL."""
        try:
            import re
            # Remove domain to get path
            path = re.sub(r"https?://[^/]+/", "", profile_url).strip("/")
            parts = path.split("/")
            
            # Handle /in/first-last-123 format
            if parts and parts[0] == "in" and len(parts) > 1:
                handle = parts[1]
            else:
                handle = parts[0] if parts else ""
            
            # Extract first token before delimiter
            token = re.split(r"[-_\.+]", handle)[0]
            token = re.sub(r"\d+", "", token)  # Remove digits
            token = token.strip()
            
            return token.capitalize() if token else "there"
        except Exception:
            return "there"

    def _get_linkedin_url_from_contact(self, contact: dict) -> str:
        """Extract LinkedIn profile URL from contact data."""
        # Try direct linkedin field first
        linkedin_url = contact.get("linkedin")
        if isinstance(linkedin_url, str) and linkedin_url.startswith("http"):
            return linkedin_url
        
        # Try other common field names
        for key in ("linkedin_url", "profile_url", "url"):
            val = contact.get(key)
            if isinstance(val, str) and "linkedin.com" in val and val.startswith("http"):
                return val
        
        # Try nested socials
        socials = contact.get("socials") or {}
        if isinstance(socials, dict):
            li = socials.get("linkedin") or socials.get("linkedin_url")
            if isinstance(li, str) and li.startswith("http"):
                return li
        
        raise ValueError(f"No LinkedIn profile URL found in contact {contact.get('id')}")

    def _personalize_message(self, first_name: str, base_message: str) -> str:
        """Personalize message with first name."""
        if "{first_name}" in base_message or "{{first_name}}" in base_message:
            return base_message.replace("{first_name}", first_name).replace("{{first_name}}", first_name)
        return f"Hi {first_name} — " + base_message

    # ----------------- Core Message Sending -----------------

    def send_message(self, profile_url: str, message: str, actually_send: bool = False):
        """
        Send a LinkedIn message to a specific profile.
        
        Args:
            profile_url: LinkedIn profile URL (e.g., https://www.linkedin.com/in/username/)
            message: Message text to send
            actually_send: If True, actually sends the message. If False, drafts only.
        """
        storage = self.storage_path
        self._ensure_dir(storage)
        storage_exists = os.path.exists(storage) and os.path.getsize(storage) > 0

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, slow_mo=150)

            # Load existing session if available
            context_options = {}
            if storage_exists:
                try:
                    context_options["storage_state"] = storage
                    print(f"[INFO] Loading saved session from: {storage}")
                except Exception as e:
                    print(f"[WARN] Could not load saved session: {e}")
                    print("[INFO] Will create new session...")

            context = browser.new_context(**context_options)
            page = context.new_page()

            print(f"[INFO] Opening LinkedIn profile: {profile_url}")
            page.goto(profile_url, wait_until="domcontentloaded", timeout=120_000)
            time.sleep(3)

            # Check if logged in
            is_logged_in = self._is_logged_in(page)

            if not is_logged_in:
                print("[INFO] Not logged in or session expired. Waiting for manual login...")
                login_success = self._wait_for_login(page, max_wait_seconds=600)

                if login_success or self._is_logged_in(page):
                    print("[INFO] Login successful! Navigating to profile...")
                    page.goto(profile_url, wait_until="domcontentloaded", timeout=120_000)
                    time.sleep(3)

                    if not self._is_logged_in(page):
                        print("[ERROR] Login verification failed. Please try again.")
                        input("[INFO] Press ENTER to close browser... ")
                        context.close()
                        browser.close()
                        return

                    # Save session after successful login
                    try:
                        context.storage_state(path=storage)
                        print(f"[SUCCESS] Session saved to: {storage}")
                        print("[INFO] Next time you run this, you won't need to log in again!")
                    except Exception as e:
                        print(f"[ERROR] Could not save session: {e}")
                else:
                    print("[ERROR] Login was not completed in time.")
                    input("[INFO] Press ENTER to close browser... ")
                    context.close()
                    browser.close()
                    return
            else:
                print("[INFO] Already logged in via saved session!")
                if profile_url not in page.url:
                    print(f"[INFO] Navigating to profile: {profile_url}")
                    page.goto(profile_url, wait_until="domcontentloaded", timeout=120_000)
                    time.sleep(2)

                # Verify session is still valid
                if not self._is_logged_in(page):
                    print("[WARN] Saved session appears invalid. Will wait for re-login...")
                    self._wait_for_login(page, max_wait_seconds=600)
                    page.goto(profile_url, wait_until="domcontentloaded", timeout=120_000)
                    time.sleep(2)
                    try:
                        context.storage_state(path=storage)
                        print(f"[SUCCESS] Updated session saved to: {storage}")
                    except Exception as e:
                        print(f"[WARN] Could not save updated session: {e}")

            try:
                # Wait for page to fully load
                print("[INFO] Waiting for profile page to fully load...")
                time.sleep(3)

                # Scroll to top
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(1)

                print("[INFO] Searching for Message button...")

                # Multiple selectors to find Message button
                selectors = [
                    "button[aria-label*='Message']",
                    "button:has-text('Message')",
                    "button.artdeco-button:has-text('Message')",
                    "button.pvs-profile-actions__action:has-text('Message')",
                    "button[data-control-name='message_profile']",
                    "//button[contains(text(), 'Message')]",
                    "//span[contains(text(), 'Message')]/ancestor::button",
                ]

                visible_button = None

                for selector in selectors:
                    try:
                        if selector.startswith("//"):
                            buttons = page.locator(f"xpath={selector}")
                        else:
                            buttons = page.locator(selector)

                        count = buttons.count()
                        print(f"[DEBUG] Found {count} buttons with selector: {selector}")

                        if count > 0:
                            for i in range(count):
                                btn = buttons.nth(i)
                                try:
                                    if btn.is_visible(timeout=1000):
                                        visible_button = btn
                                        print(f"[INFO] Found visible Message button using selector: {selector}")
                                        break
                                except Exception:
                                    continue

                            if visible_button:
                                break
                    except Exception as e:
                        print(f"[DEBUG] Selector {selector} failed: {e}")
                        continue

                # Fallback: search all buttons for "Message" text
                if not visible_button:
                    print("[WARN] Standard selectors failed, trying broader search...")
                    try:
                        all_buttons = page.locator("button").all()
                        for btn in all_buttons:
                            try:
                                text = btn.inner_text().lower()
                                if "message" in text and btn.is_visible(timeout=500):
                                    visible_button = btn
                                    print("[INFO] Found Message button via text search")
                                    break
                            except Exception:
                                continue
                    except Exception as e:
                        print(f"[DEBUG] Text search failed: {e}")

                if not visible_button:
                    print("[ERROR] Could not find Message button. Please check the page manually.")
                    print("[INFO] The browser will stay open for you to review.")
                    input("[INFO] Press ENTER to close the browser... ")
                    context.close()
                    browser.close()
                    return

                # Scroll button into view
                print("[INFO] Scrolling Message button into view...")
                element_handle = visible_button.element_handle()
                page.evaluate(
                    "(el)=>el.scrollIntoView({behavior:'smooth',block:'center'})",
                    element_handle,
                )
                page.wait_for_timeout(1000)

                # Click Message button
                print("[INFO] Clicking Message button...")
                try:
                    visible_button.hover(timeout=2000)
                    page.wait_for_timeout(300)
                    visible_button.click(timeout=3000)
                    print("[INFO] Message button clicked successfully")
                except Exception as e:
                    print(f"[WARN] Normal click failed: {e}, retrying with JS click...")
                    try:
                        page.evaluate("(el)=>el.click()", element_handle)
                        print("[INFO] JS click executed")
                    except Exception as e2:
                        print(f"[ERROR] JS click also failed: {e2}")
                        raise

                # Wait for message editor
                print("[INFO] Waiting for message editor to appear...")
                editor_selectors = [
                    "div[contenteditable='true'][aria-label*='message']",
                    "div.msg-form__contenteditable[contenteditable='true']",
                    "div.msg-form__message-texteditor [contenteditable='true']",
                    "div.msg-form__msg-content-container [contenteditable='true']",
                    "div[role='textbox'][contenteditable='true']",
                    "div[contenteditable='true']",
                ]

                editor = None
                for selector in editor_selectors:
                    try:
                        page.wait_for_selector(selector, timeout=5000, state="visible")
                        editor = page.locator(selector).first
                        if editor.is_visible():
                            print(f"[INFO] Found message editor with selector: {selector}")
                            break
                    except Exception:
                        continue

                if not editor or not editor.is_visible():
                    print("[ERROR] Message editor did not appear. Please check manually.")
                    print("[INFO] Browser will stay open for review.")
                    input("[INFO] Press ENTER to close... ")
                    context.close()
                    browser.close()
                    return

                time.sleep(1)

                # Type message
                print("[INFO] Focusing editor and pasting message...")
                editor.click()
                page.wait_for_timeout(10)

                # Try clipboard paste for speed, fallback to typing
                if pyperclip is not None:
                    try:
                        pyperclip.copy(message)
                        page.keyboard.press("Control+V")
                    except Exception:
                        editor.press_sequentially(message, delay=random.uniform(25, 60))
                else:
                    editor.press_sequentially(message, delay=random.uniform(25, 60))

                # Random delay before send
                delay = random.uniform(
                    self.send_min_delay_ms / 1000,
                    self.send_max_delay_ms / 1000,
                )
                time.sleep(delay)

                # Send or draft
                if actually_send:
                    try:
                        page.keyboard.press("Control+Enter")
                        print(f"[SUCCESS] Sent message to {profile_url}!")
                        time.sleep(2)
                    except Exception as e:
                        print(f"[WARN] First Ctrl+Enter failed: {e}")
                        page.wait_for_timeout(300)
                        editor.click()
                        page.keyboard.press("Control+Enter")
                        print(f"[SUCCESS] Triggered send via Ctrl+Enter (retry) for {profile_url}")
                        time.sleep(2)
                else:
                    print(f"[DRAFT] Drafted LinkedIn message for {profile_url} (not sent).")

            except Exception as e:
                print(f"[ERROR] Error during message sending: {e}")
                import traceback
                traceback.print_exc()
                print("[INFO] Browser will stay open for review.")
                try:
                    input("[INFO] Press ENTER to close the browser... ")
                except (EOFError, KeyboardInterrupt):
                    print("[INFO] Closing browser...")

            # Keep browser open in draft mode
            if not actually_send:
                print("[INFO] Draft mode - keeping browser open for review.")
                try:
                    input("[INFO] Press ENTER to close the browser... ")
                except (EOFError, KeyboardInterrupt):
                    print("[INFO] Closing browser...")

            context.close()
            browser.close()
            print("[INFO] Browser closed.")

    # ----------------- Campaign Methods -----------------

    def send_to_contact(self, contact_id: int, campaign_id: int, actually_send: bool = False):
        """
        Send LinkedIn message to a specific contact.
        
        Args:
            contact_id: Contact ID from API
            campaign_id: Campaign ID to get message template
            actually_send: If True, sends message. If False, drafts only.
        """
        try:
            # STEP 1: Check if already contacted (only if actually sending)
            if actually_send:
                print(f"[CHECK] Checking if contact {contact_id} already contacted...")
                if api_client.check_if_already_contacted(campaign_id, contact_id, "linkedin"):
                    print(f"[SKIP] Contact {contact_id} already has outbound LinkedIn log. Skipping.")
                    return
            
            # Get contact details from API
            print(f"[INFO] Fetching contact {contact_id}...")
            contact = api_client.get_contact(contact_id)
            
            # Extract LinkedIn URL
            profile_url = self._get_linkedin_url_from_contact(contact)
            print(f"[INFO] LinkedIn URL: {profile_url}")
            
            # Get campaign message template
            base_message = api_client.get_campaign_message_text(campaign_id)
            
            # Personalize message
            first_name = contact.get("first_name") or self._extract_first_name_from_url(profile_url)
            message = self._personalize_message(first_name, base_message)
            
            # Send message
            self.send_message(profile_url, message, actually_send=actually_send)
            
            # Log to API if sent successfully
            if actually_send:
                try:
                    api_client.log_contact_outreach(
                        campaign_id=campaign_id,
                        contact_id=contact_id,
                        channel="linkedin",
                        subject=None,  # LinkedIn doesn't have subject
                        body=message
                    )
                    print(f"[LOG] Successfully logged outreach for contact {contact_id}")
                except Exception as log_error:
                    print(f"[WARN] Failed to log outreach: {log_error}")
            
        except Exception as e:
            print(f"[ERROR] Failed to send to contact {contact_id}: {e}")
            import traceback
            traceback.print_exc()

    def run_campaign(self, campaign_id: int, contact_ids: list, actually_send: bool = False):
        """
        Run LinkedIn campaign for multiple contacts.
        
        Args:
            campaign_id: Campaign ID
            contact_ids: List of contact IDs to message
            actually_send: If True, sends messages. If False, drafts only.
        """
        print("=" * 60)
        print(f"Starting LinkedIn Campaign {campaign_id}")
        print(f"Contacts to message: {len(contact_ids)}")
        print(f"Mode: {'SEND' if actually_send else 'DRAFT'}")
        print("=" * 60)
        
        success_count = 0
        
        for idx, contact_id in enumerate(contact_ids, 1):
            print(f"\n[{idx}/{len(contact_ids)}] Processing contact {contact_id}...")
            try:
                self.send_to_contact(contact_id, campaign_id, actually_send=actually_send)
                success_count += 1
            except Exception as e:
                print(f"[ERROR] Failed to process contact {contact_id}: {e}")
        
        print("\n" + "=" * 60)
        print(f"Campaign Complete: {success_count}/{len(contact_ids)} messages processed")
        print("=" * 60)


# For backward compatibility and testing
if __name__ == "__main__":
    sender = LinkedInSender()
    
    # Test with a profile URL directly
    profile_url = "https://www.linkedin.com/in/paul-bryzek/"
    message = (
        "Hi Paul — I'm reaching out from CarbonSustain to share updates around our "
        "AI-driven carbon accounting platform. Would love to explore collaboration!"
    )
    sender.send_message(profile_url, message, actually_send=False)