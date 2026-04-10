from app.heuristics.linter import PromptLinter
import timeit

linter = PromptLinter()
text = "This is a normal prompt with no issues. " * 50

def run_lint():
    linter.lint(text)

print("Baseline:", timeit.timeit(run_lint, number=10000))
