import { useState } from "react";
import "./index.css";

function App() {
  const [campaignId, setCampaignId] = useState("");
  const [contactMethod, setContactMethod] = useState("2"); // 2=email, 4=LinkedIn
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  const sendCampaign = async () => {
    if (!campaignId) {
      setStatus("❌ Please enter a campaign ID.");
      return;
    }

    setLoading(true);
    setStatus("Sending... please wait ⏳");

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
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col justify-center items-center px-6 py-10">
      <div className="bg-white shadow-2xl rounded-2xl p-8 w-full max-w-lg border border-gray-200">
        <h1 className="text-3xl font-bold text-center text-blue-600 mb-6">
          Outreach Automation Dashboard
        </h1>

        <div className="space-y-4">
          <div>
            <label className="block text-gray-700 font-medium mb-2">
              Campaign ID
            </label>
            <input
              type="number"
              value={campaignId}
              onChange={(e) => setCampaignId(e.target.value)}
              placeholder="Enter Campaign ID"
              className="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-gray-700 font-medium mb-2">
              Contact Method
            </label>
            <select
              value={contactMethod}
              onChange={(e) => setContactMethod(e.target.value)}
              className="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="2">Email (Gmail API)</option>
              <option value="4">LinkedIn (Playwright)</option>
            </select>
          </div>

          <button
            onClick={sendCampaign}
            disabled={loading}
            className={`w-full py-3 font-semibold rounded-lg transition ${
              loading
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-700 text-white"
            }`}
          >
            {loading ? "Sending..." : "Send Test Campaign"}
          </button>
        </div>

        <div className="mt-6 text-center">
          <p
            className={`text-sm font-medium ${
              status.startsWith("✅")
                ? "text-green-600"
                : status.startsWith("❌")
                ? "text-red-600"
                : "text-gray-700"
            }`}
          >
            {status}
          </p>
        </div>
      </div>

      <footer className="mt-8 text-gray-500 text-sm">
        Built by <span className="font-semibold">CarbonSustain</span>
      </footer>
    </div>
  );
}

export default App;
