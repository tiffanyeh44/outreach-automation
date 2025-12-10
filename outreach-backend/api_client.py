# outreach/api_client.py
import requests
from urllib.parse import urljoin
from config import BASE_URL, API_TOKEN, SENDER_EMAIL

HEADERS = lambda: ({"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {})

def _get_json(url: str):
    r = requests.get(url, headers=HEADERS(), timeout=20)
    r.raise_for_status()
    return r.json()

def _post_json(url: str, data: dict):
    """POST JSON data to the API"""
    r = requests.post(url, json=data, headers=HEADERS(), timeout=20)
    r.raise_for_status()
    return r.json()

def get_campaign(campaign_id: int):
    url = f"{BASE_URL}/outreach/campaigns/{campaign_id}/"
    return _get_json(url)

def get_campaign_contacts(campaign_id: int, contact_method: str):
    """
    Follows pagination for: /outreach/campaign-contact-methods/?campaign=3&contact_method=email
    
    Args:
        campaign_id: Campaign ID
        contact_method: "email" or "linkedin" (string, not numeric ID!)
    
    Returns:
        List of dicts with keys: id, campaign, contact, contact_method
    """
    results = []
    url = f"{BASE_URL}/outreach/campaign-contact-methods/?campaign={campaign_id}&contact_method={contact_method}"
    
    print(f"[DEBUG] Calling API: {url}")
    
    while url:
        page = _get_json(url)
        results.extend(page.get("results", []))
        url = page.get("next")
    
    print(f"[DEBUG] Found {len(results)} contacts for campaign {campaign_id}, method '{contact_method}'")
    return results

def get_contact(contact_id: int):
    url = f"{BASE_URL}/outreach/contacts/{contact_id}/"
    return _get_json(url)

def get_contact_logs_for_campaign(campaign_id: int, contact_id: int = None):
    """
    Fetch contact logs for a specific campaign, optionally filtered by contact.
    Endpoint: /outreach/api/v1/campaigns/contact-logs/?campaign={campaign_id}&contact={contact_id}
    
    Args:
        campaign_id: Campaign ID
        contact_id: Optional contact ID to filter logs for specific contact
    
    Returns:
        List of contact logs
    """
    results = []
    
    # Build URL with optional contact filter
    if contact_id:
        url = f"{BASE_URL}/outreach/api/v1/campaigns/contact-logs/?campaign={campaign_id}&contact={contact_id}"
        print(f"[DEBUG] Fetching contact logs for campaign {campaign_id}, contact {contact_id}")
    else:
        url = f"{BASE_URL}/outreach/api/v1/campaigns/contact-logs/?campaign={campaign_id}"
        print(f"[DEBUG] Fetching all contact logs for campaign {campaign_id}")
    
    while url:
        try:
            page = _get_json(url)
            logs = page.get("results", [])
            results.extend(logs)
            print(f"[DEBUG] Fetched {len(logs)} contact logs (total: {len(results)})")
            url = page.get("next")
        except Exception as e:
            print(f"[ERROR] Failed to fetch contact logs: {e}")
            break
    
    return results

def check_if_already_contacted(campaign_id: int, contact_id: int, channel: str) -> bool:
    """
    Check if this contact has already been contacted (outbound) in this campaign via this channel.
    
    Args:
        campaign_id: Campaign ID
        contact_id: Contact ID
        channel: "email" or "linkedin"
    
    Returns:
        True if already contacted (has outbound log), False otherwise
    """
    try:
        logs = get_contact_logs_for_campaign(campaign_id, contact_id)
        
        # Check if there's any outbound message in this channel
        for log in logs:
            if (log.get("direction") == "outbound" and 
                log.get("channel", "").lower() == channel.lower()):
                print(f"[INFO] Contact {contact_id} already contacted via {channel} in campaign {campaign_id}")
                return True
        
        print(f"[INFO] Contact {contact_id} has NOT been contacted via {channel} in campaign {campaign_id}")
        return False
    except Exception as e:
        print(f"[WARN] Failed to check contact status: {e}")
        # If we can't check, assume not contacted to allow sending
        return False

def log_contact_outreach(campaign_id: int, contact_id: int, channel: str, subject: str = None, body: str = "", sender_email: str = None):
    """
    Log that a contact was successfully reached out to via email or LinkedIn.
    Endpoint: POST /outreach/api/v1/campaigns/contact-logs/
    
    Args:
        campaign_id: Campaign ID
        contact_id: Contact ID
        channel: "email" or "linkedin"
        subject: Email subject (only for email, None for LinkedIn)
        body: Full email body or LinkedIn message
        sender_email: Sender's email address (defaults to SENDER_EMAIL from config)
    
    Returns:
        Created log entry or None if failed
    """
    url = f"{BASE_URL}/outreach/api/v1/campaigns/contact-logs/"
    
    # Use config sender email if not provided
    if not sender_email:
        sender_email = SENDER_EMAIL or "automation@carbonsustain.io"
    
    # Build the POST data according to API spec
    data = {
        "campaign": campaign_id,
        "contact": contact_id,
        "sender_email": sender_email,
        "channel": channel.lower(),
        "direction": "outbound",  # Always outbound for successful sends
        "subject": subject if channel.lower() == "email" else None,
        "body": body,
        "note": f"Automated {channel} outreach - sent successfully"
    }
    
    print(f"[LOG] Logging outbound {channel} to contact {contact_id} for campaign {campaign_id}")
    print(f"[LOG] Data: {data}")
    
    try:
        result = _post_json(url, data)
        print(f"[LOG] ✅ Successfully logged outreach (log ID: {result.get('id')})")
        return result
    except Exception as e:
        print(f"[ERROR] ❌ Failed to log outreach: {e}")
        import traceback
        traceback.print_exc()
        return None

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