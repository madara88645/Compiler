import re

with open("app/quick_edit.py", "r") as f:
    content = f.read()

# Add click import right after shlex
content = content.replace("import shlex\nimport subprocess", "import shlex\nimport click\nimport subprocess")

# Remove _parse_editor_command
content = re.sub(r'    def _parse_editor_command.*?return editor_parts\n\n', '', content, flags=re.DOTALL)

# Remove the globals
content = re.sub(r'FORBIDDEN_EDITOR_PREFIXES = \(.*?\)\nSHELL_METACHAR_TOKENS = \{.*?\}\n+', '', content, flags=re.DOTALL)

# Replace edit_text_in_editor
edit_func = """    def edit_text_in_editor(self, text: str) -> Optional[str]:
        \"\"\"Open text in external editor and return edited content.\"\"\"
        try:
            editor = self.get_editor()
            edited_text = click.edit(text, editor=editor, extension=".txt")
            return edited_text
        except click.UsageError as exc:
            console.print(f"[red]⚠️ Failed to open editor: {exc}[/red]")
            return None
        except Exception as exc:
            console.print(f"[red]⚠️ Unexpected error using editor: {exc}[/red]")
            return None"""

content = re.sub(r'    def edit_text_in_editor\(self, text: str\) -> Optional\[str\]:.*?return handle.read\(\)\n        finally:\n            try:\n                os.unlink\(temp_path\)\n            except Exception:\n                pass', edit_func, content, flags=re.DOTALL)

with open("app/quick_edit.py", "w") as f:
    f.write(content)
