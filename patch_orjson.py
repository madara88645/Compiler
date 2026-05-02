files_to_patch = [
    "app/testing/runner.py",
    "app/testing/judge.py",
    "app/testing/adversarial.py"
]

for filename in files_to_patch:
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # ensure import orjson is there
    if "import orjson" not in content:
        content = "import orjson\n" + content

    content = content.replace("json.loads(", "orjson.loads(")

    # json.JSONDecodeError needs to be handled
    content = content.replace("json.JSONDecodeError", "orjson.JSONDecodeError")

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

print("patched.")
