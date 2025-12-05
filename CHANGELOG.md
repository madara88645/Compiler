# Changelog

All notable changes to this project will be documented in this file.

## [2.0.45] - 2025-11-12
### Added
- **⌨️ Keyboard Shortcuts Panel**: Comprehensive shortcuts reference dialog
  - **Categorized Shortcuts**: 7 categories (General, Editing, Clipboard, Navigation, File Operations, Views, Appearance)
  - **40+ Shortcuts**: Complete keyboard shortcuts for all major actions
  - **Scrollable Interface**: Easy-to-navigate list with visual key indicators
  - **Color-coded Keys**: Accent color highlighting for keyboard shortcuts
  - **Ctrl+K Activation**: Quick access to shortcuts reference (also Ctrl+Shift+K)
- **🎯 Command Palette**: VS Code-style quick command execution
  - **Ctrl+Shift+P Activation**: Universal command launcher
  - **Fuzzy Search**: Filter commands by typing
  - **20+ Commands**: Access all major features instantly
  - **Keyboard Navigation**: Arrow keys to select, Enter to execute, Esc to close
  - **Modern UI**: Clean, centered dialog with emoji icons
  - **Live Filtering**: Commands update as you type
- **Enhanced Keyboard Bindings**: All shortcuts now functional
  - **Generation**: Ctrl+Enter (generate prompt), Ctrl+L (clear input)
  - **Clipboard**: Ctrl+Shift+C/U/E/S (copy system/user/expanded/schema)
  - **Navigation**: Ctrl+1-5 (switch tabs), Ctrl+Tab (next tab)
  - **File Ops**: Ctrl+S (save), Ctrl+O (open), Ctrl+E (export), Ctrl+I (import)
  - **Views**: Ctrl+B (toggle sidebar), Ctrl+H (history), Ctrl+F (favorites), Ctrl+Shift+A (analytics)
  - **Theme**: Ctrl+Shift+T (toggle theme)
- **Wrapper Functions**: Clean abstraction layer for all shortcut actions
- **Test Suite**: 30 comprehensive tests for keyboard shortcuts and command palette
  - Tests for dialog opening, command execution, clipboard operations
  - Integration tests for sidebar, theme, and export/import
  - Edge case handling for empty content and repeated operations
- **CLI Command Palette Favorites**: `promptc palette commands|favorites` lets the CLI inspect and edit the same starred actions as the desktop UI. Honors the shared `PROMPTC_UI_CONFIG` override for sandboxed settings.
- **Palette Favorites Export/Import & Backups**: `promptc palette favorites --export PATH` writes a portable JSON snapshot, `--import-from PATH` (+ `--replace`) restores/merges favorites, and every mutation now creates a timestamped `.bak` of `~/.promptc_ui.json` (last 5 retained).
- **Shared Palette Metadata (`app/command_palette.py`)**: Single source of truth for command IDs, labels, and config-file path; both UI and CLI now derive entries from this module.

### Changed
- Removed conflicting Ctrl+F binding (was used for find, now for favorites)
- Commented out Ctrl+S conflict (now handled by new shortcuts system)
- All keyboard shortcuts now bound through centralized `_bind_keyboard_shortcuts()` method
- Command palette integrates with all existing features
- CLI `promptc palette favorites --clear` now reports when nothing was removed and exits with status 1 for easier scripting
- Version updated to 2.0.45

### Fixed
- Keyboard shortcuts now properly integrated with existing UI components
- Theme toggle accessible via both UI and keyboard shortcut
- Copy operations now work from any tab
- Sidebar visibility controlled via keyboard shortcuts

## [2.0.44] - 2025-11-11
### Added
- **UI Customization & Settings**: Comprehensive appearance and behavior settings
  - **⚙️ Settings Dialog**: Centralized settings panel with tabbed interface
  - **Theme Selection**: Quick switch between Light and Dark modes
  - **Accent Colors**: 6 color options (Blue, Green, Purple, Pink, Orange, Red)
  - **Font Size Options**: Small, Medium, and Large text sizes
  - **View Modes**: Compact and Comfortable spacing options
  - **Live Preview**: See changes before applying
  - **Behavior Settings**: Window and sidebar preferences
  - **About Tab**: Version and feature information
  - All settings persist across sessions
  - Reset to defaults option
- **Enhanced UI**: Settings button added to toolbar with ⚙️ icon
- **Settings Persistence**: Accent color, font size, and view mode saved to config

### Changed
- UI initialization now loads custom accent color, font size, and view mode
- Settings structure expanded to include appearance preferences
- Version updated to 2.0.44

