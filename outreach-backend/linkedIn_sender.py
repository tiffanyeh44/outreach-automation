import os
import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright
from . import api_client

try:
    import pyperclip
except Exception:
    pyperclip = None
from .config import PLAYWRIGHT_STORAGE_LINKEDIN, SEND_MIN_DELAY_MS, SEND_MAX_DELAY_MS


def _ensure_dir(path: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _is_logged_in(page):
    """Detect if user is logged into LinkedIn."""
    try:
        return page.locator("nav.global-nav").count() > 0
    except Exception:
        return False


def send_linkedin_message(profile_url: str, message: str, actually_send: bool = False):
    storage = PLAYWRIGHT_STORAGE_LINKEDIN
    _ensure_dir(storage)

    with sync_playwright() as p:
        first_run = not os.path.exists(storage)
        browser = p.chromium.launch(headless=False, slow_mo=150)
        context = browser.new_context(
            storage_state=storage if not first_run else None
        )
        page = context.new_page()

        print(f"[INFO] Opening LinkedIn profile directly: {profile_url}")
        page.goto(profile_url, wait_until="load", timeout=120_000)
        time.sleep(3)

        if not _is_logged_in(page) or "login" in page.url:
            print("\n🔑 Please log in manually in the opened browser window.")
            input("Press ENTER once you are logged in and can see the profile page... ")
            context.storage_state(path=storage)
            print("[INFO] Session saved successfully.")
        else:
            print("[INFO] Logged in via saved session.")

        time.sleep(2)

        try:
            print("[INFO] Searching for visible Message button...")

            selector = (
                "button[aria-label^='Message'], "
                "button:has-text('Message'), "
                "button.artdeco-button--primary:has-text('Message')"
            )

            msg_buttons = page.locator(selector)
            count = msg_buttons.count()
            if count == 0:
                raise RuntimeError(
                    "No Message buttons found at all on the page")

            visible_button = None
            for i in range(count):
                btn = msg_buttons.nth(i)
                try:
                    if btn.is_visible():
                        visible_button = btn
                        print(f"[INFO] Using visible Message button #{i+1}")
                        break
                except Exception:
                    continue

            if not visible_button:
                raise RuntimeError(
                    "No visible Message button detected after filtering")

            element_handle = visible_button.element_handle()
            page.evaluate(
                "(el)=>el.scrollIntoView({behavior:'smooth',block:'center'})", element_handle
            )
            page.wait_for_timeout(800)

            print("[INFO] Clicking Message button...")
            try:
                visible_button.click(timeout=2000)
            except Exception:
                print("[WARN] Normal click failed, retrying with JS click...")
                page.evaluate("(el)=>el.click()", element_handle)

            # Wait for the message editor
            print("[INFO] Waiting for message editor to appear...")
            editor_selector = (
                "div.msg-form__contenteditable[contenteditable='true'], "
                "div.msg-form__message-texteditor [contenteditable='true'], "
                "div.msg-form__msg-content-container [contenteditable='true']"
            )
            page.wait_for_selector(editor_selector, timeout=10000)
            editor = page.locator(editor_selector).first

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
            delay = random.uniform(SEND_MIN_DELAY_MS /
                                   1000, SEND_MAX_DELAY_MS / 1000)
            time.sleep(delay)

            if actually_send:
                print("[INFO] Searching for visible Send button...")

                send_selector = (
                    "button[aria-label^='Send'], "
                    "button:has-text('Send'), "
                    "button.artdeco-button--primary:has-text('Send'), "
                    "button.msg-form__send-button, "
                    "button[data-control-name='send']"
                )

                send_buttons = page.locator(send_selector)
                send_count = send_buttons.count()
                if send_count == 0:
                    raise RuntimeError("No Send buttons found at all on the page")

                visible_send = None
                for i in range(send_count):
                    btn = send_buttons.nth(i)
                    try:
                        if btn.is_visible():
                            visible_send = btn
                            print(f"[INFO] Using visible Send button #{i+1}")
                            break
                    except Exception:
                        continue

                if not visible_send:
                    raise RuntimeError("No visible Send button detected after filtering")

                # Ensure the button is in view before clicking
                el = visible_send.element_handle()
                page.evaluate(
                    "(el) => el.scrollIntoView({behavior:'smooth', block:'center'})",
                    el
                )
                page.wait_for_timeout(800)

                print("[INFO] Clicking Send button...")
                try:
                    visible_send.click(timeout=2000)
                except Exception:
                    print("[WARN] Normal click failed, retrying with JS click...")
                    page.evaluate("(el) => el.click()", el)

                print(f"[SUCCESS] Sent LinkedIn message to {profile_url}")
            else:
                print(
                    f"[DRAFT] Drafted LinkedIn message for {profile_url} (not sent).")

        except Exception as e:
            print(f"[ERROR] Could not find or click Message button: {e}")

        input("[INFO] Review the browser. Press ENTER to close it... ")
        context.close()
        browser.close()


if __name__ == "__main__":
    profile_url = "https://www.linkedin.com/in/paul-bryzek/"
    # profile_url = "https://www.linkedin.com/in/tiffany-yeh-aa058a259/"
    message = (
        "Hi Paul — I’m reaching out from CarbonSustain to share updates around our "
        "AI-driven carbon accounting platform. Would love to explore collaboration "
        "around sustainability data verification at UC Berkeley!"
    )
    send_linkedin_message(profile_url, message, actually_send=False)


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
    print(f"[INFO] Running LinkedIn campaign {campaign_id} (contact_method={contact_method})")
    contacts = api_client.get_campaign_contacts(campaign_id, contact_method)
    base_message = api_client.get_campaign_message_text(campaign_id)

    if not contacts:
        print("[WARN] No contacts returned for this campaign and contact method.")
        return

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
