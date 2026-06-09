with open("app/quick_edit.py", "r") as f:
    content = f.read()

content = content.replace("        def edit_text_in_editor(self", "    def edit_text_in_editor(self")

with open("app/quick_edit.py", "w") as f:
    f.write(content)