## [2.0.43] - 2025-11-08
### Added
- **Export/Import System**: Backup and restore your data with flexible options
  - **💾 Export All**: Export complete backup (history + tags + snippets + settings)
  - **📋 Export History**: Export only prompt history
  - **🏷️ Export Tags**: Export only tag definitions
  - Auto-generated timestamped filenames (e.g., `promptc_backup_20251108_143052.json`)
  - JSON format with UTF-8 support and pretty-printing
  - Version and export date metadata included
- **Import Functionality**: Restore data from exported files
  - **Merge Mode**: Combine with existing data (duplicate detection)
  - **Replace Mode**: Replace all existing data
  - Validation of JSON structure
  - Version compatibility check
  - User confirmation dialog with import details
  - Smart duplicate detection based on timestamp + content
- **Auto-Backup System**: Automatic data protection
  - Creates backup automatically on app close
  - Stores in `~/.promptc_backups/` directory
  - Keeps last 5 backups (older ones auto-deleted)
  - Backup includes all data: history, tags, snippets, settings
  - Silent operation (no user interruption)
- **Restore Backup UI**: Easy recovery from automatic backups
  - "♻️ Restore Backup" button in sidebar
  - Lists all available backups with timestamps
  - Shows backup details: prompt count, tags, snippets
  - Date-sorted list (newest first)
  - One-click restore with confirmation
  - Visual feedback on success

### Changed
- Sidebar now includes "📤 Backup & Restore" section
- Export buttons added to sidebar with clear labels
- `_on_close()` enhanced to create auto-backup before exit

