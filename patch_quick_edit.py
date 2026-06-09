import re

with open("app/quick_edit.py", "r") as f:
    content = f.read()

# Add click import
if "import click" not in content:
    content = content.replace("import subprocess", "import click\nimport subprocess")

content = re.sub(r'def _parse_editor_command\(.*?return editor_parts', '', content, flags=re.DOTALL)
content = re.sub(r'SHELL_METACHAR_TOKENS = \[.*?\]\n+', '', content, flags=re.DOTALL)
content = re.sub(r'FORBIDDEN_EDITOR_PREFIXES = \[.*?\]\n+', '', content, flags=re.DOTALL)

with open("app/quick_edit.py", "w") as f:
    f.write(content)
