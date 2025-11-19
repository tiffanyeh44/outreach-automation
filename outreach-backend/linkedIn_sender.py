import os
import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright
import api_client

try:
    import pyperclip
except Exception:
    pyperclip = None
from config import PLAYWRIGHT_STORAGE_LINKEDIN, SEND_MIN_DELAY_MS, SEND_MAX_DELAY_MS


def _ensure_dir(path: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _is_logged_in(page):
    """Detect if user is logged into LinkedIn."""
    try:
        # Check for multiple indicators that user is logged in
        indicators = [
            "nav.global-nav",
            "div[data-test-id='nav-global-nav']",
            "div[data-test-app-aware-link='feed']",
            "button[aria-label*='Messaging']"
        ]
        for indicator in indicators:
            if page.locator(indicator).count() > 0:
                return True
        # Also check URL - if we're on login page, we're not logged in
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


def _wait_for_login(page, max_wait_seconds=600):
    """Wait for user to manually log in to LinkedIn.
    
    Args:
        page: Playwright page object
        max_wait_seconds: Maximum time to wait (default 10 minutes)
    """
    print("\n[LOGIN] Please log in manually in the opened browser window.")
    print(f"[LOGIN] You have {max_wait_seconds // 60} minutes to complete login (2FA, verification, etc.)")
    print("[LOGIN] The script will automatically detect when you're logged in...")
    
    start_time = time.time()
    check_interval = 3  # Check every 3 seconds (less frequent to reduce CPU)
    last_status_message = 0
    status_interval = 15  # Print status every 15 seconds
    
    while time.time() - start_time < max_wait_seconds:
        try:
            elapsed = time.time() - start_time
            remaining = max_wait_seconds - elapsed
            current_url = page.url
            
            # Check if we're logged in now
            if _is_logged_in(page):
                print(f"\n[SUCCESS] Login detected after {int(elapsed)} seconds! Proceeding...")
                time.sleep(3)  # Give page a moment to fully settle
                return True
            
            # Print status periodically (not every check to avoid spam)
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


def send_linkedin_message(profile_url: str, message: str, actually_send: bool = False):
    # Get absolute path for storage - if relative, make it relative to this file's directory
    if not os.path.isabs(PLAYWRIGHT_STORAGE_LINKEDIN):
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        storage = os.path.join(script_dir, PLAYWRIGHT_STORAGE_LINKEDIN)
    else:
        storage = PLAYWRIGHT_STORAGE_LINKEDIN
    
    storage = os.path.abspath(storage)
    _ensure_dir(storage)
    
    storage_exists = os.path.exists(storage) and os.path.getsize(storage) > 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=150)
        
        # Load existing storage state if available
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

        # Check if we need to log in
        is_logged_in = _is_logged_in(page)
        
        if not is_logged_in:
            print("[INFO] Not logged in or session expired. Waiting for manual login...")
            login_success = _wait_for_login(page, max_wait_seconds=600)  # 10 minutes
            
            # After login, verify we're logged in and navigate to profile
            if login_success or _is_logged_in(page):
                print("[INFO] Login successful! Navigating to profile...")
                page.goto(profile_url, wait_until="domcontentloaded", timeout=120_000)
                time.sleep(3)
                
                # Verify we're logged in before proceeding
                if not _is_logged_in(page):
                    print("[ERROR] Login verification failed. Please try again.")
                    input("[INFO] Press ENTER to close browser... ")
                    context.close()
                    browser.close()
                    return
                
                # Save the session immediately after successful login
                try:
                    context.storage_state(path=storage)
                    print(f"[SUCCESS] Session saved to: {storage}")
                    print("[INFO] Next time you run this, you won't need to log in again!")
                except Exception as e:
                    print(f"[ERROR] Could not save session: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("[ERROR] Login was not completed in time.")
                input("[INFO] Press ENTER to close browser... ")
                context.close()
                browser.close()
                return
        else:
            print("[INFO] Already logged in via saved session!")
            # Make sure we're on the profile page
            if profile_url not in page.url:
                print(f"[INFO] Navigating to profile: {profile_url}")
                page.goto(profile_url, wait_until="domcontentloaded", timeout=120_000)
                time.sleep(2)
            
            # Verify session is still valid by checking if we can see the page
            if not _is_logged_in(page):
                print("[WARN] Saved session appears invalid. Will wait for re-login...")
                _wait_for_login(page, max_wait_seconds=600)
                page.goto(profile_url, wait_until="domcontentloaded", timeout=120_000)
                time.sleep(2)
                # Save updated session
                try:
                    context.storage_state(path=storage)
                    print(f"[SUCCESS] Updated session saved to: {storage}")
                except Exception as e:
                    print(f"[WARN] Could not save updated session: {e}")

        try:
            # Wait a bit for page to fully load
            print("[INFO] Waiting for profile page to fully load...")
            time.sleep(3)
            
            # Scroll to top in case we're scrolled down
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(1)
            
            print("[INFO] Searching for Message button...")
            
            # Try multiple selectors for the Message button
            selectors = [
                "button[aria-label*='Message']",
                "button:has-text('Message')",
                "button.artdeco-button:has-text('Message')",
                "button.pvs-profile-actions__action:has-text('Message')",
                "button[data-control-name='message_profile']",
                "//button[contains(text(), 'Message')]",
                "//span[contains(text(), 'Message')]/ancestor::button"
            ]
            
            visible_button = None
            
            for selector in selectors:
                try:
                    if selector.startswith("//"):
                        # XPath selector
                        buttons = page.locator(f"xpath={selector}")
                    else:
                        # CSS selector
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
            
            if not visible_button:
                # Last resort: try to find any button containing "Message" text
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

            # Scroll the button into view
            print("[INFO] Scrolling Message button into view...")
            element_handle = visible_button.element_handle()
            page.evaluate(
                "(el)=>el.scrollIntoView({behavior:'smooth',block:'center'})", element_handle
            )
            page.wait_for_timeout(1000)  # Wait for scroll to complete

            print("[INFO] Clicking Message button...")
            try:
                # Try hovering first
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

            # Wait for the message editor to appear
            print("[INFO] Waiting for message editor to appear...")
            editor_selectors = [
                "div[contenteditable='true'][aria-label*='message']",
                "div.msg-form__contenteditable[contenteditable='true']",
                "div.msg-form__message-texteditor [contenteditable='true']",
                "div.msg-form__msg-content-container [contenteditable='true']",
                "div[role='textbox'][contenteditable='true']",
                "div[contenteditable='true']"
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
            
            time.sleep(1)  # Give editor a moment to be ready

            # Click and paste the message via clipboard for speed
            print("[INFO] Focusing editor and pasting message from clipboard...")
            editor.click()
            page.wait_for_timeout(10)  # ~10ms human-like lag

            if pyperclip is not None:
                try:
                    pyperclip.copy(message)
                    # Windows paste shortcut
                    page.keyboard.press("Control+V")
                except Exception:
                    # Fallback to slower typing if clipboard fails
                    editor.press_sequentially(message, delay=random.uniform(25, 60))
            else:
                # Fallback if pyperclip unavailable
                editor.press_sequentially(message, delay=random.uniform(25, 60))


            # Optional delay before send
            delay = random.uniform(SEND_MIN_DELAY_MS / 1000, SEND_MAX_DELAY_MS / 1000)
            time.sleep(delay)

            # sending message
            if actually_send:
                try:
                    page.keyboard.press("Control+Enter")
                    print(f"[SUCCESS] Sent message to {profile_url}!")
                    time.sleep(2)  # Brief pause before continuing
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
        
        # Only keep browser open if actually_send is False (draft mode)
        if not actually_send:
            print("[INFO] Draft mode - keeping browser open for review.")
            try:
                input("[INFO] Press ENTER to close the browser... ")
            except (EOFError, KeyboardInterrupt):
                print("[INFO] Closing browser...")
        
        context.close()
        browser.close()
        print("[INFO] Browser closed.")


def _extract_first_name_from_linkedin_url(profile_url: str) -> str:
    try:
        # Expecting formats like https://www.linkedin.com/in/first-last-123...
        import re
        path = re.sub(r"https?://[^/]+/", "", profile_url).strip("/")
        # Grab segment after 'in/' if present
        parts = path.split("/")
        if parts and parts[0] == "in" and len(parts) > 1:
            handle = parts[1]
        else:
            handle = parts[0] if parts else ""
        token = re.split(r"[-_\.+]", handle)[0]
        token = re.sub(r"\d+", "", token)  # remove trailing digits
        token = token.strip()
        return token.capitalize() if token else "there"
    except Exception:
        return "there"


def _resolve_profile_url_from_contact(contact: dict) -> str:
    for key in ("linkedin_url", "profile_url", "linkedin", "url"):
        val = contact.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val
    # nested social links pattern
    socials = contact.get("socials") or {}
    if isinstance(socials, dict):
        li = socials.get("linkedin") or socials.get("linkedin_url")
        if isinstance(li, str) and li.startswith("http"):
            return li
    raise ValueError("No LinkedIn profile URL found in contact record")


def _personalize_message(first_name: str, base_message: str) -> str:
    # If template includes a {first_name} placeholder, use it; else prepend greeting
    if "{first_name}" in base_message:
        return base_message.replace("{first_name}", first_name)
    return f"Hi {first_name} — " + base_message


def run_campaign_linkedin(campaign_id: int, actually_send: bool = False, contact_method: int = 4):
    """
    Run LinkedIn campaign - sends 2 messages:
    1. To all contacts from the API
    2. To the hardcoded profile: https://www.linkedin.com/in/cedricyxu/
    """
    print(f"[INFO] Running LinkedIn campaign {campaign_id} (contact_method={contact_method})")
    
    # Get campaign message
    base_message = api_client.get_campaign_message_text(campaign_id)
    
    # Get contacts from API
    contacts = api_client.get_campaign_contacts(campaign_id, contact_method)
    
    # Process API contacts
    if contacts:
        print(f"[INFO] Processing {len(contacts)} contacts from API...")
        for item in contacts:
            contact_id = item.get("contact") or item.get("contact_id")
            if not contact_id:
                print("[WARN] Skipping item without contact id", item)
                continue
            try:
                contact = api_client.get_contact(contact_id)
                profile_url = _resolve_profile_url_from_contact(contact)
                first_name = _extract_first_name_from_linkedin_url(profile_url)
                message = _personalize_message(first_name, base_message)
                send_linkedin_message(profile_url, message, actually_send=actually_send)
            except Exception as e:
                print(f"[ERROR] Failed processing contact {contact_id}: {e}")
    else:
        print("[WARN] No contacts found from API for this campaign/method.")
    
    # ALWAYS send to the hardcoded profile as well
    print("\n[INFO] Sending message to hardcoded profile: https://www.linkedin.com/in/cedricyxu/")
    try:
        cedric_profile = "https://www.linkedin.com/in/cedricyxu/"
        cedric_first_name = "Cedric"
        cedric_message = _personalize_message(cedric_first_name, base_message)
        send_linkedin_message(cedric_profile, cedric_message, actually_send=actually_send)
        print("[SUCCESS] Message sent to Cedric!")
    except Exception as e:
        print(f"[ERROR] Failed to send to Cedric: {e}")
    
    print(f"\n[INFO] LinkedIn campaign {campaign_id} completed!")


if __name__ == "__main__":
    # Test with a profile
    profile_url = "https://www.linkedin.com/in/cedricyxu/"
    message = (
        "Hi Cedric — I'm reaching out from CarbonSustain to share updates around our "
        "AI-driven carbon accounting platform. Would love to explore collaboration!"
    )
    send_linkedin_message(profile_url, message, actually_send=False)