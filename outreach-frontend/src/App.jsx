import { useState, useEffect } from "react";

function App() {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");
  const [sendingCampaigns, setSendingCampaigns] = useState({});
  const [selectedMethods, setSelectedMethods] = useState({});
  const [campaignContacts, setCampaignContacts] = useState({});
  const [selectedContacts, setSelectedContacts] = useState({});
  const [loadingContacts, setLoadingContacts] = useState({});

  const BACKEND_URL = "http://127.0.0.1:8000";

  useEffect(() => {
    fetchCampaigns();
  }, []);

  const fetchCampaigns = async () => {
    try {
      setLoading(true);
      console.log("[DEBUG] Fetching campaigns from backend");
      
      const response = await fetch(`${BACKEND_URL}/campaigns`);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error("[ERROR] Response not OK:", response.status, errorText);
        throw new Error(`Failed to fetch campaigns: ${response.status}`);
      }
      
      const data = await response.json();
      console.log("[DEBUG] Received campaigns:", data);
      
      setCampaigns(data.campaigns || []);
      
      // Initialize selected methods (default to email)
      const initialMethods = {};
      (data.campaigns || []).forEach(campaign => {
        initialMethods[campaign.id] = "email"; // Changed to string!
      });
      setSelectedMethods(initialMethods);
      
      setStatus(`✅ Loaded ${data.campaigns.length} campaigns`);
    } catch (err) {
      console.error("[ERROR] Fetch error:", err);
      setStatus(`❌ Error loading campaigns: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleMethodChange = (campaignId, method) => {
    console.log(`[DEBUG] Method changed for campaign ${campaignId}: ${method}`);
    setSelectedMethods(prev => ({
      ...prev,
      [campaignId]: method
    }));
    
    // Load contacts for this campaign and method
    fetchContactsForCampaign(campaignId, method);
  };

  const fetchContactsForCampaign = async (campaignId, contactMethod) => {
    try {
      setLoadingContacts(prev => ({ ...prev, [campaignId]: true }));
      
      console.log(`[DEBUG] Fetching contacts for campaign ${campaignId}, method ${contactMethod}`);
      
      // Call backend which will call DigitalOcean API
      const response = await fetch(
        `${BACKEND_URL}/campaigns/${campaignId}/contacts?contact_method=${contactMethod}`
      );
      
      if (!response.ok) {
        throw new Error(`Failed to fetch contacts: ${response.status}`);
      }
      
      const data = await response.json();
      console.log(`[DEBUG] Received ${data.contacts.length} contacts:`, data);
      
      setCampaignContacts(prev => ({
        ...prev,
        [campaignId]: data.contacts
      }));
      
      // Set default to "all" contacts
      setSelectedContacts(prev => ({
        ...prev,
        [campaignId]: "all"
      }));
      
    } catch (err) {
      console.error(`[ERROR] Failed to fetch contacts for campaign ${campaignId}:`, err);
      setStatus(`❌ Error loading contacts: ${err.message}`);
    } finally {
      setLoadingContacts(prev => ({ ...prev, [campaignId]: false }));
    }
  };

  const handleContactChange = (campaignId, value) => {
    console.log(`[DEBUG] Contact selected for campaign ${campaignId}: ${value}`);
    setSelectedContacts(prev => ({
      ...prev,
      [campaignId]: value
    }));
  };

  const sendCampaign = async (campaignId) => {
    const contactMethod = selectedMethods[campaignId] || "email"; // String, not number!
    const selectedContactValue = selectedContacts[campaignId] || "all";
    
    let contact_ids = [];
    
    if (selectedContactValue !== "all") {
      contact_ids = [parseInt(selectedContactValue)];
    }
    
    setSendingCampaigns(prev => ({ ...prev, [campaignId]: true }));
    setStatus(`Sending campaign ${campaignId}... please wait ⏳`);

    try {
      console.log("[DEBUG] Sending campaign:", {
        campaign_id: campaignId,
        contact_method: contactMethod, // String: "email" or "linkedin"
        contact_ids: contact_ids
      });
      
      const response = await fetch(`${BACKEND_URL}/run_campaign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          campaign_id: parseInt(campaignId),
          contact_method: contactMethod, // String, not number!
          contact_ids: contact_ids
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error("[ERROR] Response:", errorText);
        throw new Error(`Server responded with ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      console.log("[DEBUG] Success response:", data);
      setStatus(`✅ Success: ${data.message || "Messages sent successfully"}`);
    } catch (err) {
      console.error("[ERROR] Send campaign failed:", err);
      setStatus(`❌ Error: ${err.message}`);
    } finally {
      setSendingCampaigns(prev => {
        const updated = { ...prev };
        delete updated[campaignId];
        return updated;
      });
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 px-6 py-10">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold text-blue-700 mb-3">
            Outreach Automation Dashboard
          </h1>
          <p className="text-gray-600">
            Select campaigns and choose your outreach method
          </p>
        </div>

        {/* Status Message */}
        {status && (
          <div className="mb-6 text-center">
            <p
              className={`text-sm font-medium px-4 py-2 rounded-lg inline-block ${
                status.startsWith("✅")
                  ? "bg-green-100 text-green-700"
                  : status.startsWith("❌")
                  ? "bg-red-100 text-red-700"
                  : "bg-blue-100 text-blue-700"
              }`}
            >
              {status}
            </p>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="text-center py-20">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            <p className="mt-4 text-gray-600">Loading campaigns...</p>
          </div>
        )}

        {/* Campaign Cards */}
        {!loading && campaigns.length === 0 && (
          <div className="text-center py-20">
            <p className="text-gray-500 text-lg">No campaigns found</p>
            <button
              onClick={fetchCampaigns}
              className="mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Retry
            </button>
          </div>
        )}

        {!loading && campaigns.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {campaigns.map((campaign) => (
              <div
                key={campaign.id}
                className="bg-white rounded-xl shadow-lg hover:shadow-xl transition-shadow p-6 border border-gray-200"
              >
                {/* Campaign Name */}
                <h2 className="text-xl font-bold text-gray-800 mb-2">
                  {campaign.name}
                </h2>

                {/* Campaign ID */}
                <p className="text-sm text-gray-500 mb-4">
                  Campaign ID: <span className="font-mono font-semibold">{campaign.id}</span>
                </p>

                {/* Method Selector */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Sending Method
                  </label>
                  <select
                    value={selectedMethods[campaign.id] || "email"}
                    onChange={(e) => handleMethodChange(campaign.id, e.target.value)}
                    disabled={sendingCampaigns[campaign.id]}
                    className="w-full p-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
                  >
                    <option value="email">📧 Email (Gmail API)</option>
                    <option value="linkedin">💼 LinkedIn (Playwright)</option>
                  </select>
                </div>

                {/* Contact Selector */}
                {campaignContacts[campaign.id] && (
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Select Contact(s)
                    </label>
                    {loadingContacts[campaign.id] ? (
                      <div className="text-sm text-gray-500 py-2">Loading contacts...</div>
                    ) : (
                      <select
                        value={selectedContacts[campaign.id] || "all"}
                        onChange={(e) => handleContactChange(campaign.id, e.target.value)}
                        disabled={sendingCampaigns[campaign.id]}
                        className="w-full p-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
                      >
                        <option value="all">🔮 All Contacts ({campaignContacts[campaign.id].length})</option>
                        
                        {campaignContacts[campaign.id].length > 0 ? (
                          campaignContacts[campaign.id].map(contact => (
                            <option key={contact.id} value={contact.id}>
                              {contact.name}
                              {contact.email && ` (${contact.email})`}
                            </option>
                          ))
                        ) : (
                          <option disabled>No contacts found</option>
                        )}
                      </select>
                    )}
                  </div>
                )}

                {/* Send Button */}
                <button
                  onClick={() => sendCampaign(campaign.id)}
                  disabled={sendingCampaigns[campaign.id]}
                  className={`w-full py-3 font-semibold rounded-lg transition ${
                    sendingCampaigns[campaign.id]
                      ? "bg-gray-400 cursor-not-allowed text-gray-700"
                      : "bg-blue-600 hover:bg-blue-700 text-white shadow-md hover:shadow-lg"
                  }`}
                >
                  {sendingCampaigns[campaign.id] ? (
                    <span className="flex items-center justify-center">
                      <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Sending...
                    </span>
                  ) : (
                    "🚀 Send Campaign"
                  )}
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Footer */}
        <footer className="mt-12 text-center text-gray-600 text-sm">
          Built by <span className="font-semibold text-blue-700">CarbonSustain</span>
        </footer>
      </div>
    </div>
  );
}

export default App;