# outreach/api_client.py
import requests
from urllib.parse import urljoin
from config import BASE_URL, API_TOKEN

HEADERS = lambda: ({"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {})

def _get_json(url: str):
    r = requests.get(url, headers=HEADERS(), timeout=20)
    r.raise_for_status()
    return r.json()

def get_campaign(campaign_id: int):
    url = f"{BASE_URL}/outreach/campaigns/{campaign_id}/"
    return _get_json(url)

def get_campaign_contacts(campaign_id: int, contact_method: int):
    """
    Follows pagination for: /outreach/campaign-contact-methods/?campaign=3&contact_method=2
    Returns list of dicts with keys: id, campaign, contact, contact_method
    """
    results = []
    url = f"{BASE_URL}/outreach/campaign-contact-methods/?campaign={campaign_id}&contact_method={contact_method}"
    while url:
        page = _get_json(url)
        results.extend(page.get("results", []))
        url = page.get("next")
    return results

def get_contact(contact_id: int):
    url = f"{BASE_URL}/outreach/contacts/{contact_id}/"
    return _get_json(url)

def get_campaign_email_content(campaign_id: int):
    """
    Fetch campaign and extract (subject, body_html) for sending emails.
    Returns a tuple of (subject, html_body).
    """
    data = get_campaign(campaign_id)

    subject = data.get("email_subject") or data.get("name") or "Outreach Campaign"
    body_html = data.get("email_body") or ""

    # Sanity check - ensure it's valid HTML content
    if not body_html.strip().lower().startswith("<!doctype"):
        # fallback: wrap plain text in basic HTML
        body_html = f"<html><body><p>{body_html}</p></body></html>"

    return subject, body_html

def get_campaign_message_text(campaign_id: int):
    """
    Fetch campaign and extract a plain-text message for LinkedIn outreach.
    Fallbacks gracefully if specific fields are missing.
    """
    data = get_campaign(campaign_id)

    # Try LinkedIn-specific fields first if they exist
    for key in ("linkedin_message", "message", "linkedin_body", "body_text"):
        text = data.get(key)
        if isinstance(text, str) and text.strip():
            return text.strip()

    # As a last resort, derive from email body by stripping tags (naive)
    email_body = data.get("email_body") or ""
    if isinstance(email_body, str) and email_body.strip():
        # naive HTML strip
        try:
            import re
            stripped = re.sub(r"<[^>]+>", " ", email_body)
            stripped = re.sub(r"\s+", " ", stripped).strip()
            if stripped:
                return stripped
        except Exception:
            pass

    # Final fallback
    return (
        "Hi there — I'm reaching out from CarbonSustain to share a quick update "
        "on our AI-driven carbon accounting platform. Would love to connect!"
    )