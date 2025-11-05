# outreach/main.py
import random
import time
from textwrap import dedent

from .config import (
    CAMPAIGN_ID,
    EMAIL_METHOD,             # e.g., 2
    LINKEDIN_METHOD,          # e.g., 4
    SEND_MIN_DELAY_MS,
    SEND_MAX_DELAY_MS,
)
from .api_client import get_campaign, get_campaign_contacts, get_contact
from .email_sender import send_email_gmail
from .linkedIn_sender import send_linkedin_message  # keep case to match your file

@app.post("/run_campaign")
def run_campaign(data: dict):
    campaign_id = data.get("campaign_id")
    contact_method = data.get("contact_method")

    if contact_method == 2:
        # email sender logic here
        send_email_campaign(campaign_id)
        return {"message": f"Email campaign {campaign_id} sent!"}
    elif contact_method == 4:
        send_linkedin_campaign(campaign_id)
        return {"message": f"LinkedIn campaign {campaign_id} sent!"}
    else:
        return {"message": "Invalid contact method"}

def render_email(campaign: dict, contact: dict) -> tuple[str, str]:
    """Return (subject, body) for email outreach."""
    subject = campaign.get("email_subject")
    body = campaign.get('email_body')
    
    # dedent(f"""
    #     Hi {contact.get('first_name', '')},

    #     I'm reaching out regarding "{campaign.get('name', 'our initiative')}" during SD Climate Week.
    #     {campaign.get('email_body', '')}

    #     If you’re the right person to discuss next steps at {contact.get('company_name', 'your organization')},
    #     I’d love to schedule a short intro.

    #     Best,
    #     Tiffany
    # """).strip()
    return subject, body


def render_linkedin(campaign: dict, contact: dict) -> str:
    """Return the LinkedIn DM text."""
    return (
        f"Hi {contact.get('first_name', '')}, loved seeing your work around SD Climate Week. "
        f"We’re working on \"{campaign.get('name', '')}\" — quick intro?"
    )


def _sleep_jitter() -> None:
    """Sleep a random time between SEND_MIN_DELAY_MS and SEND_MAX_DELAY_MS."""
    ms = random.randint(SEND_MIN_DELAY_MS, SEND_MAX_DELAY_MS)
    time.sleep(ms / 1000)


def run_email(campaign: dict) -> int:
    """
    Send emails for the given campaign.
    Returns the number of email attempts (skipping contacts with no email).
    """
    campaign_id = campaign.get("id")
    sent = 0
    print("📬 Fetching email contacts…")
    items = (get_campaign_contacts(campaign_id, EMAIL_METHOD) or [])
    print(f"… got {len(items)} campaign-contact-method rows (email).")

    for row in items:
        contact = get_contact(row["contact"]) or {}
        email = (contact.get("email") or "").strip()
        if not email:
            print(
                f"⏭️  No email for contact id {contact.get('id')}, skipping.")
            continue
        subject, body = render_email(campaign, contact)
        send_email_gmail(subject, body, email)
        sent += 1
        _sleep_jitter()
    return sent


def run_linkedin(campaign: dict, actually_send: bool = False) -> int:
    """
    Queue or send LinkedIn messages for the given campaign.
    Returns the number of LinkedIn attempts (skipping contacts with no LinkedIn URL).
    """
    campaign_id = campaign.get("id")
    sent = 0
    print("🔗 Fetching LinkedIn contacts…")
    items = (get_campaign_contacts(campaign_id, LINKEDIN_METHOD) or [])
    print(f"… got {len(items)} campaign-contact-method rows (linkedin).")

    for row in items:
        contact = get_contact(row["contact"]) or {}
        li = (contact.get("linkedin") or contact.get(
            "linkedin_url") or "").strip()
        if not li:
            print(
                f"⏭️  No LinkedIn for contact id {contact.get('id')}, skipping.")
            continue
        msg = render_linkedin(campaign, contact)
        # Safe mode by default
        send_linkedin_message(li, msg, actually_send=actually_send)
        sent += 1
        _sleep_jitter()
    return sent


def run() -> None:
    campaign = get_campaign(CAMPAIGN_ID)
    print(f"🎯 Campaign: {campaign.get('name')}")

    run_email(campaign)

    # keep safe mode (no actual send) to match your original comment

    # run_linkedin(campaign, actually_send=False)


if __name__ == "__main__":
    run()
