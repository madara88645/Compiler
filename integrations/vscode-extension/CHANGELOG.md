# Changelog

All notable changes to the PromptC VS Code extension are documented here.

## [0.1.0] - 2026-04-23

First Marketplace-ready release.

### Added
- `PromptC: Compile Selection` command — compiles the current selection (or full file when nothing is selected) against a local PromptC backend.
- `PromptC: Open Panel` command — reveals the PromptC result panel with four tabs: Intent, Policy, Prompts, Raw JSON.
- Configuration settings:
  - `promptc.apiBaseUrl` — backend API URL (default `http://127.0.0.1:8080`).
  - `promptc.conservativeMode` — request grounded, conservative output (default `true`).
- Secure API key storage via VS Code's secret storage (prompted on first 401/403 response).
- Publishing metadata, icon, and gallery banner for Marketplace and Open VSX listings.
