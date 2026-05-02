files_to_patch = [
    "app/testing/runner.py",
    "app/testing/judge.py",
    "app/testing/adversarial.py"
]

for filename in files_to_patch:
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # Move from __future__ to the very top (after docstrings if any, but easier just top line)
    content = content.replace("import orjson\n\"\"\"", "\"\"\"")
    if "from __future__ import annotations" in content:
        content = content.replace("from __future__ import annotations\n", "")
        if content.startswith("\"\"\""):
            parts = content.split("\"\"\"", 2)
            if len(parts) >= 3:
                # parts[0] is empty, parts[1] is docstring, parts[2] is the rest
                content = "\"\"\"" + parts[1] + "\"\"\"\nfrom __future__ import annotations\nimport orjson\n" + parts[2]
        else:
            content = "from __future__ import annotations\nimport orjson\n" + content

    if filename == "app/testing/runner.py" and "from __future__" not in content:
        content = "import orjson\n" + content

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

print("fixed.")
