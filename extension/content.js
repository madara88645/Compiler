console.log("MyCompiler Extension Loaded");

// --- Site Configurations ---
const SITES = [
    {
        name: 'ChatGPT',
        host: 'chatgpt.com',
        inputSelector: '#prompt-textarea',
        containerSelector: '#prompt-textarea',
        getValue: (el) => el.innerText || el.value,
        setValue: (el, text) => {
            el.focus();
            el.innerHTML = "";
            document.execCommand('insertText', false, text);
        }
    },
    {
        name: 'Claude',
        host: 'claude.ai',
        inputSelector: '[contenteditable="true"]',
        containerSelector: 'fieldset, [contenteditable="true"]',
        getValue: (el) => el.innerText,
        setValue: (el, text) => {
            el.focus();
            const range = document.createRange();
            range.selectNodeContents(el);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
            document.execCommand('insertText', false, text);
        }
    },
    {
        name: 'Gemini',
        host: 'gemini.google.com',
        inputSelector: '.ql-editor, [contenteditable="true"]', // Gemini often uses Quill editor class
        containerSelector: '.input-area, .ql-container',
        getValue: (el) => el.innerText,
        setValue: (el, text) => {
            el.focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('insertText', false, text);
        }
    }
];

function getCurrentSite() {
    const host = window.location.hostname;
    return SITES.find(s => host.includes(s.host));
}

// --- Main Injection Logic ---
function injectButton() {
    const site = getCurrentSite();
    if (!site) return;

    const inputs = document.querySelectorAll(site.inputSelector);

    inputs.forEach(target => {
        // Finding the best place to attach the button
        // For visual consistency, we often want it floating inside the input area (bottom-right)
        // or just outside.

        let container = target.parentElement;
        // Try to find a specific container if defined, otherwise parent
        if (site.name !== 'Generic' && site.containerSelector) {
            const closest = target.closest(site.containerSelector);
            if (closest && closest.parentElement) {
                container = closest.parentElement;
            }
        }

        if (container.querySelector('.my-compiler-btn-wrapper')) return; // Already injected

        // Create Wrapper for positioning
        // We ensure the container has relative positioning so our absolute button works
        if (getComputedStyle(container).position === 'static') {
            container.style.position = 'relative';
        }

        const wrapper = document.createElement('div');
        wrapper.className = 'my-compiler-btn-wrapper';

        const btn = document.createElement('button');
        btn.className = 'my-compiler-btn';
        btn.innerHTML = '<span>✨</span> Optimize';
        btn.title = "Optimize prompt with MyCompiler";

        wrapper.appendChild(btn);
        container.appendChild(wrapper);

        // Click Handler
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation();

            const originalText = site.getValue(target);
            if (!originalText || !originalText.trim()) return;

            console.log(`[MyCompiler] Optimizing on ${site.name}:`, originalText);

            // Visual Feedback
            btn.classList.add('loading');
            btn.innerHTML = '<div class="my-compiler-spinner"></div>';

            // Get Settings
            chrome.storage.local.get(['apiKey', 'backendUrl'], async (result) => {
                const apiKey = result.apiKey;
                const backendUrl = result.backendUrl || 'http://localhost:8000';

                if (!apiKey) {
                    alert("Please set your API Key in the extension settings.");
                    resetBtn(btn);
                    return;
                }

                // Send message to background script
                chrome.runtime.sendMessage({
                    type: 'OPTIMIZE_PROMPT',
                    text: originalText,
                    apiKey: apiKey,
                    backendUrl: backendUrl
                }, (response) => {
                    if (chrome.runtime.lastError) {
                        alert("Error: " + chrome.runtime.lastError.message);
                        resetBtn(btn);
                        return;
                    }

                    if (response && response.success) {
                        site.setValue(target, response.data);
                    } else {
                        alert("Optimization failed: " + (response.error || "Unknown error"));
                    }
                    resetBtn(btn);
                });
            });
        });
    });
}

function resetBtn(btn) {
    btn.classList.remove('loading');
    btn.innerHTML = '<span>✨</span> Optimize';
}

// --- Observer ---
const observer = new MutationObserver((mutations) => {
    // Simple debounce via timeout not strictly needed if we check for existence efficiently
    injectButton();
});

observer.observe(document.body, { childList: true, subtree: true });

// Initial run
setTimeout(injectButton, 1500);
