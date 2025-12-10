from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
import os

# Add the current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import sender classes
from email_sender import EmailSender
from linkedIn_sender import LinkedInSender
import api_client
from config import BASE_URL

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CampaignRequest(BaseModel):
    campaign_id: int
    contact_method: str  # "email" or "linkedin" (string, not number!)
    contact_ids: list[int] = []  # Optional: specific contacts to send to


@app.get("/")
def read_root():
    return {"message": "Outreach Automation API is running"}


@app.get("/campaigns")
def get_campaigns():
    """Fetch all campaigns from the DigitalOcean API"""
    try:
        url = f"{BASE_URL}/outreach/campaigns/"
        print(f"[DEBUG] Fetching campaigns from: {url}")
        data = api_client._get_json(url)
        
        campaigns = data.get("results", [])
        print(f"[DEBUG] Found {len(campaigns)} campaigns")
        
        campaign_list = [
            {
                "id": c.get("id"),
                "name": c.get("name", f"Campaign {c.get('id')}")
            }
            for c in campaigns
        ]
        
        print(f"[DEBUG] Returning campaigns: {campaign_list}")
        return {
            "campaigns": campaign_list
        }
    except Exception as e:
        print(f"[ERROR] Failed to fetch campaigns: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch campaigns: {str(e)}")


@app.get("/campaigns/{campaign_id}/contacts")
def get_campaign_contacts_by_method(campaign_id: int, contact_method: str):
    """
    Fetch contacts for a specific campaign and contact method.
    
    Args:
        campaign_id: Campaign ID
        contact_method: "email" or "linkedin" (string!)
    
    Flow:
    1. Call DigitalOcean: /outreach/campaign-contact-methods/?campaign={id}&contact_method={method}
    2. For each contact ID, fetch: /outreach/contacts/{contact_id}/
    3. Return formatted list with relevant info (email or LinkedIn URL)
    """
    try:
        print(f"[DEBUG] Fetching contacts for campaign {campaign_id}, method '{contact_method}'")
        
        # Get campaign-contact-method mappings
        campaign_contacts = api_client.get_campaign_contacts(campaign_id, contact_method)
        print(f"[DEBUG] Found {len(campaign_contacts)} campaign-contact mappings")
        
        contacts_list = []
        seen_contact_ids = set()
        
        # For each mapping, fetch full contact details
        for mapping in campaign_contacts:
            contact_id = mapping.get("contact")
            
            if not contact_id or contact_id in seen_contact_ids:
                continue
            
            seen_contact_ids.add(contact_id)
            
            try:
                # Fetch contact from API
                contact = api_client.get_contact(contact_id)
                print(f"[DEBUG] Fetched contact {contact_id}: {contact.get('first_name')} {contact.get('last_name')}")
                
                contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
                if not contact_name:
                    contact_name = f"Contact {contact_id}"
                
                contact_data = {
                    "id": contact_id,
                    "name": contact_name,
                    "first_name": contact.get("first_name", "")
                }
                
                # Add method-specific fields
                if contact_method == "email":
                    # Use "email" field from contact JSON
                    email = contact.get("email")
                    
                    if isinstance(email, str) and "@" in email:
                        contact_data["email"] = email.strip()
                        contacts_list.append(contact_data)
                    else:
                        print(f"[WARN] Contact {contact_id} has no valid email, skipping")
                
                elif contact_method == "linkedin":
                    # Use "linkedin" field from contact JSON
                    linkedin_url = contact.get("linkedin")
                    
                    if isinstance(linkedin_url, str) and linkedin_url.startswith("http"):
                        contact_data["linkedin_url"] = linkedin_url
                        contacts_list.append(contact_data)
                    else:
                        print(f"[WARN] Contact {contact_id} has no valid LinkedIn URL, skipping")
                
            except Exception as e:
                print(f"[ERROR] Failed to fetch contact {contact_id}: {e}")
                continue
        
        print(f"[DEBUG] Returning {len(contacts_list)} contacts")
        
        return {
            "campaign_id": campaign_id,
            "contact_method": contact_method,
            "contacts": contacts_list
        }
        
    except Exception as e:
        print(f"[ERROR] Failed to fetch campaign contacts: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch contacts: {str(e)}")


@app.post("/run_campaign")
def run_campaign(request: CampaignRequest):
    """Run a campaign with the specified contact method"""
    try:
        campaign_id = request.campaign_id
        contact_method = request.contact_method  # Now a string: "email" or "linkedin"
        contact_ids = request.contact_ids
        
        print(f"[INFO] Starting campaign {campaign_id} with method '{contact_method}'")
        print(f"[INFO] Contact IDs: {contact_ids if contact_ids else 'ALL'}")
        
        # Verify campaign exists
        campaign = api_client.get_campaign(campaign_id)
        campaign_name = campaign.get("name", f"Campaign {campaign_id}")
        
        if contact_method == "email":
            # Email campaign
            print("[INFO] Running EMAIL campaign")
            
            # Create email sender instance
            email_sender = EmailSender()
            
            if contact_ids:
                # Send to specific contacts
                print(f"[INFO] Sending to specific contacts: {contact_ids}")
                sent_count = email_sender.run_campaign(campaign_id, contact_ids)
            else:
                # Get all contacts using campaign-contact-methods
                print("[INFO] Sending to ALL contacts from campaign-contact-methods")
                campaign_contacts = api_client.get_campaign_contacts(campaign_id, contact_method)
                
                # Extract unique contact IDs
                all_contact_ids = list(set(
                    mapping.get("contact") 
                    for mapping in campaign_contacts 
                    if mapping.get("contact")
                ))
                
                if all_contact_ids:
                    print(f"[INFO] Found {len(all_contact_ids)} email contacts")
                    sent_count = email_sender.run_campaign(campaign_id, all_contact_ids)
                else:
                    print("[WARN] No email contacts found")
                    sent_count = 0
            
            return {
                "success": True,
                "message": f"Email campaign '{campaign_name}' completed. Sent {sent_count} emails.",
                "sent_count": sent_count
            }
        
        elif contact_method == "linkedin":
            # LinkedIn campaign
            print("[INFO] Running LINKEDIN campaign")
            
            # Create LinkedIn sender instance
            linkedin_sender = LinkedInSender()
            
            if contact_ids:
                # Send to specific contacts
                print(f"[INFO] Sending to specific contacts: {contact_ids}")
                linkedin_sender.run_campaign(campaign_id, contact_ids, actually_send=True)
            else:
                # Get all contacts using campaign-contact-methods
                print("[INFO] Sending to ALL contacts from campaign-contact-methods")
                campaign_contacts = api_client.get_campaign_contacts(campaign_id, contact_method)
                
                # Extract unique contact IDs
                all_contact_ids = list(set(
                    mapping.get("contact") 
                    for mapping in campaign_contacts 
                    if mapping.get("contact")
                ))
                
                if all_contact_ids:
                    print(f"[INFO] Found {len(all_contact_ids)} LinkedIn contacts")
                    linkedin_sender.run_campaign(campaign_id, all_contact_ids, actually_send=True)
                else:
                    print("[WARN] No LinkedIn contacts found")
            
            return {
                "success": True,
                "message": f"LinkedIn campaign '{campaign_name}' completed.",
            }
        
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported contact method: {contact_method}. Must be 'email' or 'linkedin'."
            )
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)