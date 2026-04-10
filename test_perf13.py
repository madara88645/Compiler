import re
import timeit
from app.heuristics.linter import PromptLinter

text = "Write a comprehensive detailed report but keep it brief and short." * 20

# Create original version for testing
class PromptLinterOriginal:
    """Static analysis engine for prompts."""
    # ... copy everything over ...
    # Wait, I'll just restore and run both to compare correctly.
