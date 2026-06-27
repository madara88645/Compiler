import os

files_to_patch = {
    "web/app/components/BenchmarkResults.tsx": [
        (
            'title="Copy raw output"\n                            aria-label="Copy raw output"\n                        >\n                            <span className="sr-only" aria-live="polite">{copiedRaw ? "Copied to clipboard" : ""}</span>',
            'title={copiedRaw ? "Copied!" : "Copy raw output"}\n                            aria-label={copiedRaw ? "Copied" : "Copy raw output"}\n                        >\n                            <span className="sr-only" aria-live="polite">{copiedRaw ? "Copied to clipboard" : ""}</span>'
        ),
        (
            'title="Copy compiled output"\n                            aria-label="Copy compiled output"\n                        >\n                            <span className="sr-only" aria-live="polite">{copiedCompiled ? "Copied to clipboard" : ""}</span>',
            'title={copiedCompiled ? "Copied!" : "Copy compiled output"}\n                            aria-label={copiedCompiled ? "Copied" : "Copy compiled output"}\n                        >\n                            <span className="sr-only" aria-live="polite">{copiedCompiled ? "Copied to clipboard" : ""}</span>'
        )
    ],
    "web/app/agent-generator/page.tsx": [
        (
            'title="Copy to Clipboard"\n                    aria-label="Copy Markdown"\n                  >\n                    <span className="sr-only" aria-live="polite">{copied ? "Copied to clipboard" : ""}</span>',
            'title={copied ? "Copied!" : "Copy to Clipboard"}\n                    aria-label={copied ? "Copied" : "Copy Markdown"}\n                  >\n                    <span className="sr-only" aria-live="polite">{copied ? "Copied to clipboard" : ""}</span>'
        )
    ],
    "web/app/skills-generator/page.tsx": [
        (
            'title="Copy to Clipboard"\n                    aria-label="Copy Markdown"\n                  >\n                    <span className="sr-only" aria-live="polite">{copied ? "Copied to clipboard" : ""}</span>',
            'title={copied ? "Copied!" : "Copy to Clipboard"}\n                    aria-label={copied ? "Copied" : "Copy Markdown"}\n                  >\n                    <span className="sr-only" aria-live="polite">{copied ? "Copied to clipboard" : ""}</span>'
        )
    ]
}

for filepath, replacements in files_to_patch.items():
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        continue

    with open(filepath, "r") as f:
        content = f.read()

    original_content = content
    for old_str, new_str in replacements:
        if old_str in content:
            content = content.replace(old_str, new_str)
        else:
            print(f"Warning: String not found in {filepath}:\n{old_str[:50]}...")

    if content != original_content:
        with open(filepath, "w") as f:
            f.write(content)
        print(f"Patched {filepath}")
