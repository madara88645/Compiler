document.addEventListener('DOMContentLoaded', () => {
    const apiKeyInput = document.getElementById('apiKey');
    const backendUrlInput = document.getElementById('backendUrl');
    const saveBtn = document.getElementById('saveBtn');
    const statusDiv = document.getElementById('status');
    const playgroundLink = document.getElementById('openPlayground');

    // Load saved settings
    chrome.storage.local.get(['apiKey', 'backendUrl'], (result) => {
        if (result.apiKey) apiKeyInput.value = result.apiKey;
        if (result.backendUrl) backendUrlInput.value = result.backendUrl;
    });

    // Save settings
    saveBtn.addEventListener('click', () => {
        const apiKey = apiKeyInput.value.trim();
        const backendUrl = backendUrlInput.value.trim();

        if (!apiKey) {
            statusDiv.textContent = 'API Key is required.';
            statusDiv.className = 'error';
            return;
        }

        chrome.storage.local.set({
            apiKey: apiKey,
            backendUrl: backendUrl || 'http://localhost:8000'
        }, () => {
            statusDiv.textContent = 'Settings saved!';
            statusDiv.className = 'success';
            setTimeout(() => {
                statusDiv.textContent = '';
                statusDiv.className = '';
            }, 2000);
        });
    });

    // Open Dashboard/Playground
    playgroundLink.addEventListener('click', () => {
        chrome.tabs.create({ url: 'http://localhost:3000' });
    });
});
