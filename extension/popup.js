document.addEventListener('DOMContentLoaded', () => {
    const enabledToggle = document.getElementById('enabledToggle');
    const statusLabel = document.getElementById('statusLabel');
    const playgroundButton = document.getElementById('openPlayground');
    const docsButton = document.getElementById('openDocs');
    const conservativeToggle = document.getElementById('pc-conservative-toggle');
    const CONSERVATIVE_KEY = 'promptc_conservative_mode';

    chrome.storage.local.get(['enabled'], (result) => {
        const isEnabled = result.enabled !== false;
        enabledToggle.checked = isEnabled;
        updateStatus(isEnabled);
    });

    // Conservative mode initial state (default: ON)
    chrome.storage.local.get([CONSERVATIVE_KEY], (result) => {
        const on = result[CONSERVATIVE_KEY] !== false;
        setConservativeUI(on);
    });

    enabledToggle.addEventListener('change', () => {
        const isEnabled = enabledToggle.checked;
        chrome.storage.local.set({ enabled: isEnabled }, () => {
            updateStatus(isEnabled);
        });
    });

    if (conservativeToggle) {
        conservativeToggle.addEventListener('click', () => {
            chrome.storage.local.get([CONSERVATIVE_KEY], (result) => {
                const current = result[CONSERVATIVE_KEY] !== false;
                const next = !current;
                chrome.storage.local.set({ [CONSERVATIVE_KEY]: next }, () => {
                    setConservativeUI(next);
                });
            });
        });
    }

    function updateStatus(enabled) {
        statusLabel.textContent = enabled ? 'Enabled' : 'Disabled';
        statusLabel.classList.toggle('status-enabled', enabled);
        statusLabel.classList.toggle('status-disabled', !enabled);
    }

    function setConservativeUI(on) {
        if (!conservativeToggle) return;
        conservativeToggle.classList.toggle('pc-conservative-on', on);
        conservativeToggle.classList.toggle('pc-conservative-off', !on);
        conservativeToggle.setAttribute('aria-pressed', on ? 'true' : 'false');
        conservativeToggle.title = on
            ? 'Conservative mode ON – keep prompts grounded and avoid hallucinations.'
            : 'Conservative mode OFF – use more aggressive optimization.';
    }

    playgroundButton.addEventListener('click', () => {
        chrome.tabs.create({ url: 'http://localhost:3000' });
    });

    docsButton.addEventListener('click', () => {
        chrome.tabs.create({ url: 'https://github.com' });
    });

    // Helper: other scripts can query current mode
    window.getPromptCompilerMode = function (cb) {
        chrome.storage.local.get([CONSERVATIVE_KEY], (result) => {
            const on = result[CONSERVATIVE_KEY] !== false;
            cb(on ? 'conservative' : 'default');
        });
    };
});
