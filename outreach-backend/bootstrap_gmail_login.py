# save as scripts/bootstrap_gmail_login.py and run it
from playwright.sync_api import sync_playwright

STATE = "gmail.json"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://mail.google.com/")
    input("Log into Gmail fully, then press Enter to save storage state… ")
    context.storage_state(path=STATE)
    print(f"Saved storage state to {STATE}")
    browser.close()
