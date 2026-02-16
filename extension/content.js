console.log("MyCompiler Extension Loaded");

// Debounce helper to avoid excessive checks
function debounce(func, wait) {
    let timeout;
    return function (...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func(...args), wait);
    };
}

function injectButton() {
    // Select textareas based on the site
    // ChatGPT usually uses specific classes or ids, Claude uses contenteditable or textarea
    // We use a generic approach combined with specific site selectors

    const textareas = document.querySelectorAll('textarea, [contenteditable="true"]');

    textareas.forEach(target => {
        // Check if we already injected
        if (target.parentElement.querySelector('.my-compiler-btn')) return;

        // Create the button
        const btn = document.createElement('button');
        btn.className = 'my-compiler-btn';
        btn.innerHTML = '<span>✨</span> Optimize';
        btn.title = "Optimize prompt with MyCompiler";

        // Position logically (relative to parent container usually works best)
        // For ChatGPT/Claude, the input is often wrapped in a div.
        // We might need to adjust based on the specific DOM structure of these sites.
        // For this skeleton, we'll append to the parent and use absolute positioning (handled in CSS).
        // Ensure parent is relative for absolute positioning of child
        const parent = target.parentElement;
        if (getComputedStyle(parent).position === 'static') {
            parent.style.position = 'relative';
        }

        parent.appendChild(btn);

        // Click Handler
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation();

            const originalText = target.value || target.innerText;
            if (!originalText.trim()) return;

            console.log("Original Prompt:", originalText);

            // Visual Feedback
            btn.classList.add('loading');
            btn.innerHTML = '<div class="my-compiler-spinner"></div> Optimizing...';

            // Get Settings
            chrome.storage.local.get(['apiKey', 'backendUrl'], async (result) => {
                const apiKey = result.apiKey;
                const backendUrl = result.backendUrl || 'http://localhost:8000'; // Default to 8000 now

                if (!apiKey) {
                    alert("Please set your API Key in the extension settings.");
                    resetBtn(btn);
                    return;
                }

                // DEBUG: Show what we are sending
                alert(`DEBUG: Sending to ${backendUrl}\nKey: ${apiKey.substring(0, 10)}...`);

                // Send message to background script (Bypasses CORS/Mixed Content)
                chrome.runtime.sendMessage({
                    type: 'OPTIMIZE_PROMPT',
                    text: originalText,
                    apiKey: apiKey,
                    backendUrl: backendUrl
                }, (response) => {
                    // Handle response from background
                    if (chrome.runtime.lastError) {
                        console.error("Runtime Error:", chrome.runtime.lastError);
                        alert("Extension Error: " + chrome.runtime.lastError.message);
                        resetBtn(btn);
                        return;
                    }

                    if (response && response.success) {
                        const improvedText = response.data;

                        // Replace text
                        if (target.tagName === 'TEXTAREA') {
                            target.value = improvedText;
                        } else {
                            target.innerText = improvedText;
                        }

                        // Trigger input events
                        target.dispatchEvent(new Event('input', { bubbles: true }));
                        target.dispatchEvent(new Event('change', { bubbles: true }));
                    } else {
                        console.error("API Error:", response.error);
                        alert("Optimization failed: " + response.error);
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

// Observe DOM changes to handle dynamic navigation (SPA)
const observer = new MutationObserver(debounce(injectButton, 500));
observer.observe(document.body, { childList: true, subtree: true });

// Initial run
// Wait a moment for page load
setTimeout(injectButton, 1000);
