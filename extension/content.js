console.log('MyCompiler Extension Loaded');

const SITES = [
    {
        name: 'ChatGPT',
        host: 'chatgpt.com',
        inputSelector: '#prompt-textarea',
        containerSelector: '#prompt-textarea',
        getValue: (el) => el.innerText || el.value,
        setValue: (el, text) => {
            el.focus();
            el.innerHTML = '';
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
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            document.execCommand('insertText', false, text);
        }
    },
    {
        name: 'Gemini',
        host: 'gemini.google.com',
        inputSelector: 'rich-textarea > [contenteditable="true"], .ql-editor, [contenteditable="true"]',
        containerSelector: '.input-area, .text-input-field, rich-textarea',
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
    return SITES.find((site) => host.includes(site.host));
}

function getDefaultButtonLabel() {
    return '<span class="spark">✦</span> Optimize';
}

function setButtonState(button, state) {
    button.classList.remove('loading', 'success', 'error');

    if (state === 'loading') {
        button.classList.add('loading');
        button.innerHTML = '<div class="my-compiler-spinner" aria-hidden="true"></div> Optimizing';
        return;
    }

    if (state === 'success') {
        button.classList.add('success');
        button.innerHTML = '<span class="spark">✓</span> Optimized';
        return;
    }

    if (state === 'error') {
        button.classList.add('error');
        button.innerHTML = '<span class="spark">!</span> Retry';
        return;
    }

    button.innerHTML = getDefaultButtonLabel();
}

function injectButton() {
    const site = getCurrentSite();
    if (!site) {
        return;
    }

    const inputs = document.querySelectorAll(site.inputSelector);

    inputs.forEach((target) => {
        let container = target.parentElement;

        if (site.containerSelector) {
            const closest = target.closest(site.containerSelector);
            if (closest && closest.parentElement) {
                container = closest.parentElement;
            }
        }

        if (!container || container.querySelector('.my-compiler-btn-wrapper')) {
            return;
        }

        if (getComputedStyle(container).position === 'static') {
            container.style.position = 'relative';
        }

        const wrapper = document.createElement('div');
        wrapper.className = 'my-compiler-btn-wrapper';

        const button = document.createElement('button');
        button.className = 'my-compiler-btn';
        button.innerHTML = getDefaultButtonLabel();
        button.type = 'button';
        button.title = 'Optimize prompt with MyCompiler';

        wrapper.appendChild(button);
        container.appendChild(wrapper);

        button.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();

            const originalText = site.getValue(target);
            if (!originalText || !originalText.trim()) {
                return;
            }

            setButtonState(button, 'loading');

            chrome.runtime.sendMessage(
                {
                    type: 'OPTIMIZE_PROMPT',
                    text: originalText
                },
                (response) => {
                    if (chrome.runtime.lastError) {
                        alert(`Error: ${chrome.runtime.lastError.message}`);
                        setButtonState(button, 'error');
                        window.setTimeout(() => setButtonState(button, 'default'), 1400);
                        return;
                    }

                    if (response && response.success) {
                        site.setValue(target, response.data);
                        setButtonState(button, 'success');
                    } else {
                        alert(`Optimization failed: ${response?.error || 'Unknown error'}`);
                        setButtonState(button, 'error');
                    }

                    window.setTimeout(() => setButtonState(button, 'default'), 1400);
                }
            );
        });
    });
}

const observer = new MutationObserver(() => {
    injectButton();
});

observer.observe(document.body, { childList: true, subtree: true });

window.setTimeout(injectButton, 1500);
