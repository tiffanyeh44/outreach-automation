from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
import os

# Add the current directory to path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import email_sender
import linkedIn_sender
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
    contact_method: int  # 2 = email, 4 = LinkedIn


@app.get("/")
def read_root():
    return {"message": "Outreach Automation API is running"}


@app.get("/campaigns")
def get_campaigns():
    """Fetch all campaigns from the API"""
    try:
        url = f"{BASE_URL}/outreach/campaigns/"
        print(f"[DEBUG] Fetching campaigns from: {url}")
        data = api_client._get_json(url)
        
        # Extract campaigns list - handle pagination if needed
        campaigns = data.get("results", [])
        print(f"[DEBUG] Found {len(campaigns)} campaigns")
        
        # Return simplified campaign data
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


@app.post("/run_campaign")
def run_campaign(request: CampaignRequest):
    """Run a campaign with the specified contact method"""
    try:
        campaign_id = request.campaign_id
        contact_method = request.contact_method
        
        # Verify campaign exists
        campaign = api_client.get_campaign(campaign_id)
        campaign_name = campaign.get("name", f"Campaign {campaign_id}")
        
        if contact_method == 2:
            # Email campaign
            sent_count = email_sender.run_campaign_emails(campaign_id, contact_method)
            return {
                "success": True,
                "message": f"Email campaign '{campaign_name}' completed. Sent {sent_count} emails.",
                "sent_count": sent_count
            }
        
        elif contact_method == 4:
            # LinkedIn campaign
            linkedin_sender.run_campaign_linkedin(campaign_id, actually_send=True, contact_method=contact_method)
            return {
                "success": True,
                "message": f"LinkedIn campaign '{campaign_name}' completed.",
            }
        
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported contact method: {contact_method}"
            )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)