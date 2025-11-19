import { useState, useEffect } from "react";
import "./index.css";

function App() {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");
  const [sendingCampaigns, setSendingCampaigns] = useState({}); // Track which campaigns are sending
  const [selectedMethods, setSelectedMethods] = useState({}); // Track selected method per campaign

  // Fetch campaigns on mount
  useEffect(() => {
    fetchCampaigns();
  }, []);

  const fetchCampaigns = async () => {
    try {
      setLoading(true);
      console.log("[DEBUG] Fetching campaigns from: http://127.0.0.1:8000/campaigns");
      
      const response = await fetch("http://127.0.0.1:8000/campaigns");
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error("[ERROR] Response not OK:", response.status, errorText);
        throw new Error(`Failed to fetch campaigns: ${response.status} - ${errorText}`);
      }
      
      const data = await response.json();
      console.log("[DEBUG] Received data:", data);
      
      setCampaigns(data.campaigns || []);
      
      // Initialize selected methods (default to email)
      const initialMethods = {};
      (data.campaigns || []).forEach(campaign => {
        initialMethods[campaign.id] = "2"; // Default to email
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
    setSelectedMethods(prev => ({
      ...prev,
      [campaignId]: method
    }));
  };

  const sendCampaign = async (campaignId) => {
    const contactMethod = selectedMethods[campaignId] || "2";
    
    // Mark this campaign as sending
    setSendingCampaigns(prev => ({ ...prev, [campaignId]: true }));
    setStatus(`Sending campaign ${campaignId}... please wait ⏳`);

    try {
      const response = await fetch("http://127.0.0.1:8000/run_campaign", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          campaign_id: parseInt(campaignId),
          contact_method: parseInt(contactMethod),
        }),
      });

      if (!response.ok) {
        throw new Error(`Server responded with ${response.status}`);
      }

      const data = await response.json();
      setStatus(`✅ Success: ${data.message || "Messages sent successfully"}`);
    } catch (err) {
      console.error(err);
      setStatus(`❌ Error: ${err.message}`);
    } finally {
      // Mark this campaign as no longer sending
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
                    value={selectedMethods[campaign.id] || "2"}
                    onChange={(e) => handleMethodChange(campaign.id, e.target.value)}
                    disabled={sendingCampaigns[campaign.id]}
                    className="w-full p-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
                  >
                    <option value="2">Email</option>
                    <option value="4">LinkedIn</option>
                  </select>
                </div>

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