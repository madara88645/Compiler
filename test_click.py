import click
# Mock getting text and editing
# Wait, click.edit will block waiting for input. Let's just read the docstring.
print(click.edit.__doc__)
