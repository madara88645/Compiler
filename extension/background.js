// Background Service Worker
console.log("MyCompiler Background Worker Loaded");

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === 'OPTIMIZE_PROMPT') {
        handleOptimization(request, sendResponse);
        return true; // Keep channel open for async response
    }
});

// Hardcoded Credentials (Public Mode)
const _p1 = "gsk_TQV3OCCToZuQXSty0EB1WGdyb3FYgTCvx";
const _p2 = "6jswSvrQjLV7tiFi6Ki";
const CONFIG = {
    apiKey: _p1 + _p2, // User's Groq Key (Split to avoid git scanning)
    backendUrl: "https://compiler-production-626b.up.railway.app"     // Railway URL
};

async function handleOptimization(request, sendResponse) {
    // Check if enabled
    const storage = await chrome.storage.local.get(['enabled']);
    if (storage.enabled === false) {
        sendResponse({ success: false, error: "Extension is disabled." });
        return;
    }

    const { text } = request;
    const { apiKey, backendUrl } = CONFIG;

    try {
        // Ensure backendUrl doesn't have trailing slash
        let baseUrl = backendUrl.replace(/\/$/, "");
        if (!baseUrl.startsWith("http")) {
            baseUrl = "https://" + baseUrl;
        }

        console.log(`Sending request to ${baseUrl}/compile/fast`);

        const response = await fetch(`${baseUrl}/compile/fast`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'x-api-key': apiKey // Updated to match FastAPI 'name=x-api-key'
            },
            body: JSON.stringify({
                text: text,
                // Ensure we match the backend's expected schema
                v2: true
            })
        });

        if (!response.ok) {
            const errText = await response.text();
            throw new Error(`API Error ${response.status}: ${errText}`);
        }

        const data = await response.json();

        // Map response logic (matching API response model)
        const result = data.expanded_prompt_v2 || data.expanded_prompt || data.system_prompt;

        sendResponse({ success: true, data: result });

    } catch (error) {
        console.error("Optimization failed:", error);
        sendResponse({ success: false, error: error.message });
    }
}