## [2.0.42] - 2025-11-07
### Added
- **Advanced Analytics Dashboard**: Comprehensive usage insights
  - **Overview Tab**: Total prompts, favorites count, total usage, average length
  - **Top Tags Tab**: Tag usage distribution with counts
  - **Most Used Tab**: Top 10 prompts by usage count with ↻ indicator
  - **Recent Activity Tab**: 7-day activity visualization with bar charts
  - Interactive notebook interface with multiple tabs
  - Real-time statistics calculation
  - Color-coded visualizations (#3b82f6 blue theme)
- **Usage Tracking**: Track how often each prompt is used
  - `usage_count` field added to history items
  - Automatically increments when prompt is loaded
  - Persisted to JSON on each use
  - Displayed in history list with (↻n) indicator
- **Advanced Filtering**: Multi-criteria search and filter
  - **Favorites Only**: Toggle to show only starred prompts
  - **Length Filter**: short (<100), medium (100-500), long (>500 chars)
  - **Date Range**: all, today, last 7/30/90 days
  - **Sorting**: newest/oldest, shortest/longest, most/least used
  - "🔄 Clear Filters" button to reset all filters
  - "📊 View Analytics" button to open dashboard
  - All filters work together (AND logic)
  - Backward compatible with old history format
- **Enhanced History Display**: Better visual feedback
  - Usage count indicator: (↻n) after preview
  - Length tracking for all prompts
  - Date-based filtering with datetime parsing
  - Multi-criteria sorting support

### Changed
- History item schema extended with `usage_count` and `length` fields
- `_refresh_history()` completely rewritten with comprehensive filtering
- `_load_prompt_from_history()` now tracks and persists usage
- Sidebar expanded with advanced filters section
- Filter controls use modern dropdowns and checkboxes

## [2.0.41] - 2025-11-06
### Added
- **Tags System**: Organize and filter prompts with color-coded tags
  - 8 default tags: code, writing, analysis, debug, review, tutorial, test, docs
  - Each tag has unique color for visual identification
  - Tag management UI with checkboxes
  - Add/remove tags via context menu (🏷️ Manage Tags)
  - Tags persist in `~/.promptc_tags.json`
  - Tag indicators shown in history list: `[code] [review]`
- **Tag Filtering**: Multi-tag filter support in sidebar
  - Click tag buttons to filter history
  - Multiple tags show items with ANY selected tag
  - "All" button clears all filters
  - Combined search + tag filtering
  - Active tags highlighted with their color
- **Snippets Library**: Reusable prompt templates and fragments
  - 3 default snippets: Code Review, Bug Report, Explain Code
  - Quick insert with double-click or Enter
  - Snippet categories: code, writing, debug, review, tutorial, test, docs, general
  - Snippets panel in sidebar with scrollable list
  - Persist in `~/.promptc_snippets.json`
- **Snippet Management**: Full CRUD operations
  - Create new snippets with "+" button
  - Edit existing snippets via context menu
  - Delete snippets with confirmation
  - Snippets insert at cursor position
  - Name, category, and multi-line content support
- Documentation: `docs/TAGS_SNIPPETS_GUIDE.md` with comprehensive guide

### Changed
- History items now include "tags" field (array)
- Sidebar expanded with tags filter section and snippets panel
- Context menu updated with "🏷️ Manage Tags" option
- History display shows tag indicators after preview

## [2.0.40] - 2025-11-05
### Added
- **Recent Prompts Sidebar**: Track and quickly access your prompt history
  - Resizable sidebar with PanedWindow layout
  - Shows 100 most recent prompts with previews
  - Real-time search/filter functionality
  - Favorites system with ⭐ star icons
  - Context menu (Load, Delete, Toggle Favorite)
  - Keyboard shortcuts: Enter (load), Delete (remove)
  - Toggle sidebar visibility with ◀/▶ button
  - Auto-save prompts to `~/.promptc_history.json`
  - Double-click or Enter to load prompts
  - Right-click context menu for quick actions
- Documentation: `docs/SIDEBAR_GUIDE.md` with usage instructions

### Changed
- UI: Restructured layout with PanedWindow for sidebar
- UI: Moved content area to separate frame
- Added `datetime` import for timestamps

## [2.0.39] - 2025-11-04
### Added
- **Drag & Drop File Loading**: Drop .txt/.md files directly into prompt/context areas
  - Visual drop zone indicators
  - Support for multiple file formats (.txt, .md, .markdown, .text)
  - Confirmation dialog before replacing content
  - "📂 Load" buttons as fallback
  - Character and line count display on load
- Documentation: `docs/DRAG_DROP_GUIDE.md` with usage guide

## [2.0.38] - 2025-11-03
### Added
- **Modern UI Theme**: Enhanced visual design with colors and icons
  - Unicode emoji icons on all buttons (📄, 🔍, ⚙️, etc.)
  - Modern color palette for light/dark themes
  - JSON syntax highlighting in output tabs
  - Real-time syntax coloring (keys, strings, numbers, booleans)
  - Progress bar animation during generation
  - Tooltips on all interactive elements
  - Improved button styling with hover effects

## [2.0.37] - 2025-11-02
### Added
- **Template Gallery**: 10 built-in prompt templates with CLI integration
  - Templates: code-review, bug-report, feature-request, refactor, test-gen, docs, security-audit, performance, api-design, data-analysis
  - CLI commands: `promptc gallery list`, `search <keyword>`, `preview <template>`, `use <template>`
  - Template metadata: category, description, parameters, usage examples
  - 31 comprehensive tests (all passing)
- Core: `app/template_gallery.py` module with template system
- CLI: Gallery commands in `cli/main.py`

## [2.0.10] - 2025-01-XX
### Added
- **Automatic Prompt Fixing**: New `fix` CLI command and `/fix` API endpoint
  - Intelligently applies fixes based on validation issues
  - Replaces vague terms ("something" → "a specific component", "stuff" → "data")
  - Adds domain-appropriate personas when missing
  - Adds example sections for complex tasks
  - Specifies output format when unclear
  - Adds safety constraints for risky domains
  - Configurable target score and max fixes
  - Shows before/after diff with confidence scores
  - JSON output for programmatic use
- CLI: `promptc fix <text>` with options: `--from-file`, `--stdin`, `--apply`, `--max-fixes`, `--target-score`, `--diff`, `--json`, `--out`
- API: `POST /fix` endpoint accepting prompt text and returning fixed version with improvement metrics
- Core: `app/autofix.py` module with `auto_fix_prompt()` function and fix strategies
- Tests: 14 comprehensive autofix tests (all passing)

### Changed
- Tests: 104 total tests (90 → 104), all passing

### Docs
- README: Added "Auto-Fix" section with CLI examples, fix types, and sample output
- README: Added API `/fix` endpoint documentation with example request/response

## [2.0.9] - 2025-01-XX
### Added
- **Prompt Validation & Quality Scoring System**: New `validate-prompt` CLI command and `/validate` API endpoint
  - Quality scoring across 4 categories: clarity (25%), specificity (25%), completeness (35%), consistency (15%)
  - Anti-pattern detection: vague terms, conflicting constraints, missing critical elements
  - Strengths identification and actionable improvement suggestions
  - Rich-formatted CLI output with color-coded scores and severity indicators
  - JSON output support for programmatic use
  - `--min-score` threshold for CI/CD integration (exit code 1 if below threshold)
  - Comprehensive validator test suite (15 tests covering edge cases)
- CLI: `promptc validate-prompt <text>` with options: `--from-file`, `--stdin`, `--json`, `--out`, `--suggestions`, `--strengths`, `--min-score`
- API: `POST /validate` endpoint accepting prompt text and returning quality scores, issues, and strengths
- Core: `app/validator.py` module with `PromptValidator` class and `validate_prompt()` function

### Changed
- Tests: 90 total tests (75 → 90), all passing

### Docs
- README: Added "Prompt Validation" section with CLI examples and API endpoint documentation
- README: Updated with quality score categories and use cases (pre-validation, team standards, learning)

## [2.0.8] - 2025-09-28
### Added
- CLI (RAG): `promptc rag pack` gains `--sources {none|list|full}` to control the sources section in Markdown output
- CLI (diff): `promptc diff` gains `--out <file>` to write the diff to a file (plain unified diff; with `--color` uses Rich markup)
- CLI (batch): `promptc batch` gains `--summary-json <path>` to write a machine-readable summary with counts, timings, and error samples
### Docs
- README updated with usage examples for `rag pack --sources`, `diff --out`, and `batch --summary-json`

## [2.0.7] - 2025-09-08
### Changed
- Migrated codebase to Pydantic v2 (use `@field_validator`, `ConfigDict`, and `.model_dump()`)
- requirements: bump `pydantic` to `2.8.2`
### Fixed
- Removed deprecation warnings; test suite remains green (44/44)
### Docs
- README updated to note the Pydantic v2 requirement

## [2.0.5] - 2025-09-03
### Added
- CLI: `--from-file` flag on root and `compile` commands to read prompt text from UTF-8 files
- Desktop UI: "Copy all" action for prompt tabs; "Export JSON" on IR v1/v2 tabs; "Export MD" for Expanded
- API: `/healthz` alias for health and a tiny web demo enhancement with Copy/Export actions
### Changed
- Docs: README updated (CLI --from-file examples, UI export/copy details, API endpoints)
- Tooling: ruff and pre-commit configuration added; CI continues to lint with ruff

## [2.0.6] - 2025-09-04
### Added
- CLI: `--out`, `--out-dir`, and `--format {json|md}` to save outputs to files (supports v1/v2 JSON and combined Markdown)
- API: `/version` now returns `{ version, git_sha, ir_schema_version }`
- Desktop UI: IR Diff tab (v1 vs v2), Ctrl+F quick find dialog, and "Export Trace" on the Constraints toolbar
- Desktop UI: Persist Only live_debug filter in `~/.promptc_ui.json`
### Fixed
- Desktop UI: Resolved indentation/scope errors around constraints toolbar and diff tab; improved theming coverage
### Docs
- README updated with new CLI save flags, UI IR Diff/Ctrl+F/Export Trace features, and `/version` response example

## [2.0.0] - 2025-08-25
### Changed
- IR v2 is now the default in API (`v2: true` by default) and CLI (use `--v1` to access legacy output and prompt renderers)
- IR v2 metadata now includes `ir_version=2.0` and `package_version=2.0.0`
### Added
- API continues to return IR v1 alongside IR v2 when requested; default response includes `ir_v2`
### Migration Notes
- If you rely on prompt renderers (system/user/plan/expanded), use `--v1` in CLI or `{"v2": false}` in API until v2 renderers are introduced

## [2.0.1] - 2025-08-27
### Added
- Desktop UI: Trace toggle and new Trace tab
- Desktop UI: IR v2 JSON tab
- Desktop UI: Save dialog to export combined Markdown or IR JSON (v1/v2)
### Changed
- Desktop UI: Status line now shows processing time and heuristic versions

## [2.0.2] - 2025-08-28
### Added
- Desktop UI: Intent chips under the summary (from IR v2 `intents`)
- Desktop UI: IR v2 Constraints Viewer tab (table with priority/origin/id/text) and Copy action

## [2.0.3] - 2025-08-30
### Added
- Desktop UI: "Send to OpenAI" controls (model field, Use Expanded toggle, send button) and an "OpenAI Response" tab
### Docs
- README updated to include UI OpenAI send instructions and screenshot placeholder (`docs/images/desktop_openai.png`)

## [2.0.4] - 2025-09-02
### Added
- Persona: New `developer` coding assistant persona with precedence over teacher when coding context is detected
- Heuristics: Live debug detection (MRE, stack trace analysis, iterative fixes) and coding constraints (runnable examples, tests/usage)
- IR v2: `persona` now permits `developer`; new `intents` value `debug` when live debug is detected
- UI: IR v2 Constraints Viewer gains an "Only live_debug" filter checkbox
### Tests
- New tests covering developer persona triggers and IR v2 debug intent
### Docs
- README updated with developer/live debug notes, CLI examples, and UI filter mention

## [0.1.9] - 2025-08-24
### Added
- External patterns config loader (YAML/JSON) for domain, ambiguity, risk keywords override
- Structured clarification objects (`metadata.clarify_questions_struct` with category + question)
- Temporal signal extraction (`metadata.temporal_flags`) for years, quarters, relative time phrases
- Quantity extraction (`metadata.quantities`) for numeric + unit patterns (minutes, hours, days, counts, ranges)
- Constraint origin tracking (`metadata.constraint_origins`) mapping each constraint to its heuristic source
- Teaching mode constraints refactored to integrate pre-IR creation (fixing regression)
- IR v2 (preview, behind flag): new `IRv2` model with typed `constraints {id,text,origin,priority}` and `intents` + typed `steps`; Python API `compile_text_v2`, HTTP API `v2: true` returns `ir_v2`
- IR v2 JSON Schema: `schema/ir_v2.schema.json`
- Basic Spanish (es) language support across detection, models/schemas, and emitters (localized labels)
### Changed
- Rebuilt `compile_text` for clearer pipeline order and early teaching enrichment
- Domain confidence now `None` (instead of 0.0) when domain is `general` or no evidence
- Heuristic version bumped to 2025.08.21-1
 - Heuristic2 (v2) version introduced: 2025.08.23-0 (for IR v2 mapping/priorities)
### Fixed
- Restored teaching intent constraints (friendly tone, pedagogical flow, source recommendations)
- Regression causing missing duration/level constraints in teaching tests

## [0.1.5] - 2025-08-18
### Added
## [0.1.6] - 2025-08-19
### Added
### Changed
### Fixed

### Changed
### Fixed

## [0.1.7] - 2025-08-19
### Added
- PII detection (email, phone, credit card, IBAN) -> metadata.pii_flags and privacy constraints
- Domain candidates list (metadata.domain_candidates) for broader coverage insight
- Trace now includes pii_flags and domain_candidates
### Changed
- Heuristic version bumped to 2025.08.19-2 for coverage/accuracy iteration
### Fixed
- None (backward compatible; existing tests unaffected)
## [0.1.8] - 2025-08-20
### Added
- Domain confidence ratio (metadata.domain_confidence) + raw counts (metadata.domain_scores) + scoring mode (metadata.domain_score_mode)
- Trace lines now show domain_conf and domain_scores
### Changed
- Heuristic version bumped to 2025.08.20-1 for confidence feature
### Fixed
- None (all tests pass)

- Offline Desktop UI (`ui_desktop.py`) with prompt input, diagnostics toggle, copy buttons, summary header
### Changed
- README updated (Desktop UI feature + usage section, screenshots placeholders)

## [0.1.4] - 2025-08-16
### Added
- Always-on Clarification Questions block (appears before diagnostics when ambiguous terms exist)
- Lightweight Assumptions block (missing details, disclaimer for risk domains, variant differentiation rule)
### Changed
- README updated (features list + new Assumptions & Clarification Blocks section)

## [0.1.2] - 2025-08-15
### Added
- Extended heuristics: risk flags (financial/health/legal), entity extraction, complexity estimate, ambiguous term detection + clarify questions, code request detection
- New metadata fields: risk_flags, entities, complexity, ambiguous_terms, clarify_questions, code_request
### Changed
- Constraints automatically enriched for risk domains, ambiguous terms, and code examples with inline comments

## [0.1.1] - 2025-08-14
### Added
- Structured persona field (schema + model) with heuristic selection and evidence metadata
- Persona surfaced in System Prompt, Expanded Prompt context, and CLI output
### Changed
- README updated (persona in features, schema, API response example)

## [0.1.1] - 2025-08-14
### Added
- Language-specific teaching personas (TR / EN)
- Analogy usage constraints for teaching mode (TR & EN)
- Explicit role display in CLI output
### Changed
- Teaching mode feature list updated in README (persona + analogies)

## [0.1.0] - 2025-08-12
- Initial release: Prompt Compiler App with IR, API, CLI, tests
- Recency rule, language/domain detection
- Expanded Prompt and teaching mode with level/duration
- Inputs extraction (interest, budget, format)
