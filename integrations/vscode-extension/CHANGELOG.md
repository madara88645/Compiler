# Changelog

All notable changes to the PromptC VS Code extension are documented here.

## [Unreleased]

### Added
- Activity Bar sidebar with backend status, latest compile summary, history, and favorites.
- New commands for full-file compile, rerun, connection checks, API key management, artifact copy/insert, and favorite saving.
- Unit tests plus `@vscode/test-electron` integration coverage for command registration, compile flows, auth retry, and artifact reuse.
- Local debug launcher and package scripts for extension-host testing and VSIX packaging.

### Changed
- Refactored the extension into modular client, workflow, state, panel, and sidebar layers.
- Prompt panel now preserves the active tab and exposes copy, insert, and favorite actions per artifact.
- Backend preflight now checks `/health` before compile requests and surfaces clearer recovery actions.

## [0.1.0] - 2026-04-23

First Marketplace-ready release.

### Added
- `PromptC: Compile Selection` command - compiles the current selection (or full file when nothing is selected) against a local PromptC backend.
- `PromptC: Open Panel` command - reveals the PromptC result panel with four tabs: Intent, Policy, Prompts, Raw JSON.
- Configuration settings:
  - `promptc.apiBaseUrl` - backend API URL (default `http://127.0.0.1:8080`).
  - `promptc.conservativeMode` - request grounded, conservative output (default `true`).
- Secure API key storage via VS Code's secret storage (prompted on first 401/403 response).
- Publishing metadata, icon, and gallery banner for Marketplace and Open VSX listings.
