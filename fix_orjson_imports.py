files_to_patch = [
    "app/testing/runner.py",
    "app/testing/judge.py",
    "app/testing/adversarial.py"
]

for filename in files_to_patch:
    with open(filename, 'r') as f:
        content = f.read()

    # remove redundant import orjson
    while "import orjson\nimport orjson" in content:
        content = content.replace("import orjson\nimport orjson", "import orjson")

    with open(filename, 'w') as f:
        f.write(content)

print("fixed.")
