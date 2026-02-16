// Background Service Worker
console.log("MyCompiler Background Worker Loaded");

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === 'OPTIMIZE_PROMPT') {
        handleOptimization(request, sendResponse);
        return true; // Keep channel open for async response
    }
});

async function handleOptimization(request, sendResponse) {
    const { text, apiKey, backendUrl } = request;

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
