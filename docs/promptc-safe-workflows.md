# PromptC Safe Workflows

PromptC is still a prompt product first, but it now supports safer developer workflows when a request needs more structure than "better wording."

## What Changed

Instead of stopping at optimized prompt text, PromptC can also expose:

- structured IR
- explicit execution policy
- reusable workflow artifacts
- regression-testable contracts

## Why Policy Matters

If a request touches finance, health, legal guidance, debugging, file paths, or sensitive data, the system should make that visible before the output gets reused downstream.

PromptC surfaces that through:

- risk level
- execution mode
- data sensitivity
- allowed / forbidden tools
- sanitization rules

## Why This Matters for Developers

Developers still want strong prompts, but they also want safer defaults, repeatable artifacts, IDE-friendly workflows, GitHub-friendly outputs, and regression checks for behavior.
