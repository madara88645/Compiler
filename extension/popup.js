document.addEventListener('DOMContentLoaded', () => {
    const enabledToggle = document.getElementById('enabledToggle');
    const statusLabel = document.getElementById('statusLabel');
    const playgroundButton = document.getElementById('openPlayground');
    const docsButton = document.getElementById('openDocs');

    chrome.storage.local.get(['enabled'], (result) => {
        const isEnabled = result.enabled !== false;
        enabledToggle.checked = isEnabled;
        updateStatus(isEnabled);
    });

    enabledToggle.addEventListener('change', () => {
        const isEnabled = enabledToggle.checked;
        chrome.storage.local.set({ enabled: isEnabled }, () => {
            updateStatus(isEnabled);
        });
    });

    function updateStatus(enabled) {
        statusLabel.textContent = enabled ? 'Enabled' : 'Disabled';
        statusLabel.classList.toggle('status-enabled', enabled);
        statusLabel.classList.toggle('status-disabled', !enabled);
    }

    playgroundButton.addEventListener('click', () => {
        chrome.tabs.create({ url: 'http://localhost:3000' });
    });

    docsButton.addEventListener('click', () => {
        chrome.tabs.create({ url: 'https://github.com' });
    });
});
