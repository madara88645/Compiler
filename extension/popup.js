document.addEventListener('DOMContentLoaded', () => {
    const enabledToggle = document.getElementById('enabledToggle');
    const statusLabel = document.getElementById('statusLabel');
    const playgroundLink = document.getElementById('openPlayground');

    // Load saved settings (Default to true)
    chrome.storage.local.get(['enabled'], (result) => {
        const isEnabled = result.enabled !== false; // Default true
        enabledToggle.checked = isEnabled;
        updateStatus(isEnabled);
    });

    // Toggle Handler
    enabledToggle.addEventListener('change', () => {
        const isEnabled = enabledToggle.checked;
        chrome.storage.local.set({ enabled: isEnabled }, () => {
            updateStatus(isEnabled);
        });
    });

    function updateStatus(enabled) {
        statusLabel.textContent = enabled ? 'Enabled' : 'Disabled';
        statusLabel.style.color = enabled ? '#7b2cbf' : '#666';
    }

    // Open Dashboard/Playground
    playgroundLink.addEventListener('click', () => {
        chrome.tabs.create({ url: 'http://localhost:3000' });
    });
});
