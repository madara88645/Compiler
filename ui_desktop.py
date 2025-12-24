"""Offline desktop UI (tkinter) for Prompt Compiler

Run:
  python ui_desktop.py

Features:
  - Prompt input textbox
  - Diagnostics checkbox (risk & ambiguity in expanded prompt)
  - Generate / Clear / Show Schema buttons
  - Copy buttons per output tab
  - Persona + Complexity + Risk summary header
  - Light / Dark theme toggle
"""

from __future__ import annotations
import difflib
import json
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import time
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional, List

import httpx
from app.analytics import AnalyticsManager, create_record_from_ir

from app.compiler import (
    compile_text,
    compile_text_v2,
    optimize_ir,
    HEURISTIC_VERSION,
    HEURISTIC2_VERSION,
    generate_trace,
)
from app.emitters import (
    emit_system_prompt,
    emit_user_prompt,
    emit_plan,
    emit_expanded_prompt,
    emit_system_prompt_v2,
    emit_user_prompt_v2,
    emit_plan_v2,
    emit_expanded_prompt_v2,
)
from app.autofix import auto_fix_prompt, explain_fixes
from app.validator import PromptValidator
from app.templates import get_registry, PromptTemplate
from app.rag.simple_index import search, search_embed, search_hybrid
from app.context_presets import ContextPresetStore
from app.text_utils import estimate_tokens, compress_text_block
from app.rag.history_store import RAGHistoryStore
from app.command_palette import (
    CONFIG_ENV_VAR,
    compute_stale_favorites,
    get_command_palette_commands,
    get_saved_palette_favorites_list,
    get_ui_config_path,
    persist_palette_favorites,
)

# Optional OpenAI client (only used when sending directly from UI)
try:  # openai>=1.0 style client
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dep
    OpenAI = None  # type: ignore


class PromptCompilerUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("✨ Prompt Compiler")
        self.root.geometry("1200x780")
        self.root.minsize(1000, 650)
        self.current_theme = "light"

        # UI Customization settings
        self.accent_color = "#3b82f6"  # Default blue
        self.font_size = "medium"  # small, medium, large
        self.view_mode = "comfortable"  # compact, comfortable
        self.var_user_level = tk.StringVar(value="intermediate")
        self.var_task_type = tk.StringVar(value="general")
        self.cognitive_load_var = tk.StringVar(value="Load: —")

        # Settings file (per-user)
        self.config_path = get_ui_config_path()
        self.history_path = Path.home() / ".promptc_history.json"
        self.favorites_path = Path.home() / ".promptc_favorites.json"
        self.tags_path = Path.home() / ".promptc_tags.json"
        self.snippets_path = Path.home() / ".promptc_snippets.json"
        self.command_palette_favorites: list[str] = []
        self.command_palette_recent: list[str] = []
        self.rag_history_store = RAGHistoryStore()
        self.context_presets_store = ContextPresetStore()
        self.context_preset_menu = None
        self.analytics_manager = AnalyticsManager()

        # RAG settings (defaults)
        self.rag_db_path = None  # None = use default ~/.promptc_index.db
        self.rag_embed_dim = 64
        self.rag_method = "fts"  # fts, embed, hybrid

        # Progress indicator
        self.progress_var = tk.DoubleVar(value=0)
        self.is_generating = False

        # History and favorites data
        self.history_items = []
        self.favorites_items = []
        self.sidebar_visible = True

        # Tags and snippets data
        self.available_tags = []
        self.snippets = []
        self.active_tag_filter = []

        # Quality coach state
        self.prompt_validator = PromptValidator()
        self.last_quality_result = None
        self.last_quality_prompt = ""
        self.pending_auto_fix_text = None
        self.last_autofix_result = None
        self._quality_report_placeholder = (
            "Run an analysis to see per-category scores, detected issues, and strengths."
        )
        self._quality_fix_placeholder = (
            "Auto-fix results (reports and diffs) will appear here once you run the fixer."
        )
        self.quality_total_var = tk.StringVar(value="—")
        self.quality_breakdown_var = tk.StringVar(
            value="Analyze the prompt to see detailed scores."
        )
        self.quality_status_var = tk.StringVar(value="Ready")

        # Template system
        self.template_registry = get_registry()
        self.current_template = None

        # Main container with sidebar
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Left sidebar
        self.sidebar = ttk.Frame(main_container, width=250)
        main_container.add(self.sidebar, weight=0)
        self._create_sidebar()

        # Right content area
        content = ttk.Frame(main_container)
        main_container.add(content, weight=1)

        # Progress bar at the top of content area
        self.progress_frame = ttk.Frame(content)
        self.progress_frame.pack(fill=tk.X, padx=8, pady=(4, 0))
        self.progress_bar = ttk.Progressbar(
            self.progress_frame, mode="indeterminate", variable=self.progress_var, length=200
        )

        # Input area
        top = ttk.Frame(content, padding=8)
        top.pack(fill=tk.X)

        # Drop zone indicator (shown when dragging)
        self.drop_zone_frame = ttk.Frame(top, relief="solid", borderwidth=2)
        self.drop_zone_var = tk.StringVar(value="")
        self.drop_zone_label = tk.Label(
            self.drop_zone_frame,
            textvariable=self.drop_zone_var,
            font=("", 12, "bold"),
            foreground="#3b82f6",
            padx=20,
            pady=10,
        )

        prompt_header = ttk.Frame(top)
        prompt_header.pack(fill=tk.X)
        ttk.Label(prompt_header, text="📝 Prompt:", font=("", 10, "bold")).pack(side=tk.LEFT)
        btn_load_prompt = ttk.Button(
            prompt_header, text="📂 Load", command=lambda: self._load_file_dialog("prompt"), width=8
        )
        btn_load_prompt.pack(side=tk.RIGHT, padx=(4, 0))
        self._add_tooltip(btn_load_prompt, "Load prompt from file (or drag & drop)")

        self.txt_prompt = tk.Text(top, height=5, wrap=tk.WORD)
        self.txt_prompt.pack(fill=tk.X, pady=(2, 6))

        # Setup drag & drop for prompt area
        self._setup_drag_drop(self.txt_prompt, target="prompt")

        # Prompt stats (chars/words)
        self.prompt_stats_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.prompt_stats_var, foreground="#666").pack(anchor=tk.W)

        # Context (optional)
        ctx_row = ttk.Frame(top)
        ctx_row.pack(fill=tk.X, pady=(8, 0))

        ctx_header = ttk.Frame(ctx_row)
        ctx_header.pack(fill=tk.X)
        ttk.Label(ctx_header, text="📋 Context (optional):", font=("", 10, "bold")).pack(
            side=tk.LEFT
        )
        btn_presets = ttk.Menubutton(ctx_header, text="📚 Presets", width=10)
        btn_presets.pack(side=tk.RIGHT, padx=(4, 0))
        self.context_preset_menu = tk.Menu(btn_presets, tearoff=0)
        btn_presets["menu"] = self.context_preset_menu
        self._add_tooltip(btn_presets, "Load or save context presets")
        btn_pins = ttk.Button(ctx_header, text="📌 Pins", command=self._show_rag_pins, width=8)
        btn_pins.pack(side=tk.RIGHT, padx=(4, 0))
        self._add_tooltip(btn_pins, "Insert from pinned RAG snippets")
        btn_search_docs = ttk.Button(
            ctx_header, text="🔍 Search", command=self._show_rag_search, width=8
        )
        btn_search_docs.pack(side=tk.RIGHT, padx=(4, 0))
        self._add_tooltip(btn_search_docs, "Search indexed documents (RAG)")
        btn_load_context = ttk.Button(
            ctx_header, text="📂 Load", command=lambda: self._load_file_dialog("context"), width=8
        )
        btn_load_context.pack(side=tk.RIGHT, padx=(4, 0))
        self._add_tooltip(btn_load_context, "Load context from file (or drag & drop)")

        self.txt_context = tk.Text(ctx_row, height=4, wrap=tk.WORD)
        self.txt_context.pack(fill=tk.X, pady=(2, 6))

        # Setup drag & drop for context area
        self._setup_drag_drop(self.txt_context, target="context")

        self.var_include_context = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            ctx_row, text="Include context in prompts", variable=self.var_include_context
        ).pack(anchor=tk.W)

        # Options row
        opts = ttk.Frame(top)
        opts.pack(fill=tk.X)
        self.var_diag = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Diagnostics", variable=self.var_diag).pack(side=tk.LEFT)
        self.var_trace = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Trace", variable=self.var_trace).pack(side=tk.LEFT, padx=(6, 0))
        # Toggle: render prompts using IR v2 emitters
        self.var_render_v2 = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Use IR v2 emitters", variable=self.var_render_v2).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        # Toggle: wrap long lines in output panes
        self.var_wrap = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Wrap output", variable=self.var_wrap).pack(
            side=tk.LEFT, padx=(6, 0)
        )

        self.btn_generate = ttk.Button(opts, text="⚡ Generate", command=self.on_generate)
        self.btn_generate.pack(side=tk.LEFT, padx=4)
        self._add_tooltip(
            self.btn_generate, "Compile prompt and generate outputs (Ctrl+Enter or F5)"
        )

        btn_schema = ttk.Button(opts, text="📄 Schema", command=self.on_show_schema)
        btn_schema.pack(side=tk.LEFT, padx=4)
        self._add_tooltip(btn_schema, "View IR JSON schema structure")

        btn_clear = ttk.Button(opts, text="🗑️ Clear", command=self.on_clear)
        btn_clear.pack(side=tk.LEFT, padx=4)
        self._add_tooltip(btn_clear, "Clear all outputs and reset interface")

        btn_save = ttk.Button(opts, text="💾 Save", command=self.on_save)
        btn_save.pack(side=tk.LEFT, padx=4)
        self._add_tooltip(btn_save, "Save outputs to file (Ctrl+S)")

        self.btn_theme = ttk.Button(opts, text="🌙 Dark", command=self.toggle_theme)
        self.btn_theme.pack(side=tk.LEFT, padx=4)
        self._add_tooltip(self.btn_theme, "Toggle light/dark theme")

        btn_settings = ttk.Button(opts, text="⚙️ Settings", command=self._show_settings)
        btn_settings.pack(side=tk.LEFT, padx=4)
        self._add_tooltip(btn_settings, "Customize UI appearance and behavior")

        btn_templates = ttk.Button(opts, text="📋 Templates", command=self._show_template_manager)
        btn_templates.pack(side=tk.LEFT, padx=4)
        self._add_tooltip(btn_templates, "Manage and use prompt templates")

        self.btn_palette = ttk.Button(opts, text="🧭 Palette", command=self._show_command_palette)
        self.btn_palette.pack(side=tk.LEFT, padx=4)
        self._add_tooltip(self.btn_palette, "Open Command Palette (Ctrl+Shift+P)")
        self.palette_badge_var = tk.StringVar(value="")
        self.palette_badge_label = None

        btn_chat = ttk.Button(opts, text="💬 Chat (beta)", command=self._show_chat_window)
        btn_chat.pack(side=tk.LEFT, padx=4)
        self._add_tooltip(btn_chat, "Chat directly with your selected LLM without copy/paste")

        # Examples dropdown
        try:
            ex_files = sorted((Path("examples")).glob("*.txt"))
        except Exception:
            ex_files = []
        self._examples_map = {p.name: p for p in ex_files}
        if self._examples_map:
            ttk.Label(opts, text="Examples:").pack(side=tk.LEFT, padx=(12, 2))
            self.var_example = tk.StringVar(value="<select>")
            self.cmb_examples = ttk.Combobox(
                opts,
                textvariable=self.var_example,
                width=24,
                state="readonly",
                values=tuple(["<select>"] + list(self._examples_map.keys())),
            )
            self.cmb_examples.pack(side=tk.LEFT)
            self.cmb_examples.bind("<<ComboboxSelected>>", self._on_example_selected)
            # Toggle: auto-generate after loading an example
            self.var_autogen_example = tk.BooleanVar(value=False)
            ttk.Checkbutton(opts, text="Auto-generate", variable=self.var_autogen_example).pack(
                side=tk.LEFT, padx=(6, 0)
            )

        # LLM quick-send controls
        ttk.Label(opts, text="Provider:").pack(side=tk.LEFT, padx=(12, 2))
        self.var_llm_provider = tk.StringVar(value="OpenAI")
        self.cmb_llm_provider = ttk.Combobox(
            opts,
            textvariable=self.var_llm_provider,
            width=12,
            state="readonly",
            values=("OpenAI", "Local HTTP"),
        )
        self.cmb_llm_provider.pack(side=tk.LEFT)
        self.cmb_llm_provider.bind("<<ComboboxSelected>>", lambda _e: self._update_llm_controls())
        ttk.Label(opts, text="Model:").pack(side=tk.LEFT, padx=(8, 2))
        self._openai_models = (
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4.1-mini",
            "gpt-4.1",
        )
        self._local_model_suggestions = (
            "llama3",
            "llama3.1",
            "phi-3",
            "qwen2.5",
        )
        self.var_model = tk.StringVar(value="gpt-4o-mini")
        self.cmb_model = ttk.Combobox(
            opts,
            textvariable=self.var_model,
            width=18,
            state="normal",
            values=self._openai_models,
        )
        self.cmb_model.pack(side=tk.LEFT)
        self.var_openai_expanded = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Use Expanded", variable=self.var_openai_expanded).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        self.btn_send_llm = ttk.Button(opts, text="🤖 Send to OpenAI", command=self.on_send_openai)
        self.btn_send_llm.pack(side=tk.LEFT, padx=6)
        self._add_tooltip(self.btn_send_llm, "Send compiled prompt directly to OpenAI API")

        # User metadata controls
        ttk.Label(opts, text="User Level:").pack(side=tk.LEFT, padx=(12, 2))
        self.cmb_user_level = ttk.Combobox(
            opts,
            textvariable=self.var_user_level,
            width=12,
            state="readonly",
            values=("beginner", "intermediate", "advanced"),
        )
        self.cmb_user_level.pack(side=tk.LEFT)
        ttk.Label(opts, text="Task Type:").pack(side=tk.LEFT, padx=(8, 2))
        self.cmb_task_type = ttk.Combobox(
            opts,
            textvariable=self.var_task_type,
            width=12,
            state="readonly",
            values=("general", "analysis", "coding", "teaching", "ab_test"),
        )
        self.cmb_task_type.pack(side=tk.LEFT)

        llm_extra = ttk.Frame(top)
        llm_extra.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(llm_extra, text="Endpoint:").pack(side=tk.LEFT)
        self.var_local_endpoint = tk.StringVar(value="http://localhost:11434/v1/chat/completions")
        self.entry_local_endpoint = ttk.Entry(
            llm_extra, textvariable=self.var_local_endpoint, width=38
        )
        self.entry_local_endpoint.pack(side=tk.LEFT, padx=(4, 8))
        self._add_tooltip(
            self.entry_local_endpoint,
            "HTTP endpoint compatible with OpenAI chat format (e.g., Ollama, LM Studio)",
        )
        ttk.Label(llm_extra, text="API key (optional):").pack(side=tk.LEFT)
        self.var_local_api_key = tk.StringVar(value="")
        self.entry_local_api_key = ttk.Entry(
            llm_extra, textvariable=self.var_local_api_key, width=20, show="*"
        )
        self.entry_local_api_key.pack(side=tk.LEFT, padx=(4, 0))
        self._add_tooltip(
            self.entry_local_api_key,
            "Optional Authorization header for self-hosted gateways",
        )
        self._local_entries = (self.entry_local_endpoint, self.entry_local_api_key)
        self._update_llm_controls()

        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(opts, textvariable=self.status_var, foreground="#555").pack(side=tk.RIGHT)

        # Summary line + cognitive load indicator
        self.summary_var = tk.StringVar(value="")
        summary_frame = ttk.Frame(content, padding=(8, 0))
        summary_frame.pack(fill=tk.X)
        ttk.Label(summary_frame, textvariable=self.summary_var).pack(side=tk.LEFT)
        ttk.Label(summary_frame, textvariable=self.cognitive_load_var, foreground="#555").pack(
            side=tk.RIGHT
        )

        # Intents chips (IR v2)
        self.chips_frame = ttk.Frame(content, padding=(8, 2))
        self.chips_frame.pack(fill=tk.X)
        self.chips_container = ttk.Frame(self.chips_frame)
        self.chips_container.pack(anchor=tk.W)

        # Notebook outputs
        self.nb = ttk.Notebook(content)
        self.output_notebook = self.nb
        self.nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.txt_system = self._add_tab("System Prompt")
        self.txt_user = self._add_tab("User Prompt")
        self.txt_plan = self._add_tab("Plan")
        self.txt_expanded = self._add_tab("Expanded Prompt")
        self.txt_ir = self._add_tab("IR JSON")
        self.txt_ir2 = self._add_tab("IR v2 JSON")
        self.txt_llm = self._add_tab("LLM Response")
        # IR v2 Constraints Viewer tab (table)
        cons_frame = ttk.Frame(self.nb)
        self.nb.add(cons_frame, text="IR v2 Constraints")
        cons_bar = ttk.Frame(cons_frame)
        cons_bar.pack(fill=tk.X)
        ttk.Button(cons_bar, text="Copy", command=self._copy_constraints).pack(
            side=tk.LEFT, padx=2, pady=2
        )
        ttk.Button(cons_bar, text="Export CSV", command=self._export_constraints_csv).pack(
            side=tk.LEFT, padx=2, pady=2
        )
        ttk.Button(cons_bar, text="Export JSON", command=self._export_constraints_json).pack(
            side=tk.LEFT, padx=2, pady=2
        )
        ttk.Button(cons_bar, text="Export Trace", command=self._export_trace).pack(
            side=tk.LEFT, padx=2, pady=2
        )
        # Filter: show only live_debug origin constraints
        self.var_only_live_debug = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            cons_bar,
            text="Only live_debug",
            variable=self.var_only_live_debug,
            command=self._render_constraints_table,
        ).pack(side=tk.LEFT, padx=6)
        # Text search filter
        ttk.Label(cons_bar, text="Search:").pack(side=tk.LEFT, padx=(6, 2))
        self.var_constraints_search = tk.StringVar(value="")
        ent_search = ttk.Entry(cons_bar, textvariable=self.var_constraints_search, width=18)
        ent_search.pack(side=tk.LEFT)
        self.var_constraints_search.trace_add("write", lambda *_: self._render_constraints_table())
        # Min priority filter
        ttk.Label(cons_bar, text="Min priority:").pack(side=tk.LEFT, padx=(12, 4))
        self.var_min_priority = tk.StringVar(value="Any")
        self.cmb_min_priority = ttk.Combobox(
            cons_bar,
            textvariable=self.var_min_priority,
            width=6,
            state="readonly",
            values=("Any", "90", "80", "70", "65", "60", "50", "40", "30", "20", "10"),
        )
        self.cmb_min_priority.pack(side=tk.LEFT)
        self.cmb_min_priority.bind(
            "<<ComboboxSelected>>", lambda _e: self._render_constraints_table()
        )
        self.tree_constraints = ttk.Treeview(
            cons_frame, columns=("priority", "origin", "id", "text"), show="headings"
        )
        # Add clickable headings for sorting
        self._constraints_sort_state = {"col": None, "reverse": False}
        self.tree_constraints.heading(
            "priority", text="Priority", command=lambda c="priority": self._sort_constraints(c)
        )
        self.tree_constraints.heading(
            "origin", text="Origin", command=lambda c="origin": self._sort_constraints(c)
        )
        self.tree_constraints.heading(
            "id", text="ID", command=lambda c="id": self._sort_constraints(c)
        )
        self.tree_constraints.heading(
            "text", text="Text", command=lambda c="text": self._sort_constraints(c)
        )
        self.tree_constraints.column("priority", width=80, anchor=tk.CENTER)
        self.tree_constraints.column("origin", width=120, anchor=tk.W)
        self.tree_constraints.column("id", width=120, anchor=tk.W)
        self.tree_constraints.column("text", width=600, anchor=tk.W)
        self.tree_constraints.pack(fill=tk.BOTH, expand=True)

        self.txt_trace = self._add_tab("Trace")
        # IR Diff tab (v1 vs v2)
        self.txt_diff = self._add_tab("IR Diff")

        # Quality coach tab
        quality_frame = ttk.Frame(self.nb)
        self.nb.add(quality_frame, text="Quality Coach")
        self._build_quality_tab(quality_frame)

        # Load settings (theme, toggles, model, geometry) and apply
        self._load_settings()
        self.apply_theme(self.current_theme)
        self._update_palette_badge()

        # Persist on change
        self.var_diag.trace_add("write", lambda *_: self._save_settings())
        self.var_trace.trace_add("write", lambda *_: self._save_settings())
        self.var_model.trace_add("write", lambda *_: self._save_settings())
        self.var_openai_expanded.trace_add("write", lambda *_: self._save_settings())
        self.var_render_v2.trace_add("write", lambda *_: self._save_settings())
        self.var_only_live_debug.trace_add("write", lambda *_: self._render_constraints_table())
        self.var_wrap.trace_add("write", lambda *_: (self._apply_wrap(), self._save_settings()))
        self.var_min_priority.trace_add(
            "write", lambda *_: (self._render_constraints_table(), self._save_settings())
        )
        self.var_llm_provider.trace_add(
            "write", lambda *_: (self._update_llm_controls(), self._save_settings())
        )
        self.var_local_endpoint.trace_add("write", lambda *_: self._save_settings())
        self.var_local_api_key.trace_add("write", lambda *_: self._save_settings())
        self.var_user_level.trace_add("write", lambda *_: self._save_settings())
        self.var_task_type.trace_add("write", lambda *_: self._save_settings())
        try:
            # Persist auto-generate toggle if present
            getattr(self, "var_autogen_example", tk.BooleanVar(value=False)).trace_add(
                "write", lambda *_: self._save_settings()
            )
        except Exception:
            pass
        try:
            self.var_include_context.trace_add("write", lambda *_: self._save_settings())
        except Exception:
            pass

        # Shortcuts
        self.root.bind("<Control-Return>", lambda _e: self.on_generate())
        self.root.bind("<F5>", lambda _e: self.on_generate())
        # Quick search in text widgets - moved to Ctrl+Shift+F to avoid conflict
        # self.root.bind("<Control-f>", lambda _e: self._find_in_active())
        # Save geometry on close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        # Save selected tab on change
        try:
            self.nb.bind("<<NotebookTabChanged>>", lambda _e: self._save_settings())
        except Exception:
            pass
        # Ctrl+S save shortcut - will be overridden by _bind_keyboard_shortcuts
        # try:
        #     self.root.bind("<Control-s>", lambda _e: self.on_save())
        # except Exception:
        #     pass
        # Update prompt stats as user types
        try:
            self.txt_prompt.bind("<KeyRelease>", lambda _e: self._update_prompt_stats())
            self._update_prompt_stats()
        except Exception:
            pass

        # Bind all keyboard shortcuts
        self._bind_keyboard_shortcuts()
        # Apply initial wrap state
        try:
            self._apply_wrap()
        except Exception:
            pass

        # Load history, tags, snippets
        self._load_history()
        self._load_tags()
        self._load_snippets()
        self._refresh_context_presets_menu()

    # Quality coach operations

    def _run_quality_check(self):
        prompt = self.txt_prompt.get("1.0", tk.END).strip()
        if not prompt:
            messagebox.showwarning("Quality Coach", "Enter a prompt before analyzing.")
            return
        self._focus_quality_tab()
        self._set_quality_busy(True)
        self.quality_status_var.set("Analyzing prompt...")
        self.root.after(30, lambda: self._quality_worker(prompt))

    def _quality_worker(self, prompt: str):
        try:
            ir2 = compile_text_v2(prompt)
            result = self.prompt_validator.validate(ir2, prompt)
            self.root.after(0, lambda: self._render_quality_result(prompt, result))
        except Exception as exc:
            self.root.after(0, self._handle_quality_error, exc)
        finally:
            self.root.after(0, lambda: self._set_quality_busy(False))

    def _render_quality_result(self, prompt: str, result) -> None:
        self.last_quality_result = result
        self.last_quality_prompt = prompt
        self.quality_total_var.set(f"{result.score.total:.1f}/100")
        breakdown = (
            f"Clarity {result.score.clarity:.1f} | Specificity {result.score.specificity:.1f} | "
            f"Completeness {result.score.completeness:.1f} | Consistency {result.score.consistency:.1f}"
        )
        self.quality_breakdown_var.set(breakdown)
        report = self._format_quality_report(result)
        self._update_quality_text(self.txt_quality_report, report)
        self.pending_auto_fix_text = None
        try:
            self.btn_quality_apply_fix.config(state="disabled")
        except Exception:
            pass
        self.quality_status_var.set(
            f"Quality updated • {result.errors} errors • {result.warnings} warnings"
        )

    def _handle_quality_error(self, error: Exception) -> None:
        self.quality_status_var.set("Quality analysis failed")
        messagebox.showerror("Quality Coach", str(error))

    def _run_auto_fix(self):
        prompt = self.txt_prompt.get("1.0", tk.END).strip()
        if not prompt:
            messagebox.showwarning("Quality Coach", "Enter a prompt before auto-fixing.")
            return
        self._focus_quality_tab()
        self._set_quality_busy(True)
        self.quality_status_var.set("Running auto-fix...")
        self.root.after(30, lambda: self._auto_fix_worker(prompt))

    def _auto_fix_worker(self, prompt: str):
        try:
            result = auto_fix_prompt(prompt)
            report = explain_fixes(result)
            diff = difflib.unified_diff(
                result.original_text.splitlines(keepends=True),
                result.fixed_text.splitlines(keepends=True),
                fromfile="original",
                tofile="auto_fix",
            )
            diff_text = "".join(diff).strip() or "(No textual differences)"
            combined = f"{report}\n\n=== Diff ===\n{diff_text}"
            self.root.after(0, lambda: self._render_autofix_result(result, combined))
        except Exception as exc:
            self.root.after(0, self._handle_quality_error, exc)
        finally:
            self.root.after(0, lambda: self._set_quality_busy(False))

    def _render_autofix_result(self, result, combined_text: str):
        self.last_autofix_result = result
        self._update_quality_text(self.txt_quality_fix, combined_text)
        original = (result.original_text or "").strip()
        fixed = (result.fixed_text or "").strip()
        if fixed and fixed != original:
            self.pending_auto_fix_text = result.fixed_text
            self.btn_quality_apply_fix.config(state="normal")
            self.quality_status_var.set(
                f"Auto-fix ready • Improvement +{result.improvement:.1f} points"
            )
        else:
            self.pending_auto_fix_text = None
            self.btn_quality_apply_fix.config(state="disabled")
            self.quality_status_var.set("Auto-fix suggested no changes")

    def _apply_auto_fix(self):
        if not self.pending_auto_fix_text:
            messagebox.showinfo("Quality Coach", "Run auto-fix to generate suggestions first.")
            return
        self.txt_prompt.delete("1.0", tk.END)
        self.txt_prompt.insert("1.0", self.pending_auto_fix_text)
        self._update_prompt_stats()
        self.pending_auto_fix_text = None
        self.btn_quality_apply_fix.config(state="disabled")
        self.quality_status_var.set("Applied auto-fix suggestions to prompt")

    def _create_sidebar(self):
        """Create the sidebar with recent prompts and favorites."""
        # Header with title and toggle button
        header_frame = ttk.Frame(self.sidebar)
        header_frame.pack(fill=tk.X, padx=5, pady=5)

        title_label = ttk.Label(header_frame, text="📜 Recent", font=("Segoe UI", 10, "bold"))
        title_label.pack(side=tk.LEFT)

        toggle_btn = ttk.Button(header_frame, text="◀", width=3, command=self._toggle_sidebar)
        toggle_btn.pack(side=tk.RIGHT)
        self.sidebar_toggle_btn = toggle_btn

        # Search/filter box
        search_frame = ttk.Frame(self.sidebar)
        search_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        ttk.Label(search_frame, text="🔍").pack(side=tk.LEFT, padx=(0, 3))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter_history())
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Tags filter section
        tags_frame = ttk.Frame(self.sidebar)
        tags_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        ttk.Label(tags_frame, text="🏷️ Tags:", font=("", 9, "bold")).pack(anchor=tk.W)

        self.tags_filter_frame = ttk.Frame(tags_frame)
        self.tags_filter_frame.pack(fill=tk.X, pady=(2, 0))
        self._update_tag_filters()

        # Advanced Filters section
        adv_filters_frame = ttk.Frame(self.sidebar)
        adv_filters_frame.pack(fill=tk.X, padx=5, pady=(5, 5))

        ttk.Label(adv_filters_frame, text="🔧 Filters:", font=("", 9, "bold")).pack(anchor=tk.W)

        # Favorites only
        self.filter_favorites_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            adv_filters_frame,
            text="⭐ Favorites only",
            variable=self.filter_favorites_only,
            command=self._filter_history,
        ).pack(anchor=tk.W, pady=2)

        # Length filter
        length_frame = ttk.Frame(adv_filters_frame)
        length_frame.pack(fill=tk.X, pady=2)
        ttk.Label(length_frame, text="📏 Length:", font=("", 8)).pack(side=tk.LEFT)
        self.filter_length = tk.StringVar(value="all")
        length_combo = ttk.Combobox(
            length_frame,
            textvariable=self.filter_length,
            values=["all", "short (<100)", "medium (100-500)", "long (>500)"],
            state="readonly",
            width=15,
        )
        length_combo.pack(side=tk.LEFT, padx=(5, 0))
        length_combo.bind("<<ComboboxSelected>>", lambda e: self._filter_history())

        # Date range filter
        date_frame = ttk.Frame(adv_filters_frame)
        date_frame.pack(fill=tk.X, pady=2)
        ttk.Label(date_frame, text="📅 Date:", font=("", 8)).pack(side=tk.LEFT)
        self.filter_date_range = tk.StringVar(value="all")
        date_combo = ttk.Combobox(
            date_frame,
            textvariable=self.filter_date_range,
            values=["all", "today", "last 7 days", "last 30 days", "last 90 days"],
            state="readonly",
            width=15,
        )
        date_combo.pack(side=tk.LEFT, padx=(5, 0))
        date_combo.bind("<<ComboboxSelected>>", lambda e: self._filter_history())

        # Sort options
        sort_frame = ttk.Frame(adv_filters_frame)
        sort_frame.pack(fill=tk.X, pady=2)
        ttk.Label(sort_frame, text="↕️ Sort:", font=("", 8)).pack(side=tk.LEFT)
        self.filter_sort = tk.StringVar(value="date (newest)")
        sort_combo = ttk.Combobox(
            sort_frame,
            textvariable=self.filter_sort,
            values=[
                "date (newest)",
                "date (oldest)",
                "length (short)",
                "length (long)",
                "most used",
            ],
            state="readonly",
            width=15,
        )
        sort_combo.pack(side=tk.LEFT, padx=(5, 0))
        sort_combo.bind("<<ComboboxSelected>>", lambda e: self._filter_history())

        # Clear filters button
        ttk.Button(
            adv_filters_frame, text="🔄 Clear Filters", command=self._clear_all_filters
        ).pack(fill=tk.X, pady=(5, 0))

        # Analytics button
        ttk.Button(adv_filters_frame, text="📊 View Analytics", command=self._show_analytics).pack(
            fill=tk.X, pady=(2, 0)
        )

        # Export/Import section
        export_frame = ttk.LabelFrame(self.sidebar, text="📤 Backup & Restore", padding=5)
        export_frame.pack(fill=tk.X, padx=5, pady=(10, 5))

        export_btn_frame = ttk.Frame(export_frame)
        export_btn_frame.pack(fill=tk.X)

        ttk.Button(
            export_btn_frame, text="💾 Export All", command=self._export_data, width=15
        ).pack(side=tk.LEFT, padx=(0, 2))

        ttk.Button(export_btn_frame, text="📥 Import", command=self._import_data, width=15).pack(
            side=tk.LEFT, padx=(2, 0)
        )

        # Quick export options
        quick_export_frame = ttk.Frame(export_frame)
        quick_export_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(
            quick_export_frame,
            text="📋 Export History",
            command=lambda: self._export_data("history"),
            width=15,
        ).pack(side=tk.LEFT, padx=(0, 2))

        ttk.Button(
            quick_export_frame,
            text="🏷️ Export Tags",
            command=lambda: self._export_data("tags"),
            width=15,
        ).pack(side=tk.LEFT, padx=(2, 0))

        # Restore backup button
        ttk.Button(
            export_frame, text="♻️ Restore Backup", command=self._restore_backup, width=32
        ).pack(fill=tk.X, pady=(5, 0))

        # Snippets section
        snippets_label_frame = ttk.Frame(self.sidebar)
        snippets_label_frame.pack(fill=tk.X, padx=5, pady=(5, 2))

        ttk.Label(snippets_label_frame, text="✂️ Snippets:", font=("", 9, "bold")).pack(side=tk.LEFT)
        ttk.Button(snippets_label_frame, text="+", width=3, command=self._add_snippet).pack(
            side=tk.RIGHT
        )

        snippets_list_frame = ttk.Frame(self.sidebar)
        snippets_list_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        snippets_scroll = ttk.Scrollbar(snippets_list_frame)
        snippets_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.snippets_listbox = tk.Listbox(
            snippets_list_frame,
            yscrollcommand=snippets_scroll.set,
            selectmode=tk.SINGLE,
            height=4,
            activestyle="dotbox",
        )
        self.snippets_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        snippets_scroll.config(command=self.snippets_listbox.yview)

        self.snippets_listbox.bind("<Double-Button-1>", lambda e: self._insert_snippet())
        self.snippets_listbox.bind("<Return>", lambda e: self._insert_snippet())
        self.snippets_listbox.bind("<Button-3>", self._show_snippet_context_menu)

        self._refresh_snippets()

        # Listbox with scrollbar
        list_frame = ttk.Frame(self.sidebar)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.history_listbox = tk.Listbox(
            list_frame, yscrollcommand=scrollbar.set, selectmode=tk.SINGLE, activestyle="dotbox"
        )
        self.history_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.history_listbox.yview)

        # Event bindings
        self.history_listbox.bind("<Double-Button-1>", lambda e: self._load_prompt_from_history())
        self.history_listbox.bind("<Return>", lambda e: self._load_prompt_from_history())
        self.history_listbox.bind("<Delete>", lambda e: self._delete_history_item())
        self.history_listbox.bind("<Button-3>", self._show_history_context_menu)

        # Action buttons
        btn_frame = ttk.Frame(self.sidebar)
        btn_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        ttk.Button(btn_frame, text="🔄 Refresh", command=self._refresh_history).pack(
            fill=tk.X, pady=1
        )
        ttk.Button(btn_frame, text="🗑️ Clear All", command=self._clear_history).pack(
            fill=tk.X, pady=1
        )

        # Load initial history
        self._refresh_history()

    def _add_tab(self, title: str) -> tk.Text:
        frame = ttk.Frame(self.nb)
        self.nb.add(frame, text=title)
        bar = ttk.Frame(frame)
        bar.pack(fill=tk.X)
        txt = tk.Text(frame, wrap=tk.NONE)
        txt.pack(fill=tk.BOTH, expand=True)

        # Add syntax highlighting for JSON tabs
        if "JSON" in title:
            self._setup_json_highlighting(txt)

        btn_copy = ttk.Button(bar, text="📋 Copy", command=lambda t=txt: self._copy_text(t))
        btn_copy.pack(side=tk.LEFT, padx=2, pady=2)
        self._add_tooltip(btn_copy, f"Copy {title} to clipboard")
        if title in ("System Prompt", "User Prompt", "Plan", "Expanded Prompt"):
            ttk.Button(bar, text="Copy all", command=self._copy_all_texts).pack(
                side=tk.LEFT, padx=2, pady=2
            )
        if title == "IR JSON":
            ttk.Button(
                bar,
                text="Export JSON",
                command=lambda: self._export_text(self.txt_ir, default_ext=".json"),
            ).pack(side=tk.LEFT, padx=2, pady=2)
            ttk.Button(bar, text="Copy as cURL", command=self._copy_as_curl).pack(
                side=tk.LEFT, padx=2, pady=2
            )
        if title == "IR v2 JSON":
            ttk.Button(
                bar,
                text="Export JSON",
                command=lambda: self._export_text(self.txt_ir2, default_ext=".json"),
            ).pack(side=tk.LEFT, padx=2, pady=2)
            ttk.Button(bar, text="Copy as cURL", command=self._copy_as_curl).pack(
                side=tk.LEFT, padx=2, pady=2
            )
        if title == "Expanded Prompt":
            ttk.Button(
                bar, text="Export MD", command=lambda: self._export_markdown_combined()
            ).pack(side=tk.LEFT, padx=2, pady=2)
        if title == "Expanded Prompt":
            ttk.Label(bar, text="(Diagnostics appear here if enabled)", foreground="#666").pack(
                side=tk.RIGHT
            )
        return txt

    def _build_quality_tab(self, frame: ttk.Frame) -> None:
        header = ttk.Frame(frame, padding=8)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Prompt Quality Coach", font=("", 12, "bold")).pack(anchor=tk.W)

        stats = ttk.Frame(frame, padding=(8, 0))
        stats.pack(fill=tk.X)
        ttk.Label(stats, text="Overall Score:", font=("", 10, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        self.lbl_quality_total = ttk.Label(
            stats,
            textvariable=self.quality_total_var,
            font=("", 22, "bold"),
            foreground="#15803d",
        )
        self.lbl_quality_total.grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(stats, textvariable=self.quality_breakdown_var, foreground="#4b5563").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )

        btn_frame = ttk.Frame(frame, padding=8)
        btn_frame.pack(fill=tk.X)
        self.btn_quality_analyze = ttk.Button(
            btn_frame, text="🧮 Analyze Prompt", command=self._run_quality_check
        )
        self.btn_quality_analyze.pack(side=tk.LEFT)
        self._add_tooltip(self.btn_quality_analyze, "Compile and score the current prompt")
        self.btn_quality_auto_fix = ttk.Button(
            btn_frame, text="🪄 Auto-Fix Prompt", command=self._run_auto_fix
        )
        self.btn_quality_auto_fix.pack(side=tk.LEFT, padx=(6, 0))
        self._add_tooltip(self.btn_quality_auto_fix, "Suggest automatic fixes for low scores")
        self.btn_quality_apply_fix = ttk.Button(
            btn_frame, text="✅ Apply Auto-Fix", command=self._apply_auto_fix, state="disabled"
        )
        self.btn_quality_apply_fix.pack(side=tk.LEFT, padx=(6, 0))
        self._add_tooltip(self.btn_quality_apply_fix, "Replace the prompt with the suggested fixes")
        ttk.Label(btn_frame, textvariable=self.quality_status_var, foreground="#4b5563").pack(
            side=tk.RIGHT
        )

        reports = ttk.Frame(frame, padding=(8, 0))
        reports.pack(fill=tk.BOTH, expand=True)
        reports.columnconfigure(0, weight=1)
        reports.columnconfigure(1, weight=1)

        left = ttk.Frame(reports)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        ttk.Label(left, text="Quality Report", font=("", 10, "bold")).pack(anchor=tk.W)
        self.txt_quality_report = tk.Text(left, wrap=tk.WORD, height=16)
        self.txt_quality_report.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.txt_quality_report.insert("1.0", self._quality_report_placeholder)
        self.txt_quality_report.config(state=tk.DISABLED)

        right = ttk.Frame(reports)
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        ttk.Label(right, text="Auto-Fix Preview", font=("", 10, "bold")).pack(anchor=tk.W)
        self.txt_quality_fix = tk.Text(right, wrap=tk.WORD, height=16)
        self.txt_quality_fix.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.txt_quality_fix.insert("1.0", self._quality_fix_placeholder)
        self.txt_quality_fix.config(state=tk.DISABLED)

    def _update_quality_text(self, widget: tk.Text, text: str) -> None:
        try:
            widget.config(state=tk.NORMAL)
            widget.delete("1.0", tk.END)
            widget.insert("1.0", text)
            widget.config(state=tk.DISABLED)
        except Exception:
            pass

    def _focus_quality_tab(self) -> None:
        try:
            for i in range(self.nb.index("end")):
                if self.nb.tab(i, "text") == "Quality Coach":
                    self.nb.select(i)
                    break
        except Exception:
            pass

    def _set_quality_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for btn in (self.btn_quality_analyze, self.btn_quality_auto_fix):
            try:
                btn.config(state=state)
            except Exception:
                pass
        if busy:
            try:
                self.btn_quality_apply_fix.config(state="disabled")
            except Exception:
                pass
        else:
            apply_state = "normal" if self.pending_auto_fix_text else "disabled"
            try:
                self.btn_quality_apply_fix.config(state=apply_state)
            except Exception:
                pass

    def _format_quality_report(self, result) -> str:
        lines = [
            f"Total Score: {result.score.total:.1f}/100",
            (
                "Clarity: {0:.1f} | Specificity: {1:.1f} | Completeness: {2:.1f} | Consistency: {3:.1f}".format(
                    result.score.clarity,
                    result.score.specificity,
                    result.score.completeness,
                    result.score.consistency,
                )
            ),
            "",
            f"Issues ({len(result.issues)} total):",
        ]
        if result.issues:
            for issue in result.issues:
                lines.append(
                    f"- [{issue.severity.upper()} / {issue.category}] {issue.message}\n  Suggestion: {issue.suggestion}"
                )
        else:
            lines.append("- None 🎉")

        if getattr(result, "strengths", None):
            lines.append("\nStrengths:")
            for strength in result.strengths:
                lines.append(f"✓ {strength}")

        lines.append(
            f"\nSummary: {result.errors} errors, {result.warnings} warnings, {result.info} info items"
        )
        return "\n".join(lines)

    # Theme
    def toggle_theme(self):
        self.apply_theme("dark" if self.current_theme == "light" else "light")
        self._save_settings()

    def apply_theme(self, theme: str):
        self.current_theme = theme
        dark = theme == "dark"

        # Modern color palette
        if dark:
            bg = "#1a1a1a"  # Darker background
            fg = "#e4e4e7"  # Softer white
            panel = "#27272a"  # Modern dark panel
            accent = "#3b82f6"  # Modern blue
            accent_hover = "#2563eb"  # Darker blue on hover
            border = "#3f3f46"
            text_bg = "#18181b"
        else:
            bg = "#fafafa"  # Softer white
            fg = "#18181b"  # Almost black
            panel = "#f4f4f5"  # Light gray
            accent = "#3b82f6"  # Vibrant blue
            accent_hover = "#2563eb"
            border = "#e4e4e7"
            text_bg = "#ffffff"

        self.root.configure(bg=bg)
        style = ttk.Style()
        try:
            if dark:
                style.theme_use("clam")
            else:
                style.theme_use("default")
        except Exception:
            pass

        # Modern styling with better contrast
        for elem in ["TFrame", "TLabel", "TCheckbutton"]:
            style.configure(elem, background=bg, foreground=fg)

        # Notebook tabs with modern look
        style.configure("TNotebook", background=bg, foreground=fg, borderwidth=0)
        style.configure(
            "TNotebook.Tab", background=panel, foreground=fg, padding=(12, 8), borderwidth=0
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", accent), ("active", accent_hover)],
            foreground=[("selected", "#ffffff"), ("active", "#ffffff")],
        )

        # Modern buttons
        style.configure("TButton", padding=(10, 6), borderwidth=1, relief="flat")
        style.map(
            "TButton", background=[("active", accent_hover)], foreground=[("active", "#ffffff")]
        )

        # Progress bar styling
        style.configure(
            "TProgressbar", background=accent, troughcolor=panel, borderwidth=0, thickness=4
        )

        # Treeview (constraints) with better borders
        style.configure(
            "Treeview",
            background=text_bg,
            fieldbackground=text_bg,
            foreground=fg,
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "Treeview.Heading", background=panel, foreground=fg, relief="flat", borderwidth=1
        )
        style.map("Treeview.Heading", background=[("active", accent_hover)])

        # Chips label style with gradient effect (simulated)
        style.configure(
            "Chip.TLabel",
            background=accent,
            foreground="#ffffff",
            padding=(8, 4),
            borderwidth=0,
            relief="flat",
        )
        for t in [
            self.txt_prompt,
            getattr(self, "txt_context", None),
            self.txt_system,
            self.txt_user,
            self.txt_plan,
            self.txt_expanded,
            self.txt_ir,
            self.txt_ir2,
            self.txt_trace,
            getattr(self, "txt_llm", None),
            getattr(self, "txt_diff", None),
            getattr(self, "txt_quality_report", None),
            getattr(self, "txt_quality_fix", None),
        ]:
            if t is None:
                continue
            t.configure(
                bg=text_bg,
                fg=fg,
                insertbackground=accent,
                relief=tk.SOLID,
                borderwidth=1,
                highlightthickness=0,
                highlightbackground=border,
                font=("Consolas", 10),
            )

        # Update theme button
        self.btn_theme.config(text="☀️ Light" if dark else "🌙 Dark")

        # Re-apply JSON highlighting if tabs exist
        try:
            if hasattr(self, "txt_ir") and self.txt_ir.get("1.0", tk.END).strip():
                self._apply_json_highlighting(self.txt_ir, self.txt_ir.get("1.0", tk.END))
            if hasattr(self, "txt_ir2") and self.txt_ir2.get("1.0", tk.END).strip():
                self._apply_json_highlighting(self.txt_ir2, self.txt_ir2.get("1.0", tk.END))
        except Exception:
            pass

    # Settings persistence
    def _load_settings(self):  # pragma: no cover - simple IO
        data = {}
        try:
            if self.config_path.exists():
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        try:
            self.command_palette_favorites = get_saved_palette_favorites_list(data)
        except Exception:
            self.command_palette_favorites = []
        # Theme
        theme = data.get("theme")
        if theme in ("light", "dark"):
            self.current_theme = theme

        # UI Customization
        self.accent_color = data.get("accent_color", "#3b82f6")
        self.font_size = data.get("font_size", "medium")
        self.view_mode = data.get("view_mode", "comfortable")

        # Variables
        try:
            if "diagnostics" in data:
                self.var_diag.set(bool(data.get("diagnostics")))
            if "trace" in data:
                self.var_trace.set(bool(data.get("trace")))
            if "use_expanded" in data:
                self.var_openai_expanded.set(bool(data.get("use_expanded")))
            if "render_v2_emitters" in data:
                self.var_render_v2.set(bool(data.get("render_v2_emitters")))
            if "only_live_debug" in data:
                self.var_only_live_debug.set(bool(data.get("only_live_debug")))
            if "wrap" in data:
                self.var_wrap.set(bool(data.get("wrap")))
            if "auto_generate_example" in data:
                try:
                    getattr(self, "var_autogen_example", tk.BooleanVar(value=False)).set(
                        bool(data.get("auto_generate_example"))
                    )
                except Exception:
                    pass
            if "min_priority" in data:
                try:
                    val = data.get("min_priority")
                    self.var_min_priority.set(str(val) if val is not None else "Any")
                except Exception:
                    pass
            if "model" in data:
                val = str(data.get("model") or "gpt-4o-mini")
                # Only set if allowed in readonly combobox values
                try:
                    allowed = list(self.cmb_model["values"])  # type: ignore[attr-defined]
                except Exception:
                    allowed = []
                if not allowed or val in allowed:
                    self.var_model.set(val)
            provider = data.get("llm_provider")
            if provider in ("OpenAI", "Local HTTP"):
                self.var_llm_provider.set(provider)
            if "local_endpoint" in data and data.get("local_endpoint"):
                self.var_local_endpoint.set(str(data.get("local_endpoint")))
            if "local_api_key" in data:
                self.var_local_api_key.set(str(data.get("local_api_key") or ""))
            if "user_level" in data:
                lvl = str(data.get("user_level") or "intermediate")
                if lvl in ("beginner", "intermediate", "advanced"):
                    self.var_user_level.set(lvl)
            if "task_type" in data:
                tt = str(data.get("task_type") or "general")
                self.var_task_type.set(tt)
            # RAG settings
            if "rag_db_path" in data:
                self.rag_db_path = data.get("rag_db_path")
            if "rag_embed_dim" in data:
                self.rag_embed_dim = int(data.get("rag_embed_dim") or 64)
            if "rag_method" in data:
                method = data.get("rag_method")
                if method in ("fts", "embed", "hybrid"):
                    self.rag_method = method
        except Exception:
            pass
        # Geometry
        if geo := data.get("geometry"):
            try:
                self.root.geometry(str(geo))
            except Exception:
                pass
        # Selected tab
        try:
            idx = int(data.get("selected_tab", -1))
            if idx >= 0:
                self.nb.select(idx)
        except Exception:
            pass
        try:
            self._update_llm_controls()
        except Exception:
            pass

    def _save_settings(self):  # pragma: no cover - simple IO
        try:
            try:
                selected_idx = self.nb.index(self.nb.select())
            except Exception:
                selected_idx = 0
            payload = {
                "theme": self.current_theme,
                "accent_color": self.accent_color,
                "font_size": self.font_size,
                "view_mode": self.view_mode,
                "diagnostics": bool(self.var_diag.get()),
                "trace": bool(self.var_trace.get()),
                "use_expanded": bool(self.var_openai_expanded.get()),
                "render_v2_emitters": bool(
                    getattr(self, "var_render_v2", tk.BooleanVar(value=False)).get()
                ),
                "only_live_debug": bool(
                    getattr(self, "var_only_live_debug", tk.BooleanVar(value=False)).get()
                ),
                "wrap": bool(getattr(self, "var_wrap", tk.BooleanVar(value=False)).get()),
                "auto_generate_example": bool(
                    getattr(self, "var_autogen_example", tk.BooleanVar(value=False)).get()
                ),
                "min_priority": getattr(self, "var_min_priority", tk.StringVar(value="Any")).get(),
                "model": (self.var_model.get() or "gpt-4o-mini").strip(),
                "llm_provider": (self.var_llm_provider.get() or "OpenAI").strip(),
                "local_endpoint": (self.var_local_endpoint.get() or "").strip(),
                "local_api_key": (self.var_local_api_key.get() or "").strip(),
                "user_level": (self.var_user_level.get() or "intermediate").strip(),
                "task_type": (self.var_task_type.get() or "general").strip(),
                "rag_db_path": self.rag_db_path,
                "rag_embed_dim": self.rag_embed_dim,
                "rag_method": self.rag_method,
                "geometry": self.root.winfo_geometry(),
                "selected_tab": selected_idx,
                "command_palette_favorites": list(self.command_palette_favorites),
            }
            original_env = os.environ.get(CONFIG_ENV_VAR)
            try:
                os.environ[CONFIG_ENV_VAR] = str(self.config_path)
                persist_palette_favorites(self.command_palette_favorites, base_config=payload)
            finally:
                if original_env is None:
                    os.environ.pop(CONFIG_ENV_VAR, None)
                else:
                    os.environ[CONFIG_ENV_VAR] = original_env
        except Exception:
            pass

    def _on_close(self):  # pragma: no cover - UI callback
        self._save_settings()
        # Auto-backup before closing
        try:
            self._auto_backup()
        except Exception as e:
            print(f"Auto-backup failed: {e}")
        try:
            self.root.destroy()
        except Exception:
            pass

    # Actions
    def _copy_text(self, widget: tk.Text):
        data = widget.get("1.0", tk.END).strip()
        if not data:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(data)
        self.status_var.set("Copied")

    def on_clear(self):
        for t in [
            self.txt_system,
            self.txt_user,
            self.txt_plan,
            self.txt_expanded,
            self.txt_ir,
            self.txt_ir2,
            self.txt_trace,
            getattr(self, "txt_llm", None),
            getattr(self, "txt_diff", None),
            getattr(self, "txt_quality_report", None),
            getattr(self, "txt_quality_fix", None),
        ]:
            if t is None:
                continue
            t.delete("1.0", tk.END)
        if hasattr(self, "txt_quality_report"):
            self._update_quality_text(self.txt_quality_report, self._quality_report_placeholder)
        if hasattr(self, "txt_quality_fix"):
            self._update_quality_text(self.txt_quality_fix, self._quality_fix_placeholder)
        self.summary_var.set("")
        self.status_var.set("Cleared")
        self.quality_total_var.set("—")
        self.quality_breakdown_var.set("Analyze the prompt to see detailed scores.")
        self.quality_status_var.set("Ready")
        self.pending_auto_fix_text = None
        try:
            self.btn_quality_apply_fix.config(state="disabled")
        except Exception:
            pass
        # Clear chips and constraints
        for w in self.chips_container.winfo_children():
            w.destroy()
        if hasattr(self, "tree_constraints"):
            for i in self.tree_constraints.get_children():
                self.tree_constraints.delete(i)

    def on_show_schema(self):
        try:
            text = Path("schema/ir.schema.json").read_text(encoding="utf-8")
        except FileNotFoundError:
            messagebox.showerror("Schema", "schema/ir.schema.json not found")
            return
        win = tk.Toplevel(self.root)
        win.title("IR JSON Schema")
        win.geometry("800x600")
        txt = tk.Text(win, wrap=tk.NONE)
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert(tk.END, text)
        txt.config(state=tk.DISABLED)

    def _insert_snippets_into_context(self, snippets: list[str]):
        current_context = self.txt_context.get("1.0", tk.END).strip()
        separator = "\n---\n" if current_context else ""
        new_context = current_context + separator + "\n".join(snippets)
        self.txt_context.delete("1.0", tk.END)
        self.txt_context.insert("1.0", new_context)
        self.var_include_context.set(True)

    def _insert_pin_into_context(self, pin_entry):
        snippet = getattr(pin_entry, "snippet", "")
        if not snippet.strip():
            return
        label = getattr(pin_entry, "label", "Pinned snippet")
        display = f"[{label}]\n{snippet}\n"
        self._insert_snippets_into_context([display])
        self.status_var.set(f"📌 Inserted '{label}' into context")

    def _show_rag_pins(self):
        try:
            if not self.rag_history_store.pins:
                messagebox.showinfo("Pins", "No pinned snippets yet. Use RAG search to add pins.")
                return
            win = tk.Toplevel(self.root)
            win.title("📌 Pinned Snippets")
            win.geometry("500x400")
            win.transient(self.root)

            tree = ttk.Treeview(
                win,
                columns=("label", "source", "time"),
                show="headings",
                selectmode="browse",
            )
            for col, width in ("label", 200), ("source", 120), ("time", 100):
                tree.heading(col, text=col.title())
                tree.column(col, width=width, anchor=tk.W)
            tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            def refresh():
                tree.delete(*tree.get_children())
                for idx, entry in self.rag_history_store.iter_pins():
                    tree.insert(
                        "",
                        tk.END,
                        iid=f"p{idx}",
                        values=(
                            entry.label,
                            entry.source or "context",
                            self.rag_history_store.format_timestamp(entry.created_at),
                        ),
                    )

            def get_selected():
                sel = tree.selection()
                if not sel:
                    return None
                idx = int(sel[0][1:])
                if 0 <= idx < len(self.rag_history_store.pins):
                    return idx, self.rag_history_store.pins[idx]
                return None

            def insert_sel():
                entry = get_selected()
                if not entry:
                    messagebox.showinfo("Pins", "Select a pinned snippet first.")
                    return
                _idx, pin_entry = entry
                self._insert_pin_into_context(pin_entry)

            def delete_sel():
                entry = get_selected()
                if not entry:
                    return
                idx, _ = entry
                self.rag_history_store.delete_pin(idx)
                refresh()

            btns = ttk.Frame(win)
            btns.pack(fill=tk.X, padx=10, pady=(0, 10))
            ttk.Button(btns, text="➕ Insert", command=insert_sel).pack(side=tk.LEFT, padx=4)
            ttk.Button(btns, text="🗑️ Remove", command=delete_sel).pack(side=tk.LEFT, padx=4)
            ttk.Button(btns, text="❌ Close", command=win.destroy).pack(side=tk.RIGHT, padx=4)

            tree.bind("<Double-1>", lambda _e: insert_sel())
            refresh()
        except Exception as exc:
            messagebox.showerror("Pins", f"Failed to open pins: {exc}")

    def _refresh_context_presets_menu(self):
        try:
            if not self.context_preset_menu:
                return
            self.context_preset_menu.delete(0, tk.END)
            names = self.context_presets_store.list_names()
            if names:
                for name in names:
                    self.context_preset_menu.add_command(
                        label=name,
                        command=lambda n=name: self._apply_context_preset(n),
                    )
            else:
                self.context_preset_menu.add_command(label="(No presets yet)", state=tk.DISABLED)
            self.context_preset_menu.add_separator()
            self.context_preset_menu.add_command(
                label="💾 Save current…", command=self._prompt_save_context_preset
            )
            self.context_preset_menu.add_command(
                label="🛠️ Manage presets…", command=self._show_context_presets_dialog
            )
        except Exception:
            pass

    def _apply_context_preset(self, name: str):
        preset = self.context_presets_store.get(name)
        if not preset:
            messagebox.showerror("Context Presets", f"Preset '{name}' not found.")
            return
        self.txt_context.delete("1.0", tk.END)
        self.txt_context.insert("1.0", preset.content)
        self.var_include_context.set(True)
        self.status_var.set(f"📚 Loaded preset '{name}'")

    def _prompt_save_context_preset(self):
        content = self.txt_context.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("Context Presets", "Enter context text before saving a preset.")
            return
        default = f"Preset {len(self.context_presets_store.presets) + 1}"
        name = simpledialog.askstring(
            "Save Context Preset",
            "Preset name:",
            parent=self.root,
            initialvalue=default,
        )
        if not name:
            return
        self.context_presets_store.upsert(name, content)
        self._refresh_context_presets_menu()
        self.status_var.set(f"💾 Saved preset '{name}'")

    def _show_context_presets_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Context Presets")
        dialog.geometry("500x420")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        listbox = tk.Listbox(frame, height=10)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(frame, command=listbox.yview)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        listbox.config(yscrollcommand=scrollbar.set)

        preview = tk.Text(dialog, height=10, wrap=tk.WORD)
        preview.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        preview.config(state=tk.DISABLED)

        btns = ttk.Frame(dialog)
        btns.pack(fill=tk.X, padx=10, pady=(0, 10))

        def refresh_list():
            listbox.delete(0, tk.END)
            for name in self.context_presets_store.list_names():
                listbox.insert(tk.END, name)
            update_preview()

        def get_selected_name():
            selection = listbox.curselection()
            if not selection:
                return None
            return listbox.get(selection[0])

        def update_preview(_event=None):
            try:
                selection = get_selected_name()
                preset = self.context_presets_store.get(selection) if selection else None
                preview.config(state=tk.NORMAL)
                preview.delete("1.0", tk.END)
                if preset:
                    preview.insert("1.0", preset.content)
                preview.config(state=tk.DISABLED)
            except Exception:
                pass

        def apply_selected():
            name = get_selected_name()
            if not name:
                messagebox.showinfo("Context Presets", "Select a preset to load.")
                return
            self._apply_context_preset(name)
            dialog.destroy()

        def rename_selected():
            name = get_selected_name()
            if not name:
                return
            new_name = simpledialog.askstring(
                "Rename Preset", "New name:", parent=dialog, initialvalue=name
            )
            if not new_name:
                return
            if self.context_presets_store.rename(name, new_name):
                self._refresh_context_presets_menu()
                refresh_list()

        def delete_selected():
            name = get_selected_name()
            if not name:
                return
            if messagebox.askyesno("Delete Preset", f"Delete '{name}'?"):
                self.context_presets_store.delete(name)
                self._refresh_context_presets_menu()
                refresh_list()

        ttk.Button(btns, text="Load", command=apply_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Rename", command=rename_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Delete", command=delete_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=4)

        listbox.bind("<<ListboxSelect>>", update_preview)
        refresh_list()

    def _show_rag_search(self):
        """Show RAG document search dialog with recents and pins."""
        try:
            search_window = tk.Toplevel(self.root)
            search_window.title("🔍 Search Documents (RAG)")
            search_window.geometry("1000x720")
            search_window.transient(self.root)

            header = ttk.Frame(search_window, padding=10)
            header.pack(fill=tk.X)
            ttk.Label(header, text="🔍 Document Search", font=("", 12, "bold")).pack(anchor=tk.W)
            ttk.Label(
                header,
                text="Search indexed documents, re-run saved queries, and manage pinned snippets",
                foreground="#666",
            ).pack(anchor=tk.W)

            controls = ttk.Frame(search_window, padding=10)
            controls.pack(fill=tk.X)

            ttk.Label(controls, text="Query:").pack(side=tk.LEFT, padx=(0, 5))
            query_var = tk.StringVar()
            query_entry = ttk.Entry(controls, textvariable=query_var, width=40)
            query_entry.pack(side=tk.LEFT, padx=(0, 10))
            query_entry.focus_set()

            ttk.Label(controls, text="Method:").pack(side=tk.LEFT, padx=(10, 5))
            method_var = tk.StringVar(value=self.rag_method)
            method_combo = ttk.Combobox(
                controls,
                textvariable=method_var,
                width=10,
                state="readonly",
                values=("fts", "embed", "hybrid"),
            )
            method_combo.pack(side=tk.LEFT, padx=(0, 10))

            ttk.Label(controls, text="Results:").pack(side=tk.LEFT, padx=(10, 5))
            k_var = tk.IntVar(value=10)
            k_spin = ttk.Spinbox(controls, from_=1, to=50, textvariable=k_var, width=8)
            k_spin.pack(side=tk.LEFT, padx=(0, 10))

            btn_search = ttk.Button(controls, text="🔍 Search")
            btn_search.pack(side=tk.LEFT, padx=5)

            body = ttk.PanedWindow(search_window, orient=tk.HORIZONTAL)
            body.pack(fill=tk.BOTH, expand=True)

            left_panel = ttk.Frame(body, padding=10)
            body.add(left_panel, weight=0)
            right_panel = ttk.Frame(body)
            body.add(right_panel, weight=1)

            # Left: history and pins
            history_frame = ttk.LabelFrame(left_panel, text="🕘 Recent queries", padding=6)
            history_frame.pack(fill=tk.BOTH, expand=True)

            history_tree = ttk.Treeview(
                history_frame,
                columns=("query", "method", "time"),
                show="headings",
                height=8,
                selectmode="browse",
            )
            for col, width in ("query", 160), ("method", 70), ("time", 90):
                history_tree.heading(col, text=col.title())
                history_tree.column(col, width=width, anchor=tk.W)
            history_tree.pack(fill=tk.BOTH, expand=True)

            history_btns = ttk.Frame(history_frame)
            history_btns.pack(fill=tk.X, pady=(4, 0))

            # Pins
            pins_frame = ttk.LabelFrame(left_panel, text="📌 Pinned snippets", padding=6)
            pins_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

            pins_tree = ttk.Treeview(
                pins_frame,
                columns=("label", "source", "time"),
                show="headings",
                height=6,
                selectmode="browse",
            )
            for col, width in ("label", 140), ("source", 80), ("time", 90):
                pins_tree.heading(col, text=col.title())
                pins_tree.column(col, width=width, anchor=tk.W)
            pins_tree.pack(fill=tk.BOTH, expand=True)

            pins_btns = ttk.Frame(pins_frame)
            pins_btns.pack(fill=tk.X, pady=(4, 0))

            # Right: results
            results_label = ttk.Label(right_panel, text="No results yet", padding=(10, 5))
            results_label.pack(anchor=tk.W)
            selection_info_var = tk.StringVar(value="Select snippets to preview size")
            selection_info_lbl = ttk.Label(
                right_panel, textvariable=selection_info_var, padding=(10, 0), foreground="#555"
            )
            selection_info_lbl.pack(anchor=tk.W)

            results_frame = ttk.Frame(right_panel, padding=10)
            results_frame.pack(fill=tk.BOTH, expand=True)

            columns = ("file", "chunk", "score", "snippet")
            results_tree = ttk.Treeview(
                results_frame, columns=columns, show="headings", selectmode="extended"
            )
            results_tree.heading("file", text="File")
            results_tree.heading("chunk", text="Chunk")
            results_tree.heading("score", text="Score")
            results_tree.heading("snippet", text="Snippet")

            results_tree.column("file", width=150, anchor=tk.W)
            results_tree.column("chunk", width=80, anchor=tk.CENTER)
            results_tree.column("score", width=80, anchor=tk.CENTER)
            results_tree.column("snippet", width=500, anchor=tk.W)

            results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=results_tree.yview)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            results_tree.configure(yscrollcommand=scrollbar.set)

            actions = ttk.Frame(right_panel, padding=10)
            actions.pack(fill=tk.X)
            compression_var = tk.BooleanVar(value=False)
            compression_limit_var = tk.IntVar(value=600)

            def refresh_history():
                history_tree.delete(*history_tree.get_children())
                for idx, entry in self.rag_history_store.iter_queries():
                    display = entry.query[:40] + ("…" if len(entry.query) > 40 else "")
                    history_tree.insert(
                        "",
                        tk.END,
                        iid=f"q{idx}",
                        values=(
                            display,
                            entry.method,
                            self.rag_history_store.format_timestamp(entry.timestamp),
                        ),
                    )

            def refresh_pins():
                pins_tree.delete(*pins_tree.get_children())
                for idx, entry in self.rag_history_store.iter_pins():
                    pins_tree.insert(
                        "",
                        tk.END,
                        iid=f"p{idx}",
                        values=(
                            entry.label,
                            entry.source or "context",
                            self.rag_history_store.format_timestamp(entry.created_at),
                        ),
                    )

            def get_history_entry():
                sel = history_tree.selection()
                if not sel:
                    return None
                idx = int(sel[0][1:])
                if 0 <= idx < len(self.rag_history_store.queries):
                    return idx, self.rag_history_store.queries[idx]
                return None

            def get_pin_entry():
                sel = pins_tree.selection()
                if not sel:
                    return None
                idx = int(sel[0][1:])
                if 0 <= idx < len(self.rag_history_store.pins):
                    return idx, self.rag_history_store.pins[idx]
                return None

            def _compression_limit() -> int:
                try:
                    val = int(compression_limit_var.get())
                except Exception:
                    val = 600
                return max(120, min(2000, val))

            def _get_snippet_from_item(item_id: str) -> str:
                values = results_tree.item(item_id, "values")
                return values[3] if len(values) > 3 else ""

            def update_selection_stats(*_args):
                selected = results_tree.selection()
                if not selected:
                    selection_info_var.set("Select snippets to preview size")
                    return
                total_chars = 0
                total_tokens = 0
                compressed_tokens = 0
                limit = _compression_limit()
                use_compress = bool(compression_var.get())
                for item_id in selected:
                    snippet = _get_snippet_from_item(item_id)
                    total_chars += len(snippet)
                    tokens = estimate_tokens(snippet)
                    total_tokens += tokens
                    if use_compress:
                        compressed_tokens += estimate_tokens(
                            compress_text_block(snippet, max_chars=limit)
                        )
                msg = f"{len(selected)} snippet(s) • ~{total_tokens} tokens • {total_chars} chars"
                if use_compress:
                    msg += f" → ~{compressed_tokens} tokens after summarize"
                selection_info_var.set(msg)

            def do_search():
                query = query_var.get().strip()
                if not query:
                    messagebox.showwarning("Search", "Enter a search query first.")
                    return

                method = method_var.get()
                k = k_var.get()
                self.rag_method = method
                self._save_settings()
                self.status_var.set(f"RAG: searching ({method})...")

                try:
                    search_kwargs = {"k": k, "db_path": self.rag_db_path}
                    if method == "fts":
                        results = search(query, **search_kwargs)
                    elif method == "embed":
                        results = search_embed(query, embed_dim=self.rag_embed_dim, **search_kwargs)
                    else:
                        results = search_hybrid(
                            query, embed_dim=self.rag_embed_dim, **search_kwargs
                        )

                    for item in results_tree.get_children():
                        results_tree.delete(item)

                    for r in results:
                        path = r.get("path", "")
                        snippet = r.get("snippet", "")
                        score = r.get("score", 0.0)
                        chunk_idx = r.get("chunk_index", 0)
                        display_path = Path(path).name if path else "unknown"
                        results_tree.insert(
                            "",
                            tk.END,
                            values=(display_path, f"chunk {chunk_idx}", f"{score:.3f}", snippet),
                        )

                    self.rag_history_store.add_query(query, method, k)
                    refresh_history()
                    results_label.config(text=f"Found {len(results)} result(s)")
                    self.status_var.set(f"RAG: {len(results)} results")

                except Exception as e:
                    messagebox.showerror("Search Error", f"Failed to search: {e}")
                    self.status_var.set("RAG: error")

            btn_search.config(command=do_search)

            def rerun_selected():
                entry = get_history_entry()
                if not entry:
                    messagebox.showinfo("RAG", "Select a saved query first.")
                    return
                _idx, query_entry_data = entry
                query_var.set(query_entry_data.query)
                method_var.set(query_entry_data.method)
                k_var.set(query_entry_data.k)
                do_search()

            def delete_history():
                entry = get_history_entry()
                if not entry:
                    return
                idx, _ = entry
                self.rag_history_store.delete_query(idx)
                refresh_history()

            def clear_history():
                self.rag_history_store.clear_queries()
                refresh_history()

            def add_to_context():
                selected = results_tree.selection()
                if not selected:
                    messagebox.showwarning("Selection", "Select one or more results first.")
                    return
                snippets = []
                for item_id in selected:
                    values = results_tree.item(item_id, "values")
                    snippet_text = values[3] if len(values) > 3 else ""
                    if bool(compression_var.get()) and snippet_text:
                        snippet_text = compress_text_block(
                            snippet_text, max_chars=_compression_limit()
                        )
                    file_name = values[0] if len(values) > 0 else ""
                    chunk_info = values[1] if len(values) > 1 else ""
                    snippets.append(f"[{file_name} {chunk_info}]\n{snippet_text}\n")
                if snippets:
                    self._insert_snippets_into_context(snippets)
                    search_window.destroy()
                    note = " (summarized)" if compression_var.get() else ""
                    self.status_var.set(f"✅ Added {len(selected)} snippet(s){note} to context")

            def pin_selected():
                selected = results_tree.selection()
                if not selected:
                    messagebox.showwarning("Pins", "Select at least one snippet to pin.")
                    return
                count = 0
                for item_id in selected:
                    values = results_tree.item(item_id, "values")
                    snippet_text = values[3] if len(values) > 3 else ""
                    label = values[0] if len(values) > 0 else "Snippet"
                    source = f"{values[0]} {values[1]}" if len(values) > 1 else values[0]
                    if snippet_text.strip():
                        self.rag_history_store.add_pin(label, snippet_text, source)
                        count += 1
                if count:
                    refresh_pins()
                    self.status_var.set(f"📌 Added {count} snippet(s) to pins")

            def insert_pin():
                entry = get_pin_entry()
                if not entry:
                    messagebox.showinfo("Pins", "Select a pinned snippet first.")
                    return
                _idx, pin_data = entry
                self._insert_pin_into_context(pin_data)

            def delete_pin():
                entry = get_pin_entry()
                if not entry:
                    return
                idx, _ = entry
                self.rag_history_store.delete_pin(idx)
                refresh_pins()

            def clear_pins():
                self.rag_history_store.clear_pins()
                refresh_pins()

            ttk.Button(history_btns, text="▶️ Run", command=rerun_selected).pack(
                side=tk.LEFT, padx=2
            )
            ttk.Button(history_btns, text="🗑️ Remove", command=delete_history).pack(
                side=tk.LEFT, padx=2
            )
            ttk.Button(history_btns, text="🧹 Clear", command=clear_history).pack(
                side=tk.LEFT, padx=2
            )

            ttk.Button(pins_btns, text="➕ Insert", command=insert_pin).pack(side=tk.LEFT, padx=2)
            ttk.Button(pins_btns, text="🗑️ Remove", command=delete_pin).pack(side=tk.LEFT, padx=2)
            ttk.Button(pins_btns, text="🧹 Clear", command=clear_pins).pack(side=tk.LEFT, padx=2)

            ttk.Button(actions, text="➕ Add Selected to Context", command=add_to_context).pack(
                side=tk.LEFT, padx=5
            )
            ttk.Checkbutton(
                actions,
                text="Summarize before insert",
                variable=compression_var,
            ).pack(side=tk.LEFT, padx=5)
            ttk.Label(actions, text="Max chars:").pack(side=tk.LEFT)
            ttk.Spinbox(
                actions,
                from_=120,
                to=2000,
                increment=40,
                textvariable=compression_limit_var,
                width=6,
            ).pack(side=tk.LEFT, padx=(0, 8))
            ttk.Button(actions, text="📌 Pin Selected", command=pin_selected).pack(
                side=tk.LEFT, padx=5
            )
            ttk.Button(actions, text="❌ Close", command=search_window.destroy).pack(
                side=tk.LEFT, padx=5
            )

            history_tree.bind("<Double-1>", lambda _e: rerun_selected())
            pins_tree.bind("<Double-1>", lambda _e: insert_pin())
            query_entry.bind("<Return>", lambda e: do_search())
            results_tree.bind("<<TreeviewSelect>>", lambda _e: update_selection_stats())
            compression_var.trace_add("write", update_selection_stats)
            compression_limit_var.trace_add("write", update_selection_stats)

            refresh_history()
            refresh_pins()
            update_selection_stats()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open RAG search: {e}")

    def on_generate(self):
        prompt = self.txt_prompt.get("1.0", tk.END).strip()
        if not prompt:
            messagebox.showwarning("Prompt", "Enter a prompt text first.")
            return

        # Save to history
        self._save_to_history(prompt)

        # Start progress animation
        self.is_generating = True
        self.progress_bar.pack(fill=tk.X, pady=2)
        self.progress_bar.start(10)
        self.btn_generate.config(state="disabled")
        self.status_var.set("⚡ Generating...")

        self.root.after(30, lambda: self._generate_core(prompt))

    def _update_llm_controls(self) -> None:
        provider = getattr(self, "var_llm_provider", tk.StringVar(value="OpenAI")).get()
        is_openai = provider == "OpenAI"
        model_choices = self._openai_models if is_openai else self._local_model_suggestions
        try:
            self.cmb_model.configure(values=model_choices)
        except Exception:
            pass
        if is_openai and self.var_model.get() not in model_choices:
            self.var_model.set(self._openai_models[0])
        elif not is_openai and not self.var_model.get():
            self.var_model.set(model_choices[0])
        entry_state = "disabled" if is_openai else "normal"
        for entry in getattr(self, "_local_entries", []):
            try:
                entry.config(state=entry_state)
            except Exception:
                pass
        btn_label = "🤖 Send to OpenAI" if is_openai else "🖥️ Send to Local LLM"
        tooltip = (
            "Send compiled prompt directly to OpenAI API"
            if is_openai
            else "Send prompt to a local HTTP endpoint (Ollama, LM Studio, etc.)"
        )
        try:
            self.btn_send_llm.config(text=btn_label)
            self._add_tooltip(self.btn_send_llm, tooltip)
        except Exception:
            pass

    def _prepare_llm_messages(self, prompt: str) -> tuple[str, str, object]:
        ir = optimize_ir(compile_text(prompt))
        use_expanded = bool(self.var_openai_expanded.get())
        diagnostics = bool(self.var_diag.get()) if use_expanded else False
        system = ""
        user = ""
        ir2 = None
        if bool(self.var_render_v2.get()):
            try:
                ir2 = compile_text_v2(prompt)
            except Exception:
                ir2 = None
        if ir2 is not None:
            system = emit_system_prompt_v2(ir2)
            if use_expanded:
                user = emit_expanded_prompt_v2(ir2, diagnostics=diagnostics)
            else:
                user = emit_user_prompt_v2(ir2)
        else:
            system = emit_system_prompt(ir)
            if use_expanded:
                user = emit_expanded_prompt(ir, diagnostics=diagnostics)
            else:
                user = emit_user_prompt(ir)
        try:
            if bool(self.var_include_context.get()):
                ctx_text = self.txt_context.get("1.0", tk.END).strip()
                if ctx_text:
                    user = f"[Context]\n{ctx_text}\n\n" + user
        except Exception:
            pass
        return system, user, ir

    def _compute_cognitive_load(self, prompt: str) -> str:
        """Rough heuristic: combines character and sentence counts."""
        text = prompt.strip()
        if not text:
            return "unknown"
        chars = len(text)
        sentences = max(1, text.count(".") + text.count("!") + text.count("?"))
        words = len(text.split())
        score = chars / 400 + sentences / 3 + words / 150
        if score >= 6:
            return "high"
        if score >= 3:
            return "medium"
        return "low"

    def _record_analytics(
        self, prompt: str, ir_obj, elapsed_ms: int, *, task_type: str, tags: Optional[List[str]] = None
    ) -> None:
        """Best-effort analytics logging for desktop runs."""
        try:
            load = self._compute_cognitive_load(prompt)
            tag_list = tags or []
            if load not in tag_list:
                tag_list.append(f"load:{load}")
            record = create_record_from_ir(
                prompt,
                ir_obj.model_dump() if hasattr(ir_obj, "model_dump") else ir_obj,
                None,
                interface_type="desktop",
                user_level=(self.var_user_level.get() or "intermediate").strip(),
                task_type=task_type,
                time_ms=elapsed_ms,
                iteration_count=1,
                tags=tag_list,
            )
            self.analytics_manager.record_prompt(record)
        except Exception:
            try:
                self.status_var.set("Analytics logging skipped")
            except Exception:
                pass

    def on_send_openai(self):  # pragma: no cover - UI action
        prompt = self.txt_prompt.get("1.0", tk.END).strip()
        if not prompt:
            messagebox.showwarning("LLM", "Enter a prompt text first.")
            return
        provider = (self.var_llm_provider.get() or "OpenAI").strip()
        try:
            system, user, ir = self._prepare_llm_messages(prompt)
        except Exception as exc:
            messagebox.showerror("LLM", f"Failed to prepare prompt: {exc}")
            return
        t0 = time.time()

        def _focus_llm_tab():
            try:
                for i in range(self.nb.index("end")):
                    if self.nb.tab(i, "text") == "LLM Response":
                        self.nb.select(i)
                        break
            except Exception:
                pass

        if provider == "Local HTTP":
            endpoint = (self.var_local_endpoint.get() or "").strip()
            if not endpoint:
                messagebox.showerror("Local LLM", "Set a local HTTP endpoint URL first.")
                return
            model = (self.var_model.get() or "local-model").strip()
            api_key = (self.var_local_api_key.get() or "").strip()
            headers = {"Content-Type": "application/json"}
            if api_key:
                if api_key.lower().startswith("bearer "):
                    headers["Authorization"] = api_key
                else:
                    headers["Authorization"] = f"Bearer {api_key}"
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.7,
            }
            self.status_var.set(f"Local LLM: sending ({model})...")

            def _send_local():
                try:
                    resp = httpx.post(endpoint, json=payload, timeout=60, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    content = None
                    try:
                        choices = data.get("choices")
                        if choices:
                            msg = choices[0].get("message", {})
                            content = msg.get("content") or choices[0].get("text")
                    except Exception:
                        content = None
                    if content is None:
                        content = json.dumps(data, ensure_ascii=False, indent=2)
                    self.txt_llm.delete("1.0", tk.END)
                    self.txt_llm.insert(tk.END, content or "<no content>")
                    _focus_llm_tab()
                    self.status_var.set("Local LLM: done")
                    try:
                        elapsed = int((time.time() - t0) * 1000)
                        load = self._compute_cognitive_load(prompt)
                        self.cognitive_load_var.set(f"Load: {load}")
                        self._record_analytics(
                            prompt,
                            ir,
                            elapsed,
                            task_type="llm_send",
                            tags=["llm_send"],
                        )
                    except Exception:
                        pass
                except Exception as e:
                    self.status_var.set("Local LLM: error")
                    messagebox.showerror("Local LLM", str(e))

            self.root.after(30, _send_local)
            return

        # Default to OpenAI provider
        if OpenAI is None:
            messagebox.showerror(
                "OpenAI", "Package 'openai' not installed. Run: pip install openai"
            )
            return
        if not os.environ.get("OPENAI_API_KEY"):
            messagebox.showerror("OpenAI", "OPENAI_API_KEY is not set in environment.")
            return
        model = (self.var_model.get() or "gpt-4o-mini").strip()
        self.status_var.set(f"OpenAI: sending ({model})...")

        def _send_openai():
            try:
                client = OpenAI()
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.7,
                )
                try:
                    content = resp.choices[0].message.content  # type: ignore[attr-defined]
                except Exception:
                    content = str(resp)
                self.txt_llm.delete("1.0", tk.END)
                self.txt_llm.insert(tk.END, content or "<no content>")
                _focus_llm_tab()
                self.status_var.set("OpenAI: done")
                try:
                    elapsed = int((time.time() - t0) * 1000)
                    load = self._compute_cognitive_load(prompt)
                    self.cognitive_load_var.set(f"Load: {load}")
                    self._record_analytics(
                        prompt,
                        ir,
                        elapsed,
                        task_type="llm_send",
                        tags=["llm_send"],
                    )
                except Exception:
                    pass
            except Exception as e:
                self.status_var.set("OpenAI: error")
                messagebox.showerror("OpenAI", str(e))

        self.root.after(30, _send_openai)

    def _generate_core(self, prompt: str):
        try:
            t0 = time.time()
            ir = optimize_ir(compile_text(prompt))
            diagnostics = self.var_diag.get()
            # Compile IR v2 for potential rendering and tables
            ir2 = None
            try:
                ir2 = compile_text_v2(prompt)
            except Exception:
                ir2 = None
            # Choose emitters based on toggle
            use_v2_emitters = bool(self.var_render_v2.get()) and ir2 is not None
            if use_v2_emitters and ir2 is not None:
                system = emit_system_prompt_v2(ir2)
                user = emit_user_prompt_v2(ir2)
                plan = emit_plan_v2(ir2)
                expanded = emit_expanded_prompt_v2(ir2, diagnostics=diagnostics)
            else:
                system = emit_system_prompt(ir)
                user = emit_user_prompt(ir)
                plan = emit_plan(ir)
                expanded = emit_expanded_prompt(ir, diagnostics=diagnostics)
            # Inject optional Context section (applies to both branches)
            try:
                if bool(self.var_include_context.get()):
                    ctx_text = self.txt_context.get("1.0", tk.END).strip() or ""
                    if ctx_text:
                        user = f"[Context]\n{ctx_text}\n\n" + user
                        expanded = f"[Context]\n{ctx_text}\n\n" + expanded
            except Exception:
                pass
            ir_json = json.dumps(ir.model_dump(), ensure_ascii=False, indent=2)
            ir2_json = (
                json.dumps(ir2.model_dump(), ensure_ascii=False, indent=2)
                if ir2 is not None
                else ""
            )
            # Optional extras
            trace_lines = generate_trace(ir) if self.var_trace.get() else []
            mapping = [
                (self.txt_system, system),
                (self.txt_user, user),
                (self.txt_plan, plan),
                (self.txt_expanded, expanded),
                (self.txt_ir, ir_json),
                (self.txt_ir2, ir2_json),
                (self.txt_trace, "\n".join(trace_lines) if trace_lines else ""),
            ]
            for widget, data in mapping:
                widget.delete("1.0", tk.END)
                widget.insert(tk.END, data)
            # IR Diff (simple)
            try:
                import difflib

                a = (ir_json or "").splitlines(keepends=True)
                b = (ir2_json or "").splitlines(keepends=True)
                diff = difflib.unified_diff(a, b, fromfile="IR v1", tofile="IR v2")
                diff_text = "".join(diff)
            except Exception:
                diff_text = ""
            self.txt_diff.delete("1.0", tk.END)
            self.txt_diff.insert(tk.END, diff_text)
            # Populate intents chips and constraints table from IR v2
            for w in self.chips_container.winfo_children():
                w.destroy()
            if ir2 is not None:
                # Intent chips
                for intent in getattr(ir2, "intents", []) or []:
                    lbl = ttk.Label(self.chips_container, text=intent, style="Chip.TLabel")
                    lbl.pack(side=tk.LEFT, padx=4, pady=2)
                # Constraints table sorted by priority desc
                rows = []
                for c in getattr(ir2, "constraints", []) or []:
                    pr = getattr(c, "priority", 0) or 0
                    rows.append(
                        (pr, getattr(c, "origin", ""), getattr(c, "id", ""), getattr(c, "text", ""))
                    )
                rows.sort(key=lambda r: r[0], reverse=True)
                # Save all rows and render via helper (supports filtering)
                self._constraints_rows_all = rows
                self._render_constraints_table()
            meta = ir.metadata or {}
            persona = getattr(ir, "persona", "?")
            complexity = meta.get("complexity")
            risk_flags = meta.get("risk_flags") or []
            amb = meta.get("ambiguous_terms") or []
            parts = [f"Persona: {persona}"]
            if complexity:
                parts.append(f"Complexity: {complexity}")
            if risk_flags:
                parts.append("Risk: " + ",".join(risk_flags[:3]))
            if diagnostics and amb:
                parts.append("Ambiguous: " + ",".join(sorted(amb)[:5]))
            elapsed = int((time.time() - t0) * 1000)
            load = self._compute_cognitive_load(prompt)
            self.cognitive_load_var.set(f"Load: {load}")
            self.summary_var.set(" | ".join(parts))
            suffix = " • v2 emitters" if use_v2_emitters else ""
            self.status_var.set(
                f"✅ Done ({elapsed} ms) • heur v1 {HEURISTIC_VERSION} • heur v2 {HEURISTIC2_VERSION}{suffix}"
            )

            # Best-effort analytics capture (desktop)
            self._record_analytics(prompt, ir, elapsed, task_type=self.var_task_type.get())

            # Apply JSON syntax highlighting
            self._apply_json_highlighting(self.txt_ir, ir_json)
            if ir2_json:
                self._apply_json_highlighting(self.txt_ir2, ir2_json)

        except Exception as e:  # pragma: no cover
            self.status_var.set("❌ Error")
            messagebox.showerror("Error", str(e))
        finally:
            # Stop progress animation
            self.is_generating = False
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
            self.btn_generate.config(state="normal")

    def _copy_constraints(self):
        if not hasattr(self, "tree_constraints"):
            return
        rows = [
            self.tree_constraints.item(i, "values") for i in self.tree_constraints.get_children()
        ]
        if not rows:
            return
        # Build Markdown table
        md = ["| Priority | Origin | ID | Text |", "|---:|---|---|---|"]
        for pr, origin, idv, text in rows:
            text_str = str(text).replace("|", "\\|")
            md.append(f"| {pr} | {origin} | {idv} | {text_str} |")
        data = "\n".join(md)
        self.root.clipboard_clear()
        self.root.clipboard_append(data)
        self.status_var.set("Constraints copied")

    def _export_constraints_csv(self):
        if not hasattr(self, "tree_constraints"):
            return
        rows = [
            self.tree_constraints.item(i, "values") for i in self.tree_constraints.get_children()
        ]
        if not rows:
            messagebox.showinfo("Export", "No constraints to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv"), ("All Files", "*.*")]
        )
        if not path:
            return
        try:
            # Simple CSV without quotes for readability; escape commas in text
            lines = ["priority,origin,id,text"]
            for pr, origin, idv, text in rows:
                text_s = str(text).replace("\n", " ").replace('"', '""')
                # surround text with quotes to preserve commas
                lines.append(f'{pr},{origin},{idv},"{text_s}"')
            Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
            messagebox.showinfo("Export", f"Saved: {path}")
        except Exception as e:
            messagebox.showerror("Export", str(e))

    def _export_constraints_json(self):
        if not hasattr(self, "tree_constraints"):
            return
        rows = [
            self.tree_constraints.item(i, "values") for i in self.tree_constraints.get_children()
        ]
        if not rows:
            messagebox.showinfo("Export", "No constraints to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON", "*.json"), ("All Files", "*.*")]
        )
        if not path:
            return
        try:
            data = [
                {"priority": pr, "origin": origin, "id": idv, "text": text}
                for pr, origin, idv, text in rows
            ]
            Path(path).write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            messagebox.showinfo("Export", f"Saved: {path}")
        except Exception as e:
            messagebox.showerror("Export", str(e))

    def _copy_all_texts(self):
        parts = [
            ("System Prompt", self.txt_system),
            ("User Prompt", self.txt_user),
            ("Plan", self.txt_plan),
            ("Expanded Prompt", self.txt_expanded),
        ]
        buf = []
        for title, widget in parts:
            val = widget.get("1.0", tk.END).strip()
            if val:
                buf.append(f"# {title}\n\n{val}")
        if not buf:
            return
        data = "\n\n".join(buf)
        self.root.clipboard_clear()
        self.root.clipboard_append(data)
        self.status_var.set("All outputs copied")

    def _export_text(self, widget: tk.Text, default_ext: str = ".txt"):
        ft = [("All Files", "*.*")]
        if default_ext == ".json":
            ft = [("JSON", "*.json"), ("All Files", "*.*")]
        path = filedialog.asksaveasfilename(defaultextension=default_ext, filetypes=ft)
        if not path:
            return
        data = widget.get("1.0", tk.END).strip()
        try:
            Path(path).write_text(data + "\n", encoding="utf-8")
            messagebox.showinfo("Export", f"Saved: {path}")
        except Exception as e:
            messagebox.showerror("Export", str(e))

    def _export_markdown_combined(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".md", filetypes=[("Markdown", "*.md"), ("All Files", "*.*")]
        )
        if not path:
            return
        content = []
        content.append("# System Prompt\n\n" + self.txt_system.get("1.0", tk.END).strip())
        content.append("\n\n# User Prompt\n\n" + self.txt_user.get("1.0", tk.END).strip())
        content.append("\n\n# Plan\n\n" + self.txt_plan.get("1.0", tk.END).strip())
        content.append("\n\n# Expanded Prompt\n\n" + self.txt_expanded.get("1.0", tk.END).strip())
        try:
            Path(path).write_text("\n".join(content), encoding="utf-8")
            messagebox.showinfo("Export", f"Saved: {path}")
        except Exception as e:
            messagebox.showerror("Export", str(e))

    def _render_constraints_table(self):
        # Render constraints from cached rows with optional live_debug filter
        if not hasattr(self, "tree_constraints"):
            return
        rows = getattr(self, "_constraints_rows_all", [])
        if not isinstance(rows, list):
            rows = []
        if bool(getattr(self, "var_only_live_debug", tk.BooleanVar(value=False)).get()):
            rows_to_show = [r for r in rows if (len(r) > 1 and str(r[1]) == "live_debug")]
        else:
            rows_to_show = rows
        # Apply min priority filter if set
        try:
            mp_raw = getattr(self, "var_min_priority", tk.StringVar(value="Any")).get()
            if mp_raw and mp_raw != "Any":
                mp = int(mp_raw)
                rows_to_show = [r for r in rows_to_show if (len(r) > 0 and int(r[0]) >= mp)]
        except Exception:
            pass
        # Apply text search filter
        try:
            term = (
                getattr(self, "var_constraints_search", tk.StringVar(value=""))
                .get()
                .strip()
                .lower()
            )
            if term:
                rows_to_show = [
                    r for r in rows_to_show if any(term in str(cell).lower() for cell in r)
                ]
        except Exception:
            pass
        # Apply sorting state
        try:
            state = getattr(self, "_constraints_sort_state", None)
            if state and state.get("col"):
                col = state["col"]
                idx_map = {"priority": 0, "origin": 1, "id": 2, "text": 3}
                ci = idx_map.get(col)
                if ci is not None:
                    rows_to_show = sorted(
                        rows_to_show,
                        key=lambda r: (r[ci] if ci < len(r) else ""),
                        reverse=bool(state.get("reverse")),
                    )
        except Exception:
            pass
        for i in self.tree_constraints.get_children():
            self.tree_constraints.delete(i)
        for r in rows_to_show:
            self.tree_constraints.insert("", tk.END, values=r)
        # Persist filter state
        self._save_settings()

    def _sort_constraints(self, column: str):  # pragma: no cover - UI event
        try:
            state = getattr(self, "_constraints_sort_state", {"col": None, "reverse": False})
            if state.get("col") == column:
                state["reverse"] = not state.get("reverse")
            else:
                state["col"] = column
                state["reverse"] = False
            self._constraints_sort_state = state
            self._render_constraints_table()
        except Exception:
            pass

    def _copy_as_curl(self):  # pragma: no cover - UI utility
        try:
            prompt = self.txt_prompt.get("1.0", tk.END).strip()
            diagnostics = "true" if bool(self.var_diag.get()) else "false"
            trace = "true" if bool(self.var_trace.get()) else "false"
            render_v2_prompts = "true" if bool(self.var_render_v2.get()) else "false"
            payload = {
                "text": prompt,
                "diagnostics": diagnostics == "true",
                "trace": trace == "true",
                "v2": True,
                "render_v2_prompts": render_v2_prompts == "true",
            }
            # Minify JSON for curl
            body = json.dumps(payload, ensure_ascii=False)
            # Escape single quotes for POSIX shell: close quote, insert escaped quote, reopen.
            # Replace ' with '\'' pattern (achieved via '"'"' sequence) to keep portability.
            escaped = body.replace("'", "'\"'\"'")
            cmd = (
                "curl -s -X POST http://localhost:8000/compile "
                '-H "Content-Type: application/json" '
                f"--data '{escaped}'"
            )
            self.root.clipboard_clear()
            self.root.clipboard_append(cmd)
            self.status_var.set("cURL copied")
        except Exception:
            pass

    def _on_example_selected(self, _e=None):  # pragma: no cover - UI utility
        try:
            name = getattr(self, "var_example", tk.StringVar(value="")).get()
            if not name or name == "<select>":
                return
            path = getattr(self, "_examples_map", {}).get(name)
            if not path:
                return
            try:
                text = Path(path).read_text(encoding="utf-8")
            except Exception as e:
                messagebox.showerror("Examples", str(e))
                return
            self.txt_prompt.delete("1.0", tk.END)
            self.txt_prompt.insert(tk.END, text.strip())
            try:
                self._update_prompt_stats()
            except Exception:
                pass
            self.status_var.set(f"Loaded: {name}")
            try:
                if bool(getattr(self, "var_autogen_example", tk.BooleanVar(value=False)).get()):
                    # Trigger generation shortly after UI updates
                    self.root.after(10, self.on_generate)
            except Exception:
                pass
        except Exception:
            pass

    def on_save(self):
        # Offer to save combined Markdown or IR JSONs
        win = tk.Toplevel(self.root)
        win.title("Save Outputs")
        win.geometry("420x200")
        frm = ttk.Frame(win, padding=8)
        frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text="Choose what to save:").pack(anchor=tk.W)

        def save_md():
            path = filedialog.asksaveasfilename(
                defaultextension=".md", filetypes=[("Markdown", "*.md"), ("All Files", "*.*")]
            )
            if not path:
                return
            content = []
            content.append("# System Prompt\n\n" + self.txt_system.get("1.0", tk.END).strip())
            content.append("\n\n# User Prompt\n\n" + self.txt_user.get("1.0", tk.END).strip())
            content.append("\n\n# Plan\n\n" + self.txt_plan.get("1.0", tk.END).strip())
            content.append(
                "\n\n# Expanded Prompt\n\n" + self.txt_expanded.get("1.0", tk.END).strip()
            )
            try:
                Path(path).write_text("\n".join(content), encoding="utf-8")
                messagebox.showinfo("Save", f"Saved: {path}")
            except Exception as e:
                messagebox.showerror("Save", str(e))

        def save_ir():
            path = filedialog.asksaveasfilename(
                defaultextension=".json", filetypes=[("JSON", "*.json"), ("All Files", "*.*")]
            )
            if not path:
                return
            try:
                Path(path).write_text(
                    self.txt_ir.get("1.0", tk.END).strip() + "\n", encoding="utf-8"
                )
                messagebox.showinfo("Save", f"Saved: {path}")
            except Exception as e:
                messagebox.showerror("Save", str(e))

        def save_ir2():
            path = filedialog.asksaveasfilename(
                defaultextension=".json", filetypes=[("JSON", "*.json"), ("All Files", "*.*")]
            )
            if not path:
                return
            try:
                Path(path).write_text(
                    self.txt_ir2.get("1.0", tk.END).strip() + "\n", encoding="utf-8"
                )
                messagebox.showinfo("Save", f"Saved: {path}")
            except Exception as e:
                messagebox.showerror("Save", str(e))

        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btns, text="Save Combined Markdown", command=save_md).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Save IR v1 JSON", command=save_ir).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Save IR v2 JSON", command=save_ir2).pack(side=tk.LEFT, padx=4)

    # Extra helpers
    def _export_trace(self):
        data = self.txt_trace.get("1.0", tk.END).strip()
        if not data:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text", "*.txt"), ("All Files", "*.*")]
        )
        if not path:
            return
        try:
            Path(path).write_text(data + "\n", encoding="utf-8")
            messagebox.showinfo("Export", f"Saved: {path}")
        except Exception as e:
            messagebox.showerror("Export", str(e))

    def _find_in_active(self):
        try:
            idx = self.nb.index(self.nb.select())
            widget = None
            # map tab title to text widget
            title = self.nb.tab(idx, "text")
            mapping = {
                "System Prompt": self.txt_system,
                "User Prompt": self.txt_user,
                "Plan": self.txt_plan,
                "Expanded Prompt": self.txt_expanded,
                "IR JSON": self.txt_ir,
                "IR v2 JSON": self.txt_ir2,
                "LLM Response": self.txt_llm,
                "Trace": self.txt_trace,
                "IR Diff": self.txt_diff,
            }
            widget = mapping.get(title)
            if widget is None:
                return
            self._open_find_dialog(widget)
        except Exception:
            pass

    def _open_find_dialog(self, widget: tk.Text):
        win = tk.Toplevel(self.root)
        win.title("Find")
        win.geometry("320x80")
        frm = ttk.Frame(win, padding=8)
        frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text="Find:").pack(anchor=tk.W)
        var = tk.StringVar()
        ent = ttk.Entry(frm, textvariable=var)
        ent.pack(fill=tk.X)
        ent.focus_set()

        def do_find():
            term = var.get()
            if not term:
                return
            try:
                start = widget.search(term, widget.index(tk.INSERT), stopindex=tk.END, nocase=True)
                if not start:
                    start = widget.search(term, "1.0", stopindex=tk.END, nocase=True)
                if start:
                    end = f"{start}+{len(term)}c"
                    widget.tag_remove("sel", "1.0", tk.END)
                    widget.tag_add("sel", start, end)
                    widget.mark_set(tk.INSERT, end)
                    widget.see(start)
            except Exception:
                pass

        ttk.Button(frm, text="Find Next", command=do_find).pack(anchor=tk.E, pady=(6, 0))

    def _update_prompt_stats(self):
        try:
            text = self.txt_prompt.get("1.0", tk.END)
            s = text.rstrip("\n")
            chars = len(s)
            words = len([w for w in s.split() if w])
            # Rough token estimate (~4 chars/token heuristic)
            tokens_est = (chars + 3) // 4 if chars else 0
            self.prompt_stats_var.set(f"Chars: {chars} | Words: {words} | ≈ Tokens: {tokens_est}")
        except Exception:
            pass

    def _apply_wrap(self):
        wrap_mode = tk.WORD if bool(self.var_wrap.get()) else tk.NONE
        for t in [
            self.txt_system,
            self.txt_user,
            self.txt_plan,
            self.txt_expanded,
            self.txt_ir,
            self.txt_ir2,
            self.txt_trace,
            getattr(self, "txt_llm", None),
            getattr(self, "txt_diff", None),
            getattr(self, "txt_quality_report", None),
            getattr(self, "txt_quality_fix", None),
        ]:
            if t is None:
                continue
            try:
                t.configure(wrap=wrap_mode)
            except Exception:
                pass

    def _add_tooltip(self, widget, text: str):
        """Add hover tooltip to a widget."""

        def on_enter(event):
            # Create tooltip window
            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root + 10}+{event.y_root + 10}")

            dark = self.current_theme == "dark"
            bg = "#18181b" if dark else "#fafafa"
            fg = "#e4e4e7" if dark else "#18181b"

            label = tk.Label(
                tooltip,
                text=text,
                background=bg,
                foreground=fg,
                relief="solid",
                borderwidth=1,
                font=("", 9),
                padx=8,
                pady=4,
            )
            label.pack()
            widget._tooltip = tooltip

        def on_leave(event):
            if hasattr(widget, "_tooltip"):
                try:
                    widget._tooltip.destroy()
                except Exception:
                    pass

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def _setup_json_highlighting(self, text_widget: tk.Text):
        """Setup tags for JSON syntax highlighting."""
        dark = self.current_theme == "dark"

        # Color scheme for JSON
        if dark:
            text_widget.tag_configure("json_key", foreground="#a5d6ff")  # Light blue
            text_widget.tag_configure("json_string", foreground="#7ee787")  # Green
            text_widget.tag_configure("json_number", foreground="#79c0ff")  # Blue
            text_widget.tag_configure("json_bool", foreground="#ffa657")  # Orange
            text_widget.tag_configure("json_null", foreground="#ffa657")  # Orange
            text_widget.tag_configure("json_brace", foreground="#c9d1d9")  # Gray
        else:
            text_widget.tag_configure("json_key", foreground="#0550ae")  # Blue
            text_widget.tag_configure("json_string", foreground="#0a3069")  # Dark blue
            text_widget.tag_configure("json_number", foreground="#6639ba")  # Purple
            text_widget.tag_configure("json_bool", foreground="#bf3989")  # Magenta
            text_widget.tag_configure("json_null", foreground="#bf3989")  # Magenta
            text_widget.tag_configure("json_brace", foreground="#24292f")  # Dark gray

    def _apply_json_highlighting(self, text_widget: tk.Text, json_text: str):
        """Apply syntax highlighting to JSON text."""
        try:
            # Clear existing tags
            for tag in [
                "json_key",
                "json_string",
                "json_number",
                "json_bool",
                "json_null",
                "json_brace",
            ]:
                text_widget.tag_remove(tag, "1.0", tk.END)

            # Pattern matching for JSON elements
            patterns = [
                (r'"([^"]+)"\s*:', "json_key"),  # Keys
                (r':\s*"([^"]*)"', "json_string"),  # String values
                (r":\s*(\d+\.?\d*)", "json_number"),  # Numbers
                (r":\s*(true|false)", "json_bool"),  # Booleans
                (r":\s*(null)", "json_null"),  # Null
                (r"([{}\[\],])", "json_brace"),  # Braces and brackets
            ]

            for pattern, tag in patterns:
                for match in re.finditer(pattern, json_text):
                    start_idx = match.start(1) if match.lastindex else match.start()
                    end_idx = match.end(1) if match.lastindex else match.end()

                    # Convert to tkinter text indices
                    start_line = json_text[:start_idx].count("\n") + 1
                    start_col = start_idx - json_text[:start_idx].rfind("\n") - 1
                    end_line = json_text[:end_idx].count("\n") + 1
                    end_col = end_idx - json_text[:end_idx].rfind("\n") - 1

                    start_pos = f"{start_line}.{start_col}"
                    end_pos = f"{end_line}.{end_col}"

                    text_widget.tag_add(tag, start_pos, end_pos)
        except Exception:
            pass  # Fail silently if highlighting fails

    def _setup_drag_drop(self, widget: tk.Text, target: str = "prompt"):
        """Setup drag and drop functionality for a text widget."""
        # Store target info
        widget._drop_target = target

        def on_drag_enter(event):
            """Visual feedback when dragging over widget."""
            dark = self.current_theme == "dark"
            highlight_color = "#3b82f6" if dark else "#2563eb"
            bg_color = "#18181b" if dark else "#f4f4f5"

            widget.config(highlightbackground=highlight_color, highlightthickness=3)
            self.drop_zone_label.config(background=bg_color)
            self.drop_zone_frame.config(background=bg_color)
            self.drop_zone_var.set(f"📁 Drop {target} file here (.txt, .md)...")
            self.drop_zone_label.pack(expand=True, fill=tk.BOTH, pady=8)
            self.drop_zone_frame.pack(fill=tk.X, pady=(0, 4), padx=4)
            return event.action

        def on_drag_leave(event):
            """Remove visual feedback when drag leaves."""
            widget.config(highlightthickness=0)
            self.drop_zone_label.pack_forget()
            self.drop_zone_frame.pack_forget()
            self.drop_zone_var.set("")

        def on_drop(event):
            """Handle file drop."""
            widget.config(highlightthickness=0)
            self.drop_zone_label.pack_forget()
            self.drop_zone_frame.pack_forget()
            self.drop_zone_var.set("")

            # Get dropped files
            files = self._parse_drop_data(event.data)
            if not files:
                return

            # Process first file
            file_path = Path(files[0])
            if not file_path.exists():
                messagebox.showerror("Error", f"File not found: {file_path}")
                return

            # Check file extension
            allowed_extensions = {".txt", ".md", ".markdown", ".text"}
            if file_path.suffix.lower() not in allowed_extensions:
                messagebox.showwarning(
                    "Unsupported File",
                    f"Only text files are supported: {', '.join(allowed_extensions)}\n"
                    f"Got: {file_path.suffix}",
                )
                return

            # Read and load file
            try:
                content = file_path.read_text(encoding="utf-8")

                # Ask before replacing if there's existing content
                existing = widget.get("1.0", tk.END).strip()
                if existing:
                    if not messagebox.askyesno(
                        "Replace Content",
                        f"Replace existing {target} content with file:\n{file_path.name}?",
                    ):
                        return

                # Load content
                widget.delete("1.0", tk.END)
                widget.insert("1.0", content)

                # Update stats if this is the prompt area
                if target == "prompt":
                    self._update_prompt_stats()

                self.status_var.set(f"📁 Loaded: {file_path.name}")

                # Show success message
                messagebox.showinfo(
                    "File Loaded",
                    f"Successfully loaded:\n{file_path.name}\n\n"
                    f"Characters: {len(content)}\n"
                    f"Lines: {content.count(chr(10)) + 1}",
                )

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file:\n{str(e)}")

        # Enable drag and drop using tkinterdnd2 or built-in methods
        try:
            # Try using tkinterdnd2 if available
            from tkinterdnd2 import DND_FILES  # type: ignore

            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<DropEnter>>", on_drag_enter)
            widget.dnd_bind("<<DropLeave>>", on_drag_leave)
            widget.dnd_bind("<<Drop>>", on_drop)
        except ImportError:
            # Fallback to basic tk drag-drop (Windows only)
            try:
                widget.drop_target_register("DND_Files")
                widget.dnd_bind("<<DropEnter>>", on_drag_enter)
                widget.dnd_bind("<<DropLeave>>", on_drag_leave)
                widget.dnd_bind("<<Drop>>", on_drop)
            except Exception:
                # If DND not available, add file open button as fallback
                pass

    def _parse_drop_data(self, data: str) -> list:
        """Parse dropped file data into list of file paths."""
        # Handle different formats
        if data.startswith("{") and data.endswith("}"):
            # Windows format: {file1} {file2}
            files = []
            current = ""
            in_braces = False
            for char in data:
                if char == "{":
                    in_braces = True
                elif char == "}":
                    in_braces = False
                    if current:
                        files.append(current.strip())
                        current = ""
                elif in_braces:
                    current += char
            return files
        else:
            # Simple space-separated or single file
            return [f.strip("{}").strip() for f in data.split()]

    def _load_file_dialog(self, target: str = "prompt"):
        """Fallback: Open file dialog to load content."""
        file_path = filedialog.askopenfilename(
            title=f"Load {target.capitalize()} from File",
            filetypes=[("Text Files", "*.txt"), ("Markdown Files", "*.md"), ("All Files", "*.*")],
        )

        if not file_path:
            return

        try:
            content = Path(file_path).read_text(encoding="utf-8")
            widget = self.txt_prompt if target == "prompt" else self.txt_context

            # Ask before replacing
            existing = widget.get("1.0", tk.END).strip()
            if existing:
                if not messagebox.askyesno(
                    "Replace Content", f"Replace existing {target} content?"
                ):
                    return

            widget.delete("1.0", tk.END)
            widget.insert("1.0", content)

            if target == "prompt":
                self._update_prompt_stats()

            self.status_var.set(f"📁 Loaded: {Path(file_path).name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file:\n{str(e)}")

    def _load_history(self):
        """Load history from JSON file."""
        try:
            if self.history_path.exists():
                with open(self.history_path, "r", encoding="utf-8") as f:
                    self.history_items = json.load(f)
            else:
                self.history_items = []
        except Exception as e:
            print(f"Failed to load history: {e}")
            self.history_items = []

    def _save_to_history(self, prompt_text: str):
        """Save a new prompt to history."""
        try:
            # Create preview (first 100 chars)
            preview = prompt_text[:100].replace("\n", " ")
            if len(prompt_text) > 100:
                preview += "..."

            # Create history entry
            entry = {
                "timestamp": datetime.now().isoformat(),
                "preview": preview,
                "full_text": prompt_text,
                "is_favorite": False,
                "tags": [],
                "usage_count": 0,
                "length": len(prompt_text),
            }

            # Add to beginning of list
            self.history_items.insert(0, entry)

            # Keep only last 100 items
            if len(self.history_items) > 100:
                self.history_items = self.history_items[:100]

            # Save to file
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(self.history_items, f, indent=2, ensure_ascii=False)

            # Refresh display
            self._refresh_history()

        except Exception as e:
            print(f"Failed to save to history: {e}")

    def _refresh_history(self):
        """Refresh the history listbox display with advanced filters."""
        try:
            # Clear listbox
            self.history_listbox.delete(0, tk.END)

            # Get search filter
            search_term = self.search_var.get().lower()

            # Get advanced filters
            favorites_only = (
                self.filter_favorites_only.get()
                if hasattr(self, "filter_favorites_only")
                else False
            )
            length_filter = self.filter_length.get() if hasattr(self, "filter_length") else "all"
            date_range = (
                self.filter_date_range.get() if hasattr(self, "filter_date_range") else "all"
            )
            sort_by = self.filter_sort.get() if hasattr(self, "filter_sort") else "date (newest)"

            # Filter and collect items
            filtered_items = []
            for item in self.history_items:
                preview = item["preview"]

                # Filter by search term
                if search_term and search_term not in preview.lower():
                    continue

                # Filter by tags
                if self.active_tag_filter:
                    item_tags = item.get("tags", [])
                    if not any(tag in item_tags for tag in self.active_tag_filter):
                        continue

                # Filter by favorites
                if favorites_only and not item.get("is_favorite", False):
                    continue

                # Filter by length
                item_length = item.get("length", len(item.get("full_text", "")))
                if length_filter == "short (<100)" and item_length >= 100:
                    continue
                elif length_filter == "medium (100-500)" and (
                    item_length < 100 or item_length > 500
                ):
                    continue
                elif length_filter == "long (>500)" and item_length <= 500:
                    continue

                # Filter by date range
                if date_range != "all":
                    try:
                        item_date = datetime.fromisoformat(item["timestamp"])
                        now = datetime.now()
                        days_diff = (now - item_date).days

                        if date_range == "today" and days_diff > 0:
                            continue
                        elif date_range == "last 7 days" and days_diff > 7:
                            continue
                        elif date_range == "last 30 days" and days_diff > 30:
                            continue
                        elif date_range == "last 90 days" and days_diff > 90:
                            continue
                    except Exception:
                        pass

                filtered_items.append(item)

            # Sort items
            if sort_by == "date (newest)":
                filtered_items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            elif sort_by == "date (oldest)":
                filtered_items.sort(key=lambda x: x.get("timestamp", ""))
            elif sort_by == "length (short)":
                filtered_items.sort(key=lambda x: x.get("length", len(x.get("full_text", ""))))
            elif sort_by == "length (long)":
                filtered_items.sort(
                    key=lambda x: x.get("length", len(x.get("full_text", ""))), reverse=True
                )
            elif sort_by == "most used":
                filtered_items.sort(key=lambda x: x.get("usage_count", 0), reverse=True)

            # Add items to listbox
            for item in filtered_items:
                preview = item["preview"]

                # Add favorite star
                if item.get("is_favorite", False):
                    preview = "⭐ " + preview

                # Add tag indicators
                item_tags = item.get("tags", [])
                if item_tags:
                    tag_str = " ".join([f"[{tag}]" for tag in item_tags[:3]])
                    preview = f"{preview} {tag_str}"

                # Add usage count if > 0
                usage_count = item.get("usage_count", 0)
                if usage_count > 0:
                    preview = f"{preview} (↻{usage_count})"

                self.history_listbox.insert(tk.END, preview)

        except Exception as e:
            print(f"Failed to refresh history: {e}")

    def _filter_history(self):
        """Filter history based on search term."""
        self._refresh_history()

    def _load_prompt_from_history(self):
        """Load selected prompt from history into prompt area."""
        try:
            selection = self.history_listbox.curselection()
            if not selection:
                return

            idx = selection[0]

            # Get search filter to find correct item
            search_term = self.search_var.get().lower()
            filtered_items = []
            for item in self.history_items:
                if not search_term or search_term in item["preview"].lower():
                    filtered_items.append(item)

            if idx >= len(filtered_items):
                return

            item = filtered_items[idx]
            prompt_text = item["full_text"]

            # Ask before replacing
            existing = self.txt_prompt.get("1.0", tk.END).strip()
            if existing:
                if not messagebox.askyesno(
                    "Replace Prompt", "Replace current prompt with history item?"
                ):
                    return

            # Increment usage count
            # Find actual index in history_items
            for i, hist_item in enumerate(self.history_items):
                if (
                    hist_item["full_text"] == prompt_text
                    and hist_item["timestamp"] == item["timestamp"]
                ):
                    self.history_items[i]["usage_count"] = (
                        self.history_items[i].get("usage_count", 0) + 1
                    )
                    # Save updated count
                    with open(self.history_path, "w", encoding="utf-8") as f:
                        json.dump(self.history_items, f, indent=2, ensure_ascii=False)
                    break

            # Load prompt
            self.txt_prompt.delete("1.0", tk.END)
            self.txt_prompt.insert("1.0", prompt_text)
            self._update_prompt_stats()

            self.status_var.set("📜 Loaded from history")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load prompt: {e}")

    def _delete_history_item(self):
        """Delete selected item from history."""
        try:
            selection = self.history_listbox.curselection()
            if not selection:
                return

            idx = selection[0]

            # Get filtered items
            search_term = self.search_var.get().lower()
            filtered_items = []
            filtered_indices = []
            for i, item in enumerate(self.history_items):
                if not search_term or search_term in item["preview"].lower():
                    filtered_items.append(item)
                    filtered_indices.append(i)

            if idx >= len(filtered_items):
                return

            # Confirm deletion
            if not messagebox.askyesno("Delete Item", "Delete this item from history?"):
                return

            # Remove from history
            actual_idx = filtered_indices[idx]
            del self.history_items[actual_idx]

            # Save and refresh
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(self.history_items, f, indent=2, ensure_ascii=False)

            self._refresh_history()
            self.status_var.set("🗑️ Item deleted")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete item: {e}")

    def _clear_history(self):
        """Clear all history items."""
        try:
            if not messagebox.askyesno(
                "Clear History", "Delete all history items? This cannot be undone."
            ):
                return

            self.history_items = []

            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(self.history_items, f, indent=2, ensure_ascii=False)

            self._refresh_history()
            self.status_var.set("🗑️ History cleared")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to clear history: {e}")

    def _toggle_sidebar(self):
        """Toggle sidebar visibility."""
        try:
            if self.sidebar_visible:
                # Hide sidebar
                self.main_container.forget(self.sidebar)
                self.sidebar_toggle_btn.config(text="▶")
                self.sidebar_visible = False
            else:
                # Show sidebar
                self.main_container.insert(0, self.sidebar)
                self.sidebar_toggle_btn.config(text="◀")
                self.sidebar_visible = True
        except Exception as e:
            print(f"Failed to toggle sidebar: {e}")

    def _show_history_context_menu(self, event):
        """Show context menu for history item."""
        try:
            # Select item under cursor
            idx = self.history_listbox.nearest(event.y)
            self.history_listbox.selection_clear(0, tk.END)
            self.history_listbox.selection_set(idx)

            # Create context menu
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="📂 Load", command=self._load_prompt_from_history)
            menu.add_command(label="⭐ Toggle Favorite", command=self._toggle_favorite)
            menu.add_command(label="🏷️ Manage Tags", command=self._manage_item_tags)
            menu.add_separator()
            menu.add_command(label="🗑️ Delete", command=self._delete_history_item)

            # Show menu
            menu.tk_popup(event.x_root, event.y_root)

        except Exception as e:
            print(f"Failed to show context menu: {e}")

    def _toggle_favorite(self):
        """Toggle favorite status of selected item."""
        try:
            selection = self.history_listbox.curselection()
            if not selection:
                return

            idx = selection[0]

            # Get filtered items
            search_term = self.search_var.get().lower()
            filtered_indices = []
            for i, item in enumerate(self.history_items):
                if not search_term or search_term in item["preview"].lower():
                    filtered_indices.append(i)

            if idx >= len(filtered_indices):
                return

            # Toggle favorite
            actual_idx = filtered_indices[idx]
            self.history_items[actual_idx]["is_favorite"] = not self.history_items[actual_idx].get(
                "is_favorite", False
            )

            # Save and refresh
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(self.history_items, f, indent=2, ensure_ascii=False)

            self._refresh_history()

            # Restore selection
            if idx < self.history_listbox.size():
                self.history_listbox.selection_set(idx)

        except Exception as e:
            print(f"Failed to toggle favorite: {e}")

    def _manage_item_tags(self):
        """Manage tags for selected history item."""
        try:
            selection = self.history_listbox.curselection()
            if not selection:
                return

            idx = selection[0]

            # Get actual item index
            search_term = self.search_var.get().lower()
            filtered_items = []
            filtered_indices = []
            for i, item in enumerate(self.history_items):
                if not search_term or search_term in item["preview"].lower():
                    # Apply tag filter
                    if self.active_tag_filter:
                        item_tags = item.get("tags", [])
                        if not any(tag in item_tags for tag in self.active_tag_filter):
                            continue
                    filtered_items.append(item)
                    filtered_indices.append(i)

            if idx >= len(filtered_items):
                return

            actual_idx = filtered_indices[idx]
            item = self.history_items[actual_idx]

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Manage Tags")
            dialog.geometry("400x300")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Select tags for this prompt:", font=("", 10, "bold")).pack(
                anchor=tk.W, padx=10, pady=10
            )

            # Tag checkboxes
            tag_vars = {}
            current_tags = item.get("tags", [])

            tags_frame = ttk.Frame(dialog)
            tags_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

            for tag_info in self.available_tags:
                tag_name = tag_info["name"]
                tag_color = tag_info["color"]

                var = tk.BooleanVar(value=tag_name in current_tags)
                tag_vars[tag_name] = var

                check_frame = tk.Frame(tags_frame, bg=tag_color, padx=2, pady=2)
                check_frame.pack(fill=tk.X, pady=2)

                cb = ttk.Checkbutton(check_frame, text=tag_name, variable=var)
                cb.pack(anchor=tk.W)

            # Buttons
            btn_frame = ttk.Frame(dialog)
            btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            def save_tags():
                selected_tags = [tag for tag, var in tag_vars.items() if var.get()]
                self.history_items[actual_idx]["tags"] = selected_tags

                with open(self.history_path, "w", encoding="utf-8") as f:
                    json.dump(self.history_items, f, indent=2, ensure_ascii=False)

                self._refresh_history()
                dialog.destroy()
                self.status_var.set("🏷️ Updated tags")

            ttk.Button(btn_frame, text="💾 Save", command=save_tags).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(btn_frame, text="❌ Cancel", command=dialog.destroy).pack(side=tk.LEFT)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to manage tags: {e}")

    def _load_tags(self):
        """Load available tags from JSON file."""
        try:
            if self.tags_path.exists():
                with open(self.tags_path, "r", encoding="utf-8") as f:
                    self.available_tags = json.load(f)
            else:
                # Default tags
                self.available_tags = [
                    {"name": "code", "color": "#3b82f6"},
                    {"name": "writing", "color": "#10b981"},
                    {"name": "analysis", "color": "#f59e0b"},
                    {"name": "debug", "color": "#ef4444"},
                    {"name": "review", "color": "#8b5cf6"},
                    {"name": "tutorial", "color": "#ec4899"},
                    {"name": "test", "color": "#06b6d4"},
                    {"name": "docs", "color": "#84cc16"},
                ]
                self._save_tags()
        except Exception as e:
            print(f"Failed to load tags: {e}")
            self.available_tags = []

    def _save_tags(self):
        """Save tags to JSON file."""
        try:
            with open(self.tags_path, "w", encoding="utf-8") as f:
                json.dump(self.available_tags, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save tags: {e}")

    def _update_tag_filters(self):
        """Update tag filter buttons."""
        try:
            # Clear existing buttons
            for widget in self.tags_filter_frame.winfo_children():
                widget.destroy()

            # Add "All" button
            all_btn = tk.Button(
                self.tags_filter_frame,
                text="All",
                command=lambda: self._toggle_tag_filter(None),
                relief="raised" if self.active_tag_filter else "sunken",
                padx=6,
                pady=2,
                font=("", 8),
            )
            all_btn.pack(side=tk.LEFT, padx=2, pady=2)

            # Add tag buttons
            for tag in self.available_tags:
                tag_name = tag["name"]
                tag_color = tag["color"]
                is_active = tag_name in self.active_tag_filter

                btn = tk.Button(
                    self.tags_filter_frame,
                    text=tag_name,
                    command=lambda t=tag_name: self._toggle_tag_filter(t),
                    bg=tag_color if is_active else "#e5e7eb",
                    fg="white" if is_active else "black",
                    relief="sunken" if is_active else "raised",
                    padx=6,
                    pady=2,
                    font=("", 8),
                    borderwidth=1,
                )
                btn.pack(side=tk.LEFT, padx=2, pady=2)

        except Exception as e:
            print(f"Failed to update tag filters: {e}")

    def _toggle_tag_filter(self, tag_name):
        """Toggle tag filter on/off."""
        try:
            if tag_name is None:
                # Clear all filters
                self.active_tag_filter = []
            else:
                # Toggle specific tag
                if tag_name in self.active_tag_filter:
                    self.active_tag_filter.remove(tag_name)
                else:
                    self.active_tag_filter.append(tag_name)

            self._update_tag_filters()
            self._filter_history()

        except Exception as e:
            print(f"Failed to toggle tag filter: {e}")

    def _load_snippets(self):
        """Load snippets from JSON file."""
        try:
            if self.snippets_path.exists():
                with open(self.snippets_path, "r", encoding="utf-8") as f:
                    self.snippets = json.load(f)
            else:
                # Default snippets
                self.snippets = [
                    {
                        "name": "Code Review Template",
                        "content": "Review this code for:\n- Best practices\n- Performance issues\n- Security vulnerabilities\n- Code quality",
                        "category": "code",
                    },
                    {
                        "name": "Bug Report",
                        "content": "**Bug Description:**\n\n**Steps to Reproduce:**\n1. \n2. \n3. \n\n**Expected Behavior:**\n\n**Actual Behavior:**",
                        "category": "debug",
                    },
                    {
                        "name": "Explain Code",
                        "content": "Explain this code in simple terms:\n- What it does\n- How it works\n- Key concepts used",
                        "category": "tutorial",
                    },
                ]
                self._save_snippets()
        except Exception as e:
            print(f"Failed to load snippets: {e}")
            self.snippets = []

    def _save_snippets(self):
        """Save snippets to JSON file."""
        try:
            with open(self.snippets_path, "w", encoding="utf-8") as f:
                json.dump(self.snippets, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save snippets: {e}")

    def _refresh_snippets(self):
        """Refresh snippets listbox."""
        try:
            self.snippets_listbox.delete(0, tk.END)
            for snippet in self.snippets:
                self.snippets_listbox.insert(tk.END, f"✂️ {snippet['name']}")
        except Exception as e:
            print(f"Failed to refresh snippets: {e}")

    def _insert_snippet(self):
        """Insert selected snippet into prompt area."""
        try:
            selection = self.snippets_listbox.curselection()
            if not selection:
                return

            idx = selection[0]
            if idx >= len(self.snippets):
                return

            snippet = self.snippets[idx]
            content = snippet["content"]

            # Get current cursor position
            try:
                cursor_pos = self.txt_prompt.index(tk.INSERT)
            except Exception:
                cursor_pos = "end"

            # Insert snippet at cursor
            self.txt_prompt.insert(cursor_pos, content)
            self._update_prompt_stats()

            self.status_var.set(f"✂️ Inserted: {snippet['name']}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to insert snippet: {e}")

    def _add_snippet(self):
        """Add new snippet dialog."""
        try:
            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Add Snippet")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()

            # Name field
            ttk.Label(dialog, text="Name:", font=("", 10, "bold")).pack(
                anchor=tk.W, padx=10, pady=(10, 2)
            )
            name_var = tk.StringVar()
            name_entry = ttk.Entry(dialog, textvariable=name_var)
            name_entry.pack(fill=tk.X, padx=10, pady=(0, 10))
            name_entry.focus()

            # Category field
            ttk.Label(dialog, text="Category:", font=("", 10, "bold")).pack(
                anchor=tk.W, padx=10, pady=(0, 2)
            )
            category_var = tk.StringVar(value="general")
            category_combo = ttk.Combobox(
                dialog,
                textvariable=category_var,
                values=[
                    "code",
                    "writing",
                    "debug",
                    "review",
                    "tutorial",
                    "test",
                    "docs",
                    "general",
                ],
            )
            category_combo.pack(fill=tk.X, padx=10, pady=(0, 10))

            # Content field
            ttk.Label(dialog, text="Content:", font=("", 10, "bold")).pack(
                anchor=tk.W, padx=10, pady=(0, 2)
            )
            content_text = tk.Text(dialog, height=10, wrap=tk.WORD)
            content_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

            # Buttons
            btn_frame = ttk.Frame(dialog)
            btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            def save_snippet():
                name = name_var.get().strip()
                category = category_var.get().strip()
                content = content_text.get("1.0", tk.END).strip()

                if not name:
                    messagebox.showwarning("Warning", "Please enter a name")
                    return

                if not content:
                    messagebox.showwarning("Warning", "Please enter content")
                    return

                self.snippets.append({"name": name, "content": content, "category": category})
                self._save_snippets()
                self._refresh_snippets()
                dialog.destroy()
                self.status_var.set(f"✂️ Added snippet: {name}")

            ttk.Button(btn_frame, text="💾 Save", command=save_snippet).pack(
                side=tk.LEFT, padx=(0, 5)
            )
            ttk.Button(btn_frame, text="❌ Cancel", command=dialog.destroy).pack(side=tk.LEFT)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to add snippet: {e}")

    def _show_snippet_context_menu(self, event):
        """Show context menu for snippet."""
        try:
            idx = self.snippets_listbox.nearest(event.y)
            self.snippets_listbox.selection_clear(0, tk.END)
            self.snippets_listbox.selection_set(idx)

            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="✂️ Insert", command=self._insert_snippet)
            menu.add_command(label="✏️ Edit", command=self._edit_snippet)
            menu.add_separator()
            menu.add_command(label="🗑️ Delete", command=self._delete_snippet)

            menu.tk_popup(event.x_root, event.y_root)

        except Exception as e:
            print(f"Failed to show snippet context menu: {e}")

    def _edit_snippet(self):
        """Edit selected snippet."""
        try:
            selection = self.snippets_listbox.curselection()
            if not selection:
                return

            idx = selection[0]
            if idx >= len(self.snippets):
                return

            snippet = self.snippets[idx]

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Edit Snippet")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()

            # Name field
            ttk.Label(dialog, text="Name:", font=("", 10, "bold")).pack(
                anchor=tk.W, padx=10, pady=(10, 2)
            )
            name_var = tk.StringVar(value=snippet["name"])
            name_entry = ttk.Entry(dialog, textvariable=name_var)
            name_entry.pack(fill=tk.X, padx=10, pady=(0, 10))

            # Category field
            ttk.Label(dialog, text="Category:", font=("", 10, "bold")).pack(
                anchor=tk.W, padx=10, pady=(0, 2)
            )
            category_var = tk.StringVar(value=snippet.get("category", "general"))
            category_combo = ttk.Combobox(
                dialog,
                textvariable=category_var,
                values=[
                    "code",
                    "writing",
                    "debug",
                    "review",
                    "tutorial",
                    "test",
                    "docs",
                    "general",
                ],
            )
            category_combo.pack(fill=tk.X, padx=10, pady=(0, 10))

            # Content field
            ttk.Label(dialog, text="Content:", font=("", 10, "bold")).pack(
                anchor=tk.W, padx=10, pady=(0, 2)
            )
            content_text = tk.Text(dialog, height=10, wrap=tk.WORD)
            content_text.insert("1.0", snippet["content"])
            content_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

            # Buttons
            btn_frame = ttk.Frame(dialog)
            btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            def save_changes():
                name = name_var.get().strip()
                category = category_var.get().strip()
                content = content_text.get("1.0", tk.END).strip()

                if not name or not content:
                    messagebox.showwarning("Warning", "Name and content are required")
                    return

                self.snippets[idx] = {"name": name, "content": content, "category": category}
                self._save_snippets()
                self._refresh_snippets()
                dialog.destroy()
                self.status_var.set(f"✏️ Updated snippet: {name}")

            ttk.Button(btn_frame, text="💾 Save", command=save_changes).pack(
                side=tk.LEFT, padx=(0, 5)
            )
            ttk.Button(btn_frame, text="❌ Cancel", command=dialog.destroy).pack(side=tk.LEFT)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to edit snippet: {e}")

    def _delete_snippet(self):
        """Delete selected snippet."""
        try:
            selection = self.snippets_listbox.curselection()
            if not selection:
                return

            idx = selection[0]
            if idx >= len(self.snippets):
                return

            snippet = self.snippets[idx]

            if messagebox.askyesno("Delete Snippet", f"Delete snippet '{snippet['name']}'?"):
                del self.snippets[idx]
                self._save_snippets()
                self._refresh_snippets()
                self.status_var.set(f"🗑️ Deleted snippet: {snippet['name']}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete snippet: {e}")

    def _clear_all_filters(self):
        """Clear all advanced filters."""
        try:
            self.search_var.set("")
            self.active_tag_filter = []
            self.filter_favorites_only.set(False)
            self.filter_length.set("all")
            self.filter_date_range.set("all")
            self.filter_sort.set("date (newest)")
            self._update_tag_filters()
            self._filter_history()
            self.status_var.set("🔄 Filters cleared")
        except Exception as e:
            print(f"Failed to clear filters: {e}")

    def _show_analytics(self):
        """Show analytics dashboard."""
        try:
            # Create analytics window
            analytics_window = tk.Toplevel(self.root)
            analytics_window.title("📊 Analytics Dashboard")
            analytics_window.geometry("700x600")
            analytics_window.transient(self.root)

            # Header
            header_frame = ttk.Frame(analytics_window, padding=10)
            header_frame.pack(fill=tk.X)
            ttk.Label(header_frame, text="📊 Prompt Analytics", font=("Segoe UI", 16, "bold")).pack(
                anchor=tk.W
            )

            # Create notebook for different analytics views
            notebook = ttk.Notebook(analytics_window)
            notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Overview tab
            overview_frame = ttk.Frame(notebook, padding=10)
            notebook.add(overview_frame, text="📈 Overview")

            # Calculate statistics
            total_prompts = len(self.history_items)
            favorites_count = sum(
                1 for item in self.history_items if item.get("is_favorite", False)
            )
            total_usage = sum(item.get("usage_count", 0) for item in self.history_items)
            avg_length = (
                sum(
                    item.get("length", len(item.get("full_text", "")))
                    for item in self.history_items
                )
                / total_prompts
                if total_prompts > 0
                else 0
            )

            # Stats grid
            stats_frame = ttk.Frame(overview_frame)
            stats_frame.pack(fill=tk.X, pady=10)

            # Create stat boxes
            stats = [
                ("📝 Total Prompts", str(total_prompts)),
                ("⭐ Favorites", str(favorites_count)),
                ("↻ Total Usage", str(total_usage)),
                ("📏 Avg Length", f"{int(avg_length)} chars"),
            ]

            for i, (label, value) in enumerate(stats):
                stat_box = ttk.Frame(stats_frame, relief="solid", borderwidth=1, padding=10)
                stat_box.grid(row=0, column=i, padx=5, sticky="ew")
                stats_frame.columnconfigure(i, weight=1)

                ttk.Label(stat_box, text=label, font=("", 9)).pack()
                ttk.Label(stat_box, text=value, font=("", 14, "bold")).pack()

            # Top tags
            ttk.Label(overview_frame, text="🏷️ Top Tags", font=("", 12, "bold")).pack(
                anchor=tk.W, pady=(20, 5)
            )
            tags_frame = ttk.Frame(overview_frame)
            tags_frame.pack(fill=tk.BOTH, expand=True, pady=5)

            # Count tag usage
            tag_counts = {}
            for item in self.history_items:
                for tag in item.get("tags", []):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

            # Display top tags
            if tag_counts:
                sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
                for tag, count in sorted_tags:
                    tag_row = ttk.Frame(tags_frame)
                    tag_row.pack(fill=tk.X, pady=2)
                    ttk.Label(tag_row, text=f"🏷️ {tag}:", width=20).pack(side=tk.LEFT)
                    ttk.Label(tag_row, text=f"{count} prompts").pack(side=tk.LEFT)
            else:
                ttk.Label(tags_frame, text="No tags found").pack()

            # Top Used tab
            top_used_frame = ttk.Frame(notebook, padding=10)
            notebook.add(top_used_frame, text="🔥 Most Used")

            ttk.Label(top_used_frame, text="Top 10 Most Used Prompts", font=("", 12, "bold")).pack(
                anchor=tk.W, pady=(0, 10)
            )

            # Sort by usage count
            top_used = sorted(
                self.history_items, key=lambda x: x.get("usage_count", 0), reverse=True
            )[:10]

            if top_used:
                for i, item in enumerate(top_used, 1):
                    usage_count = item.get("usage_count", 0)
                    if usage_count > 0:
                        item_frame = ttk.Frame(top_used_frame)
                        item_frame.pack(fill=tk.X, pady=5)

                        ttk.Label(item_frame, text=f"{i}.", font=("", 10, "bold"), width=3).pack(
                            side=tk.LEFT
                        )
                        ttk.Label(item_frame, text=item["preview"][:60] + "...").pack(
                            side=tk.LEFT, fill=tk.X, expand=True
                        )
                        ttk.Label(item_frame, text=f"↻ {usage_count}", foreground="#3b82f6").pack(
                            side=tk.RIGHT
                        )
            else:
                ttk.Label(top_used_frame, text="No usage data yet").pack()

            # Recent Activity tab
            recent_frame = ttk.Frame(notebook, padding=10)
            notebook.add(recent_frame, text="📅 Recent Activity")

            ttk.Label(recent_frame, text="Last 7 Days Activity", font=("", 12, "bold")).pack(
                anchor=tk.W, pady=(0, 10)
            )

            # Count prompts by day
            from collections import defaultdict

            daily_counts = defaultdict(int)
            now = datetime.now()

            for item in self.history_items:
                try:
                    item_date = datetime.fromisoformat(item["timestamp"])
                    days_ago = (now - item_date).days
                    if days_ago < 7:
                        day_name = item_date.strftime("%A")
                        daily_counts[day_name] += 1
                except Exception:
                    pass

            # Display daily activity
            if daily_counts:
                max_count = max(daily_counts.values())
                for day in [
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                ]:
                    count = daily_counts.get(day, 0)
                    day_frame = ttk.Frame(recent_frame)
                    day_frame.pack(fill=tk.X, pady=3)

                    ttk.Label(day_frame, text=f"{day}:", width=12).pack(side=tk.LEFT)

                    # Simple bar chart
                    bar_width = int((count / max_count * 300)) if max_count > 0 else 0
                    canvas = tk.Canvas(day_frame, width=300, height=20, bg="white")
                    canvas.pack(side=tk.LEFT, padx=5)
                    if bar_width > 0:
                        canvas.create_rectangle(0, 0, bar_width, 20, fill="#3b82f6", outline="")

                    ttk.Label(day_frame, text=str(count)).pack(side=tk.LEFT)
            else:
                ttk.Label(recent_frame, text="No activity in the last 7 days").pack()

            # Close button
            btn_frame = ttk.Frame(analytics_window, padding=10)
            btn_frame.pack(fill=tk.X)
            ttk.Button(btn_frame, text="❌ Close", command=analytics_window.destroy).pack(
                side=tk.RIGHT
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show analytics: {e}")

    def _export_data(self, data_type="all"):
        """Export data to JSON file."""
        try:
            # Prepare data based on type
            if data_type == "all":
                export_data = {
                    "version": "2.0.43",
                    "export_date": datetime.now().isoformat(),
                    "history": self.history_items,
                    "tags": self.tags,
                    "snippets": self.snippets,
                    "ui_settings": {
                        "theme": self.current_theme,
                    },
                }
                default_filename = f"promptc_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                title = "Export All Data"
            elif data_type == "history":
                export_data = {
                    "version": "2.0.43",
                    "export_date": datetime.now().isoformat(),
                    "history": self.history_items,
                }
                default_filename = (
                    f"promptc_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )
                title = "Export History"
            elif data_type == "tags":
                export_data = {
                    "version": "2.0.43",
                    "export_date": datetime.now().isoformat(),
                    "tags": self.tags,
                }
                default_filename = f"promptc_tags_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                title = "Export Tags"
            else:
                messagebox.showerror("Error", f"Unknown data type: {data_type}")
                return

            # Ask for save location
            filepath = filedialog.asksaveasfilename(
                title=title,
                defaultextension=".json",
                initialfile=default_filename,
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            )

            if not filepath:
                return

            # Save to file
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            messagebox.showinfo(
                "Export Successful",
                f"Data exported successfully to:\n{filepath}\n\n"
                f"Items exported: {len(export_data.get('history', []))} prompts, "
                f"{len(export_data.get('tags', []))} tags, "
                f"{len(export_data.get('snippets', []))} snippets",
            )
            self.status_var.set(f"✅ Exported to {Path(filepath).name}")

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export data: {e}")

    def _import_data(self):
        """Import data from JSON file."""
        try:
            # Ask for file
            filepath = filedialog.askopenfilename(
                title="Import Data",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            )

            if not filepath:
                return

            # Load file
            with open(filepath, "r", encoding="utf-8") as f:
                import_data = json.load(f)

            # Validate structure
            if not isinstance(import_data, dict):
                messagebox.showerror("Import Error", "Invalid file format: Expected JSON object")
                return

            # Check version (optional, for future compatibility)
            version = import_data.get("version", "unknown")

            # Ask merge or replace
            merge_choice = messagebox.askyesnocancel(
                "Import Mode",
                f"Import file version: {version}\n"
                f"Export date: {import_data.get('export_date', 'unknown')}\n\n"
                "Choose import mode:\n\n"
                "• YES = Merge with existing data (keep both)\n"
                "• NO = Replace existing data (overwrite)\n"
                "• CANCEL = Abort import",
            )

            if merge_choice is None:  # Cancel
                return

            merge_mode = merge_choice  # True = merge, False = replace

            # Import history
            if "history" in import_data:
                imported_history = import_data["history"]
                if not isinstance(imported_history, list):
                    messagebox.showerror("Import Error", "Invalid history format")
                    return

                if merge_mode:
                    # Merge: Add only new items (check by timestamp + text)
                    existing_keys = {
                        (item.get("timestamp"), item.get("full_text"))
                        for item in self.history_items
                    }
                    new_items = [
                        item
                        for item in imported_history
                        if (item.get("timestamp"), item.get("full_text")) not in existing_keys
                    ]
                    self.history_items.extend(new_items)
                    added_count = len(new_items)
                else:
                    # Replace
                    self.history_items = imported_history
                    added_count = len(imported_history)

                # Save to file
                with open(self.history_path, "w", encoding="utf-8") as f:
                    json.dump(self.history_items, f, indent=2, ensure_ascii=False)

                self._refresh_history()

            # Import tags
            if "tags" in import_data:
                imported_tags = import_data["tags"]
                if not isinstance(imported_tags, list):
                    messagebox.showerror("Import Error", "Invalid tags format")
                    return

                if merge_mode:
                    # Merge: Add only new tags
                    existing_names = {tag["name"] for tag in self.tags}
                    new_tags = [tag for tag in imported_tags if tag["name"] not in existing_names]
                    self.tags.extend(new_tags)
                    tags_added = len(new_tags)
                else:
                    # Replace
                    self.tags = imported_tags
                    tags_added = len(imported_tags)

                # Save to file
                with open(self.tags_path, "w", encoding="utf-8") as f:
                    json.dump(self.tags, f, indent=2, ensure_ascii=False)

                self._update_tag_filters()

            # Import snippets
            if "snippets" in import_data:
                imported_snippets = import_data["snippets"]
                if not isinstance(imported_snippets, list):
                    messagebox.showerror("Import Error", "Invalid snippets format")
                    return

                if merge_mode:
                    # Merge: Add only new snippets
                    existing_names = {snip["name"] for snip in self.snippets}
                    new_snippets = [
                        snip for snip in imported_snippets if snip["name"] not in existing_names
                    ]
                    self.snippets.extend(new_snippets)
                    snippets_added = len(new_snippets)
                else:
                    # Replace
                    self.snippets = imported_snippets
                    snippets_added = len(imported_snippets)

                # Save to file
                with open(self.snippets_path, "w", encoding="utf-8") as f:
                    json.dump(self.snippets, f, indent=2, ensure_ascii=False)

                self._refresh_snippets()

            # Import UI settings (optional)
            if "ui_settings" in import_data and merge_mode is False:
                ui_settings = import_data["ui_settings"]
                if "theme" in ui_settings and ui_settings["theme"] != self.current_theme:
                    self.toggle_theme()

            mode_text = "merged" if merge_mode else "replaced"
            messagebox.showinfo(
                "Import Successful",
                f"Data {mode_text} successfully!\n\n"
                f"History: {added_count if 'history' in import_data else 0} items\n"
                f"Tags: {tags_added if 'tags' in import_data else 0} tags\n"
                f"Snippets: {snippets_added if 'snippets' in import_data else 0} snippets",
            )
            self.status_var.set(f"✅ Imported from {Path(filepath).name}")

        except json.JSONDecodeError as e:
            messagebox.showerror("Import Error", f"Invalid JSON file: {e}")
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import data: {e}")

    def _auto_backup(self):
        """Create automatic backup on app close."""
        try:
            # Create backups directory
            backup_dir = Path.home() / ".promptc_backups"
            backup_dir.mkdir(exist_ok=True)

            # Create backup file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"auto_backup_{timestamp}.json"

            # Prepare backup data
            backup_data = {
                "version": "2.0.43",
                "backup_date": datetime.now().isoformat(),
                "backup_type": "auto",
                "history": self.history_items,
                "tags": self.tags,
                "snippets": self.snippets,
                "ui_settings": {
                    "theme": self.current_theme,
                },
            }

            # Save backup
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)

            # Keep only last 5 backups
            backup_files = sorted(backup_dir.glob("auto_backup_*.json"))
            if len(backup_files) > 5:
                for old_backup in backup_files[:-5]:
                    old_backup.unlink()

            print(f"Auto-backup created: {backup_file.name}")

        except Exception as e:
            print(f"Auto-backup failed: {e}")

    def _restore_backup(self):
        """Restore from automatic backup."""
        try:
            backup_dir = Path.home() / ".promptc_backups"
            if not backup_dir.exists():
                messagebox.showinfo("No Backups", "No automatic backups found.")
                return

            # List available backups
            backup_files = sorted(backup_dir.glob("auto_backup_*.json"), reverse=True)
            if not backup_files:
                messagebox.showinfo("No Backups", "No automatic backups found.")
                return

            # Create selection dialog
            restore_window = tk.Toplevel(self.root)
            restore_window.title("♻️ Restore Backup")
            restore_window.geometry("600x400")
            restore_window.transient(self.root)

            ttk.Label(
                restore_window, text="Select a backup to restore:", font=("", 11, "bold")
            ).pack(padx=10, pady=10, anchor=tk.W)

            # Listbox with backups
            list_frame = ttk.Frame(restore_window)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

            scrollbar = ttk.Scrollbar(list_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            backup_listbox = tk.Listbox(
                list_frame, yscrollcommand=scrollbar.set, selectmode=tk.SINGLE
            )
            backup_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=backup_listbox.yview)

            # Populate list
            for backup_file in backup_files:
                # Parse timestamp from filename
                try:
                    timestamp_str = backup_file.stem.replace("auto_backup_", "")
                    timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    display_name = f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {backup_file.name}"
                except Exception:
                    display_name = backup_file.name
                backup_listbox.insert(tk.END, display_name)

            # Selected backup info
            info_var = tk.StringVar(value="Select a backup to see details")
            info_label = ttk.Label(restore_window, textvariable=info_var, foreground="#666")
            info_label.pack(padx=10, pady=(0, 10))

            def on_select(event):
                selection = backup_listbox.curselection()
                if not selection:
                    return
                idx = selection[0]
                backup_file = backup_files[idx]

                # Load backup to show details
                try:
                    with open(backup_file, "r", encoding="utf-8") as f:
                        backup_data = json.load(f)

                    history_count = len(backup_data.get("history", []))
                    tags_count = len(backup_data.get("tags", []))
                    snippets_count = len(backup_data.get("snippets", []))

                    info_var.set(
                        f"📊 {history_count} prompts, {tags_count} tags, {snippets_count} snippets"
                    )
                except Exception as e:
                    info_var.set(f"Error reading backup: {e}")

            backup_listbox.bind("<<ListboxSelect>>", on_select)

            # Buttons
            btn_frame = ttk.Frame(restore_window)
            btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            def do_restore():
                selection = backup_listbox.curselection()
                if not selection:
                    messagebox.showwarning("No Selection", "Please select a backup to restore.")
                    return

                idx = selection[0]
                backup_file = backup_files[idx]

                # Confirm
                confirm = messagebox.askyesno(
                    "Confirm Restore",
                    f"Restore from backup:\n{backup_file.name}\n\n"
                    "This will replace your current data.\n"
                    "Continue?",
                )

                if not confirm:
                    return

                try:
                    # Load backup
                    with open(backup_file, "r", encoding="utf-8") as f:
                        backup_data = json.load(f)

                    # Restore history
                    if "history" in backup_data:
                        self.history_items = backup_data["history"]
                        with open(self.history_path, "w", encoding="utf-8") as f:
                            json.dump(self.history_items, f, indent=2, ensure_ascii=False)
                        self._refresh_history()

                    # Restore tags
                    if "tags" in backup_data:
                        self.tags = backup_data["tags"]
                        with open(self.tags_path, "w", encoding="utf-8") as f:
                            json.dump(self.tags, f, indent=2, ensure_ascii=False)
                        self._update_tag_filters()

                    # Restore snippets
                    if "snippets" in backup_data:
                        self.snippets = backup_data["snippets"]
                        with open(self.snippets_path, "w", encoding="utf-8") as f:
                            json.dump(self.snippets, f, indent=2, ensure_ascii=False)
                        self._refresh_snippets()

                    messagebox.showinfo("Restore Successful", "Data restored successfully!")
                    restore_window.destroy()
                    self.status_var.set(f"✅ Restored from {backup_file.name}")

                except Exception as e:
                    messagebox.showerror("Restore Error", f"Failed to restore backup: {e}")

            ttk.Button(btn_frame, text="♻️ Restore", command=do_restore).pack(
                side=tk.LEFT, padx=(0, 5)
            )
            ttk.Button(btn_frame, text="❌ Cancel", command=restore_window.destroy).pack(
                side=tk.LEFT
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open restore dialog: {e}")

    def _show_settings(self):
        """Show UI customization settings dialog."""
        try:
            settings_window = tk.Toplevel(self.root)
            settings_window.title("⚙️ UI Settings")
            settings_window.geometry("550x600")
            settings_window.transient(self.root)

            # Header
            header_frame = ttk.Frame(settings_window, padding=10)
            header_frame.pack(fill=tk.X)
            ttk.Label(header_frame, text="⚙️ UI Customization", font=("Segoe UI", 14, "bold")).pack(
                anchor=tk.W
            )
            ttk.Label(header_frame, text="Personalize your workspace", foreground="#666").pack(
                anchor=tk.W
            )

            # Create notebook for settings categories
            notebook = ttk.Notebook(settings_window)
            notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Appearance Tab
            appearance_frame = ttk.Frame(notebook, padding=15)
            notebook.add(appearance_frame, text="🎨 Appearance")

            # Theme selection
            ttk.Label(appearance_frame, text="Theme:", font=("", 10, "bold")).pack(
                anchor=tk.W, pady=(0, 5)
            )
            theme_frame = ttk.Frame(appearance_frame)
            theme_frame.pack(fill=tk.X, pady=(0, 15))

            current_theme = tk.StringVar(value=self.current_theme)
            ttk.Radiobutton(
                theme_frame, text="☀️ Light", variable=current_theme, value="light"
            ).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Radiobutton(theme_frame, text="🌙 Dark", variable=current_theme, value="dark").pack(
                side=tk.LEFT
            )

            # Accent color selection
            ttk.Label(appearance_frame, text="Accent Color:", font=("", 10, "bold")).pack(
                anchor=tk.W, pady=(10, 5)
            )
            accent_frame = ttk.Frame(appearance_frame)
            accent_frame.pack(fill=tk.X, pady=(0, 15))

            accent_colors = {
                "Blue": "#3b82f6",
                "Green": "#10b981",
                "Purple": "#8b5cf6",
                "Pink": "#ec4899",
                "Orange": "#f59e0b",
                "Red": "#ef4444",
            }

            current_accent = tk.StringVar(value=self.accent_color)

            color_buttons_frame = ttk.Frame(accent_frame)
            color_buttons_frame.pack(fill=tk.X)

            for i, (name, color) in enumerate(accent_colors.items()):
                btn_frame = ttk.Frame(color_buttons_frame)
                btn_frame.pack(side=tk.LEFT, padx=5)

                color_canvas = tk.Canvas(
                    btn_frame, width=30, height=30, bg="white", highlightthickness=2
                )
                color_canvas.pack()
                color_canvas.create_rectangle(2, 2, 28, 28, fill=color, outline="")

                ttk.Radiobutton(
                    btn_frame,
                    text=name,
                    variable=current_accent,
                    value=color,
                    command=lambda c=color, canvas=color_canvas: self._preview_accent_color(
                        canvas, c
                    ),
                ).pack()

                # Highlight selected
                if color == self.accent_color:
                    color_canvas.config(highlightbackground=color, highlightthickness=3)

            # Font size selection
            ttk.Label(appearance_frame, text="Font Size:", font=("", 10, "bold")).pack(
                anchor=tk.W, pady=(10, 5)
            )
            font_frame = ttk.Frame(appearance_frame)
            font_frame.pack(fill=tk.X, pady=(0, 15))

            current_font_size = tk.StringVar(value=self.font_size)
            ttk.Radiobutton(
                font_frame, text="Small", variable=current_font_size, value="small"
            ).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Radiobutton(
                font_frame, text="Medium", variable=current_font_size, value="medium"
            ).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Radiobutton(
                font_frame, text="Large", variable=current_font_size, value="large"
            ).pack(side=tk.LEFT)

            # View mode selection
            ttk.Label(appearance_frame, text="View Mode:", font=("", 10, "bold")).pack(
                anchor=tk.W, pady=(10, 5)
            )
            view_frame = ttk.Frame(appearance_frame)
            view_frame.pack(fill=tk.X, pady=(0, 15))

            current_view_mode = tk.StringVar(value=self.view_mode)
            ttk.Radiobutton(
                view_frame, text="Compact", variable=current_view_mode, value="compact"
            ).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Radiobutton(
                view_frame, text="Comfortable", variable=current_view_mode, value="comfortable"
            ).pack(side=tk.LEFT)

            # Preview area
            preview_frame = ttk.LabelFrame(appearance_frame, text="Preview", padding=10)
            preview_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

            preview_text = tk.Text(preview_frame, height=4, wrap=tk.WORD)
            preview_text.pack(fill=tk.BOTH, expand=True)
            preview_text.insert(
                "1.0",
                "This is a sample text preview.\nYou can see how your settings will look here.",
            )
            preview_text.config(state=tk.DISABLED)

            # Behavior Tab
            behavior_frame = ttk.Frame(notebook, padding=15)
            notebook.add(behavior_frame, text="⚡ Behavior")

            ttk.Label(behavior_frame, text="Window Settings:", font=("", 10, "bold")).pack(
                anchor=tk.W, pady=(0, 5)
            )

            remember_size = tk.BooleanVar(value=True)
            ttk.Checkbutton(
                behavior_frame,
                text="Remember window size and position",
                variable=remember_size,
            ).pack(anchor=tk.W, pady=5)

            remember_sidebar = tk.BooleanVar(value=True)
            ttk.Checkbutton(
                behavior_frame,
                text="Remember sidebar width",
                variable=remember_sidebar,
            ).pack(anchor=tk.W, pady=5)

            ttk.Separator(behavior_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)

            ttk.Label(behavior_frame, text="Sidebar Settings:", font=("", 10, "bold")).pack(
                anchor=tk.W, pady=(0, 5)
            )

            auto_refresh = tk.BooleanVar(value=True)
            ttk.Checkbutton(
                behavior_frame,
                text="Auto-refresh history on generate",
                variable=auto_refresh,
            ).pack(anchor=tk.W, pady=5)

            show_usage_count = tk.BooleanVar(value=True)
            ttk.Checkbutton(
                behavior_frame,
                text="Show usage count indicators (↻n)",
                variable=show_usage_count,
            ).pack(anchor=tk.W, pady=5)

            # About Tab
            about_frame = ttk.Frame(notebook, padding=15)
            notebook.add(about_frame, text="ℹ️ About")

            ttk.Label(about_frame, text="Prompt Compiler", font=("", 14, "bold")).pack(pady=(0, 5))
            ttk.Label(about_frame, text="Version 2.0.44", foreground="#666").pack(pady=(0, 15))

            about_text = tk.Text(about_frame, height=10, wrap=tk.WORD, relief=tk.FLAT)
            about_text.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
            about_text.insert(
                "1.0",
                "An offline desktop UI for compiling and optimizing prompts.\n\n"
                "Features:\n"
                "• Advanced analytics and filtering\n"
                "• Tags and snippets system\n"
                "• Export/Import with auto-backup\n"
                "• Customizable UI themes\n"
                "• Usage tracking and insights\n\n"
                "For more information, visit the documentation.",
            )
            about_text.config(state=tk.DISABLED)

            # Action buttons
            btn_frame = ttk.Frame(settings_window, padding=10)
            btn_frame.pack(fill=tk.X)

            def apply_settings():
                try:
                    # Apply theme
                    if current_theme.get() != self.current_theme:
                        self.apply_theme(current_theme.get())

                    # Apply accent color
                    old_accent = self.accent_color
                    self.accent_color = current_accent.get()
                    if old_accent != self.accent_color:
                        self._apply_accent_color()

                    # Apply font size
                    old_font_size = self.font_size
                    self.font_size = current_font_size.get()
                    if old_font_size != self.font_size:
                        self._apply_font_size()

                    # Apply view mode
                    old_view_mode = self.view_mode
                    self.view_mode = current_view_mode.get()
                    if old_view_mode != self.view_mode:
                        self._apply_view_mode()

                    # Save settings
                    self._save_settings()

                    messagebox.showinfo(
                        "Settings Applied", "Your settings have been applied successfully!"
                    )
                    settings_window.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to apply settings: {e}")

            ttk.Button(btn_frame, text="✅ Apply", command=apply_settings).pack(
                side=tk.RIGHT, padx=(5, 0)
            )
            ttk.Button(btn_frame, text="❌ Cancel", command=settings_window.destroy).pack(
                side=tk.RIGHT
            )

            def reset_defaults():
                if messagebox.askyesno("Reset Settings", "Reset all settings to default values?"):
                    current_theme.set("light")
                    current_accent.set("#3b82f6")
                    current_font_size.set("medium")
                    current_view_mode.set("comfortable")

            ttk.Button(btn_frame, text="↺ Reset", command=reset_defaults).pack(side=tk.LEFT)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show settings: {e}")

    def _preview_accent_color(self, canvas, color):
        """Preview accent color on canvas."""
        canvas.config(highlightbackground=color, highlightthickness=3)

    def _apply_accent_color(self):
        """Apply accent color to UI elements."""
        # This will be called when accent color changes
        # Update relevant UI elements with new accent color
        self.status_var.set("🎨 Accent color updated")

    def _apply_font_size(self):
        """Apply font size changes."""
        # Font size mapping (for future implementation)
        # sizes = {"small": 9, "medium": 10, "large": 12}
        # base_size = sizes.get(self.font_size, 10)

        # Update UI elements
        self.status_var.set(f"📏 Font size updated to {self.font_size}")

    def _apply_view_mode(self):
        """Apply view mode (compact/comfortable)."""
        # Adjust padding based on view mode (for future implementation)
        # padding = 5 if self.view_mode == "compact" else 10
        self.status_var.set(f"👁️ View mode: {self.view_mode}")

    def _shortcut_reference_data(self) -> dict[str, list[tuple[str, str]]]:
        """Return categorized keyboard shortcut data for reuse/testing."""
        return {
            "🚀 General": [
                ("Ctrl+Shift+P", "Open Command Palette"),
                ("Ctrl+K", "Show Keyboard Shortcuts"),
                ("Ctrl+,", "Open Settings"),
                ("Ctrl+Q", "Quit Application"),
                ("F11", "Toggle Fullscreen"),
            ],
            "📝 Editing": [
                ("Ctrl+Enter", "Generate Prompt"),
                ("Ctrl+L", "Clear Input"),
                ("Ctrl+A", "Select All Text"),
                ("Ctrl+C", "Copy Selected Text"),
                ("Ctrl+V", "Paste Text"),
                ("Ctrl+Z", "Undo"),
                ("Ctrl+Y", "Redo"),
            ],
            "📋 Clipboard": [
                ("Ctrl+Shift+C", "Copy System Prompt"),
                ("Ctrl+Shift+U", "Copy User Prompt"),
                ("Ctrl+Shift+E", "Copy Expanded Prompt"),
                ("Ctrl+Shift+S", "Copy JSON Schema"),
            ],
            "🔍 Navigation": [
                ("Ctrl+1", "Switch to System Prompt Tab"),
                ("Ctrl+2", "Switch to User Prompt Tab"),
                ("Ctrl+3", "Switch to Expanded Tab"),
                ("Ctrl+4", "Switch to Plan Tab"),
                ("Ctrl+5", "Switch to Schema Tab"),
                ("Ctrl+Tab", "Next Tab"),
                ("Ctrl+Shift+Tab", "Previous Tab"),
            ],
            "💾 File Operations": [
                ("Ctrl+S", "Save Current Prompt"),
                ("Ctrl+O", "Open Prompt from File"),
                ("Ctrl+E", "Export All Data"),
                ("Ctrl+I", "Import Data"),
            ],
            "📊 Views": [
                ("Ctrl+B", "Toggle Sidebar"),
                ("Ctrl+H", "Show History"),
                ("Ctrl+F", "Show Favorites"),
                ("Ctrl+T", "Show Tags"),
                ("Ctrl+R", "Show Snippets"),
                ("Ctrl+Shift+A", "Show Analytics"),
            ],
            "🎨 Appearance": [
                ("Ctrl+Shift+T", "Toggle Theme (Light/Dark)"),
                ("Ctrl+Plus", "Increase Font Size"),
                ("Ctrl+Minus", "Decrease Font Size"),
                ("Ctrl+0", "Reset Font Size"),
            ],
        }

    def _ensure_command_palette_favorites_list(self) -> None:
        if not isinstance(self.command_palette_favorites, list):
            try:
                self.command_palette_favorites = list(self.command_palette_favorites)
            except Exception:
                self.command_palette_favorites = []

    def _command_palette_favorite_set(self) -> set[str]:
        self._ensure_command_palette_favorites_list()
        return set(self.command_palette_favorites)

    def _is_command_palette_favorite(self, command_id: str) -> bool:
        return command_id in self._command_palette_favorite_set()

    def _set_command_palette_favorite(self, command_id: str, value: bool) -> None:
        if not command_id:
            return
        self._ensure_command_palette_favorites_list()
        favorites_set = self._command_palette_favorite_set()
        if value:
            if command_id not in favorites_set:
                self.command_palette_favorites.append(command_id)
        else:
            try:
                self.command_palette_favorites.remove(command_id)
            except ValueError:
                pass
        try:
            self._save_settings()
            self._update_palette_badge()
        except Exception:
            pass

    def _configure_palette_badge_style(self) -> None:
        try:
            dark = self.current_theme == "dark"
            bg = "#451a03" if dark else "#fff7ed"
            fg = "#fb923c" if dark else "#9a3412"
            border = "#ea580c" if dark else "#f97316"
            style = ttk.Style()
            style.configure(
                "PaletteBadge.TButton",
                padding=(6, 2),
                foreground=fg,
                background=bg,
                bordercolor=border,
                focusthickness=1,
                focuscolor=border,
            )
            style.map(
                "PaletteBadge.TButton",
                background=[("active", border)],
                foreground=[("active", "#ffffff")],
            )
        except Exception:
            pass

    def _ensure_palette_badge_label(self) -> ttk.Button:
        if getattr(self, "palette_badge_label", None) is None:
            try:
                parent = self.btn_palette.master
            except Exception:
                parent = None
            self._configure_palette_badge_style()
            self.palette_badge_label = ttk.Button(
                parent or self.root,
                textvariable=self.palette_badge_var,
                style="PaletteBadge.TButton",
                command=self._handle_palette_badge_click,
                takefocus=False,
            )
            try:
                self._add_tooltip(
                    self.palette_badge_label,
                    "Stale palette favorites detected. Click to clean and open the palette.",
                )
            except Exception:
                pass
        return self.palette_badge_label

    def _handle_palette_badge_click(self) -> None:
        try:
            commands = list(get_command_palette_commands())
            all_command_ids = {cmd.id for cmd in commands}
            stale_ids = compute_stale_favorites(self.command_palette_favorites, all_command_ids)

            if stale_ids:
                label_map = {cmd.id: cmd.label for cmd in commands}
                preview = [label_map.get(cid, cid) for cid in stale_ids[:3]]
                preview_text = "\n".join(f"• {lbl}" for lbl in preview)
                try:
                    messagebox.showinfo(
                        "Stale Favorites",
                        f"These favorites look stale:\n{preview_text}\n\nThey will be cleaned now and the palette will open.",
                    )
                except Exception:
                    pass

            removed = self._prune_stale_command_palette_favorites(all_command_ids)
            if removed:
                self.status_var.set(f"🧹 Removed {removed} stale favorites")
            self._show_command_palette()
        except Exception:
            try:
                self._show_command_palette()
            except Exception:
                pass

    def _update_palette_badge(self) -> None:
        try:
            if not getattr(self, "btn_palette", None):
                return
            all_command_ids = {cmd.id for cmd in get_command_palette_commands()}
            stale_ids = compute_stale_favorites(self.command_palette_favorites, all_command_ids)
            badge = getattr(self, "palette_badge_label", None)
            if not stale_ids:
                self.palette_badge_var.set("")
                if badge is not None:
                    try:
                        badge.pack_forget()
                    except Exception:
                        pass
                return
            self._configure_palette_badge_style()
            badge = self._ensure_palette_badge_label()
            self.palette_badge_var.set(f"⚠ {len(stale_ids)}")
            try:
                self.status_var.set(f"⚠️ {len(stale_ids)} stale favorite — click badge to clean")
            except Exception:
                pass
            try:
                badge.pack(side=tk.LEFT, padx=(0, 6))
            except Exception:
                pass
        except Exception:
            pass

    def _move_command_palette_favorite(self, command_id: str, direction: int) -> None:
        if not command_id or direction == 0:
            return
        try:
            idx = self.command_palette_favorites.index(command_id)
        except ValueError:
            return
        new_idx = max(0, min(len(self.command_palette_favorites) - 1, idx + direction))
        if new_idx == idx:
            return
        self.command_palette_favorites[idx], self.command_palette_favorites[new_idx] = (
            self.command_palette_favorites[new_idx],
            self.command_palette_favorites[idx],
        )
        try:
            self._save_settings()
            self._update_palette_badge()
        except Exception:
            pass

    def _prune_stale_command_palette_favorites(self, valid_ids: set[str]) -> int:
        before = len(self.command_palette_favorites)
        self.command_palette_favorites = [
            cid for cid in self.command_palette_favorites if cid in valid_ids
        ]
        removed = before - len(self.command_palette_favorites)
        if removed:
            try:
                self._save_settings()
            except Exception:
                pass
        try:
            self._update_palette_badge()
        except Exception:
            pass
        return removed

    def _record_recent_command_palette_action(self, command_id: str) -> None:
        if not command_id:
            return
        if command_id in self.command_palette_recent:
            self.command_palette_recent.remove(command_id)
        self.command_palette_recent.insert(0, command_id)
        self.command_palette_recent = self.command_palette_recent[:8]

    def _show_keyboard_shortcuts(self):
        """Show keyboard shortcuts reference dialog."""
        try:
            shortcuts_window = tk.Toplevel(self.root)
            shortcuts_window.title("⌨️ Keyboard Shortcuts")
            shortcuts_window.geometry("700x600")
            shortcuts_window.transient(self.root)

            # Header
            header_frame = ttk.Frame(shortcuts_window, padding=10)
            header_frame.pack(fill=tk.X)
            ttk.Label(
                header_frame, text="⌨️ Keyboard Shortcuts", font=("Segoe UI", 14, "bold")
            ).pack(anchor=tk.W)
            ttk.Label(
                header_frame,
                text="Speed up your workflow with keyboard shortcuts",
                foreground="#666",
            ).pack(anchor=tk.W)

            # Create main frame with scrollbar
            main_frame = ttk.Frame(shortcuts_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            canvas = tk.Canvas(main_frame, highlightthickness=0)
            scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Define shortcuts by category
            shortcuts_data = self._shortcut_reference_data()

            # Create category sections
            for category, shortcuts in shortcuts_data.items():
                # Category header
                cat_frame = ttk.Frame(scrollable_frame)
                cat_frame.pack(fill=tk.X, padx=10, pady=(15, 5))
                ttk.Label(cat_frame, text=category, font=("", 11, "bold")).pack(anchor=tk.W)
                ttk.Separator(scrollable_frame, orient="horizontal").pack(
                    fill=tk.X, padx=10, pady=(0, 5)
                )

                # Shortcuts in this category
                for key, description in shortcuts:
                    shortcut_frame = ttk.Frame(scrollable_frame)
                    shortcut_frame.pack(fill=tk.X, padx=20, pady=2)

                    # Keyboard shortcut (left)
                    key_label = ttk.Label(
                        shortcut_frame,
                        text=key,
                        font=("Consolas", 9),
                        foreground=self.accent_color,
                        width=20,
                    )
                    key_label.pack(side=tk.LEFT)

                    # Description (right)
                    desc_label = ttk.Label(shortcut_frame, text=description, foreground="#666")
                    desc_label.pack(side=tk.LEFT, padx=10)

            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Footer with close button
            footer_frame = ttk.Frame(shortcuts_window, padding=10)
            footer_frame.pack(fill=tk.X)
            ttk.Button(footer_frame, text="✓ Close", command=shortcuts_window.destroy).pack()

            # Bind mouse wheel for scrolling
            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            shortcuts_window.protocol(
                "WM_DELETE_WINDOW",
                lambda: [canvas.unbind_all("<MouseWheel>"), shortcuts_window.destroy()],
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show keyboard shortcuts: {e}")

    def _command_palette_entries(self) -> list[tuple[str, str, Callable[[], None]]]:
        """Return (id, label, action) tuples for the command palette."""
        action_map: dict[str, Callable[[], None]] = {
            "generate_prompt": lambda: self._generate_prompt(),
            "clear_input": lambda: self._clear_input(),
            "copy_system": lambda: self._copy_system_prompt(),
            "copy_user": lambda: self._copy_user_prompt(),
            "copy_expanded": lambda: self._copy_expanded_prompt(),
            "copy_schema": lambda: self._copy_schema(),
            "analyze_quality": lambda: self._analyze_prompt_quality(),
            "auto_fix": lambda: self._auto_fix_prompt_quality(),
            "apply_auto_fix": lambda: self._apply_auto_fix(),
            "template_manager": lambda: self._show_template_manager(),
            "save_prompt": lambda: self._save_current_prompt(),
            "open_prompt": lambda: self._open_prompt_file(),
            "export_data": lambda: self._export_data(),
            "import_data": lambda: self._import_data(),
            "show_analytics": lambda: self._show_analytics(),
            "toggle_favorite": lambda: self._toggle_favorite(),
            "manage_tags": lambda: self._show_tag_manager(),
            "manage_snippets": lambda: self._show_snippet_manager(),
            "show_history": lambda: self._show_history_view(),
            "keyboard_shortcuts": lambda: self._show_keyboard_shortcuts(),
            "settings": lambda: self._show_settings(),
            "toggle_theme": lambda: self._toggle_theme(),
            "toggle_sidebar": lambda: self._toggle_sidebar(),
            "quit": lambda: self.root.quit(),
        }
        entries: list[tuple[str, str, Callable[[], None]]] = []
        for command in get_command_palette_commands():
            action = action_map.get(command.id)
            if action:
                entries.append((command.id, command.label, action))
        return entries

    def _show_command_palette(self):
        """Show command palette for quick command execution."""
        try:
            try:
                self._update_palette_badge()
            except Exception:
                pass
            palette_window = tk.Toplevel(self.root)
            palette_window.title("Command Palette")
            palette_window.geometry("600x400")
            palette_window.transient(self.root)
            palette_window.grab_set()

            # Remove window decorations for modern look
            # palette_window.overrideredirect(True)  # Uncomment for frameless window

            # Center on parent
            palette_window.update_idletasks()
            x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (600 // 2)
            y = self.root.winfo_y() + 100
            palette_window.geometry(f"600x400+{x}+{y}")

            # Search entry at the top
            search_frame = ttk.Frame(palette_window, padding=10)
            search_frame.pack(fill=tk.X)

            ttk.Label(search_frame, text="🔍", font=("", 16)).pack(side=tk.LEFT, padx=(0, 5))
            search_var = tk.StringVar()
            search_entry = ttk.Entry(search_frame, textvariable=search_var, font=("", 11))
            search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            search_entry.focus()

            favorites_only_var = tk.BooleanVar(value=False)
            favorites_toggle = ttk.Checkbutton(
                search_frame,
                text="⭐ Favorites",
                variable=favorites_only_var,
                command=lambda: update_command_list(search_var.get()),
            )
            favorites_toggle.pack(side=tk.RIGHT, padx=(8, 0))

            stale_badge = None

            # Commands listbox
            list_frame = ttk.Frame(palette_window)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

            commands_listbox = tk.Listbox(
                list_frame,
                font=("", 10),
                relief=tk.FLAT,
                highlightthickness=0,
                activestyle="none",
                selectmode=tk.SINGLE,
            )
            commands_scrollbar = ttk.Scrollbar(
                list_frame, orient="vertical", command=commands_listbox.yview
            )
            commands_listbox.configure(yscrollcommand=commands_scrollbar.set)

            commands_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            commands_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Define all available commands
            all_commands = self._command_palette_entries()
            all_command_ids = {cid for cid, _label, _action in all_commands}

            stale_ids = [
                cid for cid in self.command_palette_favorites if cid not in all_command_ids
            ]

            if stale_ids:
                warning_frame = ttk.Frame(palette_window, padding=(10, 2))
                warning_frame.pack(fill=tk.X)
                ttk.Label(
                    warning_frame,
                    text="Some favorites refer to commands that no longer exist.",
                    foreground="#b45309",
                ).pack(side=tk.LEFT, padx=(0, 8))
                ttk.Button(
                    warning_frame,
                    text="🧹 Clean stale",
                    command=lambda: prune_stale_and_refresh(),
                ).pack(side=tk.LEFT)
                stale_badge = ttk.Label(search_frame, text="⚠ Stale", foreground="#b45309")
                stale_badge.pack(side=tk.RIGHT, padx=(8, 0))

            # Store filtered commands
            current_commands = []

            def update_command_list(search_term=""):
                """Update command list based on search term."""
                commands_listbox.delete(0, tk.END)
                current_commands.clear()

                search_lower = search_term.lower()
                favorites_only = favorites_only_var.get()
                filtered = []
                for cmd_id, label, action in all_commands:
                    if favorites_only and not self._is_command_palette_favorite(cmd_id):
                        continue
                    if search_lower not in label.lower():
                        continue
                    filtered.append((cmd_id, label, action))

                if not search_lower and not favorites_only and self.command_palette_recent:
                    recent_set = set(self.command_palette_recent)
                    recent_entries = [c for c in filtered if c[0] in recent_set]
                    seen = {c[0] for c in recent_entries}
                    remaining_entries = [c for c in filtered if c[0] not in seen]
                    filtered = recent_entries + remaining_entries

                for cmd_id, label, action in filtered:
                    prefix = "★ " if self._is_command_palette_favorite(cmd_id) else "   "
                    commands_listbox.insert(tk.END, f"{prefix}{label}")
                    current_commands.append((cmd_id, label, action))

                # Select first item if available
                if commands_listbox.size() > 0:
                    commands_listbox.selection_set(0)
                    commands_listbox.activate(0)
                    refresh_favorite_button()
                else:
                    refresh_favorite_button()

            def execute_selected_command():
                """Execute the selected command and close palette."""
                selection = commands_listbox.curselection()
                if selection:
                    idx = selection[0]
                    if idx < len(current_commands):
                        cmd_id, _label, action = current_commands[idx]
                        palette_window.destroy()
                        try:
                            action()
                            self._record_recent_command_palette_action(cmd_id)
                        except Exception as e:
                            messagebox.showerror("Error", f"Failed to execute command: {e}")

            def toggle_current_favorite():
                selection = commands_listbox.curselection()
                if not selection:
                    return
                idx = selection[0]
                if idx >= len(current_commands):
                    return
                cmd_id, _label, _action = current_commands[idx]
                is_fav = self._is_command_palette_favorite(cmd_id)
                self._set_command_palette_favorite(cmd_id, not is_fav)
                update_command_list(search_var.get())

            def refresh_favorite_button():
                selection = commands_listbox.curselection()
                if not selection or selection[0] >= len(current_commands):
                    fav_button.config(state=tk.DISABLED, text="☆ Add Favorite")
                    move_up_button.config(state=tk.DISABLED)
                    move_down_button.config(state=tk.DISABLED)
                    return
                cmd_id, _label, _action = current_commands[selection[0]]
                if self._is_command_palette_favorite(cmd_id):
                    fav_button.config(state=tk.NORMAL, text="★ Remove Favorite")
                    move_up_button.config(state=tk.NORMAL)
                    move_down_button.config(state=tk.NORMAL)
                else:
                    fav_button.config(state=tk.NORMAL, text="☆ Add Favorite")
                    move_up_button.config(state=tk.DISABLED)
                    move_down_button.config(state=tk.DISABLED)

            def on_search_changed(*args):
                """Called when search text changes."""
                update_command_list(search_var.get())

            search_var.trace("w", on_search_changed)

            # Initial population
            update_command_list()

            # Keyboard navigation
            def on_key_press(event):
                if event.keysym == "Escape":
                    palette_window.destroy()
                elif event.keysym == "Return":
                    execute_selected_command()
                elif event.keysym == "Down":
                    current = commands_listbox.curselection()
                    if current:
                        next_idx = min(current[0] + 1, commands_listbox.size() - 1)
                        commands_listbox.selection_clear(0, tk.END)
                        commands_listbox.selection_set(next_idx)
                        commands_listbox.activate(next_idx)
                        commands_listbox.see(next_idx)
                    return "break"
                elif event.keysym == "Up":
                    current = commands_listbox.curselection()
                    if current:
                        prev_idx = max(current[0] - 1, 0)
                        commands_listbox.selection_clear(0, tk.END)
                        commands_listbox.selection_set(prev_idx)
                        commands_listbox.activate(prev_idx)
                        commands_listbox.see(prev_idx)
                    return "break"

            search_entry.bind("<Key>", on_key_press)
            commands_listbox.bind("<Double-Button-1>", lambda e: execute_selected_command())
            commands_listbox.bind("<<ListboxSelect>>", lambda _e: refresh_favorite_button())

            # Footer info
            footer_frame = ttk.Frame(palette_window, padding=(10, 0, 10, 10))
            footer_frame.pack(fill=tk.X)

            fav_button = ttk.Button(
                footer_frame,
                text="☆ Add Favorite",
                command=toggle_current_favorite,
                state=tk.DISABLED,
                width=14,
            )
            fav_button.pack(side=tk.LEFT)

            move_up_button = ttk.Button(
                footer_frame,
                text="↑ Move Up",
                command=lambda: move_selected_favorite(-1),
                state=tk.DISABLED,
                width=10,
            )
            move_up_button.pack(side=tk.LEFT, padx=(6, 0))

            move_down_button = ttk.Button(
                footer_frame,
                text="↓ Move Down",
                command=lambda: move_selected_favorite(1),
                state=tk.DISABLED,
                width=10,
            )
            move_down_button.pack(side=tk.LEFT, padx=(4, 0))

            ttk.Label(
                footer_frame,
                text="↑↓ Navigate  •  Enter Execute  •  Esc Close  •  Favorites toggle available",
                foreground="#666",
                font=("", 9),
            ).pack(side=tk.RIGHT)

            def prune_stale_and_refresh():
                removed = self._prune_stale_command_palette_favorites(all_command_ids)
                update_command_list(search_var.get())
                if removed:
                    self.status_var.set(f"🧹 Removed {removed} stale favorites")
                else:
                    self.status_var.set("No stale favorites to remove")

            def move_selected_favorite(delta: int):
                selection = commands_listbox.curselection()
                if not selection:
                    return
                idx = selection[0]
                if idx >= len(current_commands):
                    return
                cmd_id, _label, _action = current_commands[idx]
                if not self._is_command_palette_favorite(cmd_id):
                    return
                self._move_command_palette_favorite(cmd_id, delta)
                update_command_list(search_var.get())
                # re-select the moved command
                for i, (cid, _lbl, _act) in enumerate(current_commands):
                    if cid == cmd_id:
                        commands_listbox.selection_clear(0, tk.END)
                        commands_listbox.selection_set(i)
                        commands_listbox.activate(i)
                        commands_listbox.see(i)
                        break
                refresh_favorite_button()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show command palette: {e}")

    def _show_chat_window(self):
        try:
            if getattr(self, "chat_window", None) is not None:
                try:
                    self.chat_window.deiconify()
                    self.chat_window.lift()
                    return
                except Exception:
                    self.chat_window = None
            chat = tk.Toplevel(self.root)
            chat.title("Chat (beta)")
            chat.geometry("820x620")
            chat.transient(self.root)
            self.chat_window = chat

            topbar = ttk.Frame(chat, padding=8)
            topbar.pack(fill=tk.X)
            ttk.Label(topbar, text="Provider:").pack(side=tk.LEFT)
            provider_combo = ttk.Combobox(
                topbar,
                textvariable=self.var_llm_provider,
                values=("OpenAI", "Local HTTP"),
                state="readonly",
                width=10,
            )
            provider_combo.pack(side=tk.LEFT, padx=(4, 8))

            ttk.Label(topbar, text="Model:").pack(side=tk.LEFT)
            entry_model = ttk.Entry(topbar, textvariable=self.var_model, width=18)
            entry_model.pack(side=tk.LEFT, padx=(4, 8))

            ttk.Label(topbar, text="Endpoint (Local HTTP):").pack(side=tk.LEFT)
            entry_endpoint = ttk.Entry(topbar, textvariable=self.var_local_endpoint, width=34)
            entry_endpoint.pack(side=tk.LEFT, padx=(4, 0))

            # History
            history_frame = ttk.Frame(chat, padding=(8, 4))
            history_frame.pack(fill=tk.BOTH, expand=True)
            history = tk.Text(history_frame, wrap=tk.WORD, state=tk.DISABLED, height=22)
            history.pack(fill=tk.BOTH, expand=True)

            # Prompt entry
            input_frame = ttk.Frame(chat, padding=8)
            input_frame.pack(fill=tk.X)
            ttk.Label(input_frame, text="Your message:").pack(anchor=tk.W)
            entry = tk.Text(input_frame, height=3, wrap=tk.WORD)
            entry.pack(fill=tk.X, expand=True)

            btns = ttk.Frame(chat, padding=(8, 4))
            btns.pack(fill=tk.X)
            status_label = ttk.Label(btns, textvariable=self.status_var, foreground="#555")
            status_label.pack(side=tk.RIGHT)

            def append_history(role: str, content: str):
                try:
                    history.configure(state=tk.NORMAL)
                    history.insert(tk.END, f"{role}:\n{content}\n\n")
                    history.see(tk.END)
                    history.configure(state=tk.DISABLED)
                except Exception:
                    pass

            def send_message():
                prompt_text = entry.get("1.0", tk.END).strip()
                if not prompt_text:
                    messagebox.showwarning("Chat", "Enter a message first.")
                    return

                try:
                    system, user, ir = self._prepare_llm_messages(prompt_text)
                except Exception as exc:
                    messagebox.showerror("Chat", f"Failed to prepare prompt: {exc}")
                    return

                append_history("You", prompt_text)
                entry.delete("1.0", tk.END)

                provider = (self.var_llm_provider.get() or "OpenAI").strip()
                model = (self.var_model.get() or "gpt-4o-mini").strip()
                t0 = time.time()

                if provider == "Local HTTP":
                    endpoint = (self.var_local_endpoint.get() or "").strip()
                    if not endpoint:
                        messagebox.showerror("Local LLM", "Set a local HTTP endpoint URL first.")
                        return
                    api_key = (self.var_local_api_key.get() or "").strip()
                    headers = {"Content-Type": "application/json"}
                    if api_key:
                        if api_key.lower().startswith("bearer "):
                            headers["Authorization"] = api_key
                        else:
                            headers["Authorization"] = f"Bearer {api_key}"
                    payload = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "temperature": 0.7,
                    }
                    self.status_var.set(f"Local LLM: sending ({model})...")

                    def _send_local():
                        try:
                            resp = httpx.post(endpoint, json=payload, timeout=60, headers=headers)
                            resp.raise_for_status()
                            data = resp.json()
                            content = None
                            try:
                                choices = data.get("choices")
                                if choices:
                                    msg = choices[0].get("message", {})
                                    content = msg.get("content") or choices[0].get("text")
                            except Exception:
                                content = None
                            if content is None:
                                content = json.dumps(data, ensure_ascii=False, indent=2)
                            append_history("LLM", content or "<no content>")
                            self.status_var.set("Local LLM: done")
                            try:
                                elapsed = int((time.time() - t0) * 1000)
                                load = self._compute_cognitive_load(prompt_text)
                                self.cognitive_load_var.set(f"Load: {load}")
                                self._record_analytics(
                                    prompt_text,
                                    ir,
                                    elapsed,
                                    task_type="chat",
                                    tags=["chat"],
                                )
                            except Exception:
                                pass
                        except Exception as e:
                            self.status_var.set("Local LLM: error")
                            messagebox.showerror("Local LLM", str(e))

                    self.root.after(30, _send_local)
                    return

                # OpenAI default
                if OpenAI is None:
                    messagebox.showerror(
                        "OpenAI", "Package 'openai' not installed. Run: pip install openai"
                    )
                    return
                if not os.environ.get("OPENAI_API_KEY"):
                    messagebox.showerror("OpenAI", "OPENAI_API_KEY is not set in environment.")
                    return
                self.status_var.set(f"OpenAI: sending ({model})...")

                def _send_openai():
                    try:
                        client = OpenAI()
                        resp = client.chat.completions.create(
                            model=model,
                            messages=[
                                {"role": "system", "content": system},
                                {"role": "user", "content": user},
                            ],
                            temperature=0.7,
                        )
                        try:
                            content = resp.choices[0].message.content  # type: ignore[attr-defined]
                        except Exception:
                            content = str(resp)
                        append_history("LLM", content or "<no content>")
                        self.status_var.set("OpenAI: done")
                        try:
                            elapsed = int((time.time() - t0) * 1000)
                            load = self._compute_cognitive_load(prompt_text)
                            self.cognitive_load_var.set(f"Load: {load}")
                            self._record_analytics(
                                prompt_text,
                                ir,
                                elapsed,
                                task_type="chat",
                                tags=["chat"],
                            )
                        except Exception:
                            pass
                    except Exception as e:
                        self.status_var.set("OpenAI: error")
                        messagebox.showerror("OpenAI", str(e))

                self.root.after(30, _send_openai)

            send_btn = ttk.Button(btns, text="Genişlet ve Gönder", command=send_message)
            send_btn.pack(side=tk.LEFT)

            entry.bind("<Control-Return>", lambda _e: send_message())
            entry.bind("<Control-Shift-Return>", lambda _e: send_message())

        except Exception as e:
            messagebox.showerror("Chat", f"Failed to open chat: {e}")

    def _generate_prompt(self):
        """Wrapper for generate prompt action."""
        self.on_generate()

    def _clear_input(self):
        """Wrapper for clear input action."""
        # Clear the prompt input specifically
        self.txt_prompt.delete("1.0", tk.END)
        self.status_var.set("✓ Input cleared")

    def _copy_system_prompt(self):
        """Copy system prompt to clipboard."""
        try:
            content = self.txt_system.get("1.0", tk.END).strip()
            if content:
                self.root.clipboard_clear()
                self.root.clipboard_append(content)
                self.status_var.set("📋 System prompt copied to clipboard")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy: {e}")

    def _copy_user_prompt(self):
        """Copy user prompt to clipboard."""
        try:
            content = self.txt_user.get("1.0", tk.END).strip()
            if content:
                self.root.clipboard_clear()
                self.root.clipboard_append(content)
                self.status_var.set("📋 User prompt copied to clipboard")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy: {e}")

    def _copy_expanded_prompt(self):
        """Copy expanded prompt to clipboard."""
        try:
            content = self.txt_expanded.get("1.0", tk.END).strip()
            if content:
                self.root.clipboard_clear()
                self.root.clipboard_append(content)
                self.status_var.set("📋 Expanded prompt copied to clipboard")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy: {e}")

    def _copy_schema(self):
        """Copy JSON schema to clipboard."""
        try:
            # Read schema file
            schema_path = Path("schema/ir.schema.json")
            if schema_path.exists():
                content = schema_path.read_text(encoding="utf-8")
                self.root.clipboard_clear()
                self.root.clipboard_append(content)
                self.status_var.set("📋 JSON schema copied to clipboard")
            else:
                messagebox.showwarning("Warning", "Schema file not found")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy schema: {e}")

    def _analyze_prompt_quality(self):
        """Shortcut wrapper for running quality analysis."""
        self._run_quality_check()

    def _auto_fix_prompt_quality(self):
        """Shortcut wrapper for running auto-fix."""
        self._run_auto_fix()

    def _save_current_prompt(self):
        """Wrapper for save prompt action."""
        try:
            self.on_save()
        except Exception:
            # If on_save doesn't exist, show a message
            messagebox.showinfo("Info", "Save functionality not available")

    def _open_prompt_file(self):
        """Open a prompt from file."""
        try:
            file_path = filedialog.askopenfilename(
                title="Open Prompt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            )
            if file_path:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.txt_prompt.delete("1.0", tk.END)
                    self.txt_prompt.insert("1.0", content)
                    self.status_var.set(f"📂 Opened: {os.path.basename(file_path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {e}")

    def _show_history_view(self):
        """Show history view in sidebar."""
        # Just ensure sidebar is visible and filter is cleared for history
        if not self.sidebar_visible:
            self._toggle_sidebar()
        self.status_var.set("📜 Showing history")

    def _show_favorites_view(self):
        """Show favorites view in sidebar."""
        # Just ensure sidebar is visible and activate favorites filter
        if not self.sidebar_visible:
            self._toggle_sidebar()
        self.filter_favorites_only.set(True)
        self._filter_history()
        self.status_var.set("⭐ Showing favorites")

    def _toggle_theme(self):
        """Wrapper for theme toggle."""
        self.toggle_theme()

    def _bind_keyboard_shortcuts(self):
        """Bind all keyboard shortcuts to their respective actions."""
        try:
            # Command Palette
            self.root.bind("<Control-Shift-P>", lambda e: self._show_command_palette())
            self.root.bind("<Control-Shift-p>", lambda e: self._show_command_palette())
            self.root.bind("<Alt-p>", lambda e: self._handle_palette_badge_click())
            self.root.bind("<Alt-P>", lambda e: self._handle_palette_badge_click())

            # Keyboard Shortcuts Reference
            self.root.bind("<Control-k>", lambda e: self._show_keyboard_shortcuts())
            self.root.bind("<Control-K>", lambda e: self._show_keyboard_shortcuts())

            # Settings
            self.root.bind("<Control-comma>", lambda e: self._show_settings())

            # Generate & Clear
            self.root.bind("<Control-Return>", lambda e: self._generate_prompt())
            self.root.bind("<Control-l>", lambda e: self._clear_input())
            self.root.bind("<Control-L>", lambda e: self._clear_input())

            # Copy actions
            self.root.bind("<Control-Shift-C>", lambda e: self._copy_system_prompt())
            self.root.bind("<Control-Shift-c>", lambda e: self._copy_system_prompt())
            self.root.bind("<Control-Shift-U>", lambda e: self._copy_user_prompt())
            self.root.bind("<Control-Shift-u>", lambda e: self._copy_user_prompt())
            self.root.bind("<Control-Shift-E>", lambda e: self._copy_expanded_prompt())
            self.root.bind("<Control-Shift-e>", lambda e: self._copy_expanded_prompt())
            self.root.bind("<Control-Shift-S>", lambda e: self._copy_schema())
            self.root.bind("<Control-Shift-s>", lambda e: self._copy_schema())

            # Quality coach
            self.root.bind("<Control-Shift-Q>", lambda e: self._analyze_prompt_quality())
            self.root.bind("<Control-Shift-q>", lambda e: self._analyze_prompt_quality())
            self.root.bind("<Control-Alt-Q>", lambda e: self._auto_fix_prompt_quality())
            self.root.bind("<Control-Alt-q>", lambda e: self._auto_fix_prompt_quality())

            # Tab navigation (Ctrl+1 through Ctrl+5)
            self.root.bind("<Control-Key-1>", lambda e: self.output_notebook.select(0))
            self.root.bind("<Control-Key-2>", lambda e: self.output_notebook.select(1))
            self.root.bind("<Control-Key-3>", lambda e: self.output_notebook.select(2))
            self.root.bind("<Control-Key-4>", lambda e: self.output_notebook.select(3))
            self.root.bind("<Control-Key-5>", lambda e: self.output_notebook.select(4))

            # File operations
            self.root.bind("<Control-s>", lambda e: self._save_current_prompt())
            self.root.bind("<Control-S>", lambda e: self._save_current_prompt())
            self.root.bind("<Control-o>", lambda e: self._open_prompt_file())
            self.root.bind("<Control-O>", lambda e: self._open_prompt_file())
            self.root.bind("<Control-e>", lambda e: self._export_data())
            self.root.bind("<Control-E>", lambda e: self._export_data())
            self.root.bind("<Control-i>", lambda e: self._import_data())
            self.root.bind("<Control-I>", lambda e: self._import_data())

            # Views
            self.root.bind("<Control-b>", lambda e: self._toggle_sidebar())
            self.root.bind("<Control-B>", lambda e: self._toggle_sidebar())
            self.root.bind("<Control-h>", lambda e: self._show_history_view())
            self.root.bind("<Control-H>", lambda e: self._show_history_view())
            self.root.bind("<Control-f>", lambda e: self._show_favorites_view())
            self.root.bind("<Control-F>", lambda e: self._show_favorites_view())
            self.root.bind("<Control-Shift-A>", lambda e: self._show_analytics())
            self.root.bind("<Control-Shift-a>", lambda e: self._show_analytics())

            # Theme toggle
            self.root.bind("<Control-Shift-T>", lambda e: self._toggle_theme())
            self.root.bind("<Control-Shift-t>", lambda e: self._toggle_theme())

            # Quit
            self.root.bind("<Control-q>", lambda e: self.root.quit())
            self.root.bind("<Control-Q>", lambda e: self.root.quit())

            # Templates
            self.root.bind("<Control-t>", lambda e: self._show_template_manager())
            self.root.bind("<Control-T>", lambda e: self._show_template_manager())

        except Exception as e:
            print(f"Warning: Failed to bind some keyboard shortcuts: {e}")

    # Template Management Methods

    def _show_template_manager(self):
        """Show template manager dialog."""
        try:
            manager_window = tk.Toplevel(self.root)
            manager_window.title("📋 Template Manager")
            manager_window.geometry("900x600")
            manager_window.transient(self.root)
            manager_window.grab_set()

            # Center on parent
            manager_window.update_idletasks()
            x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (900 // 2)
            y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (600 // 2)
            manager_window.geometry(f"900x600+{x}+{y}")

            # Top toolbar
            toolbar = ttk.Frame(manager_window, padding=10)
            toolbar.pack(fill=tk.X)

            ttk.Label(toolbar, text="Category:").pack(side=tk.LEFT, padx=(0, 5))

            categories = ["All"] + self.template_registry.get_categories()
            category_var = tk.StringVar(value="All")
            category_combo = ttk.Combobox(
                toolbar,
                textvariable=category_var,
                values=categories,
                state="readonly",
                width=20,
            )
            category_combo.pack(side=tk.LEFT, padx=(0, 10))

            ttk.Label(toolbar, text="Search:").pack(side=tk.LEFT, padx=(10, 5))
            search_var = tk.StringVar()
            search_entry = ttk.Entry(toolbar, textvariable=search_var, width=30)
            search_entry.pack(side=tk.LEFT, padx=(0, 10))

            btn_new = ttk.Button(
                toolbar,
                text="➕ New Template",
                command=lambda: self._edit_template(None, manager_window),
            )
            btn_new.pack(side=tk.LEFT, padx=5)

            btn_refresh = ttk.Button(
                toolbar, text="🔄 Refresh", command=lambda: update_template_list()
            )
            btn_refresh.pack(side=tk.LEFT, padx=5)

            # Template list (left side)
            list_frame = ttk.Frame(manager_window)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

            # Listbox with scrollbar
            list_container = ttk.Frame(list_frame)
            list_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            templates_listbox = tk.Listbox(
                list_container,
                font=("", 10),
                relief=tk.FLAT,
                highlightthickness=1,
                selectmode=tk.SINGLE,
            )
            list_scrollbar = ttk.Scrollbar(
                list_container, orient="vertical", command=templates_listbox.yview
            )
            templates_listbox.configure(yscrollcommand=list_scrollbar.set)

            templates_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Details panel (right side)
            details_frame = ttk.LabelFrame(list_frame, text="Template Details", padding=10)
            details_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

            # Template name
            name_label = ttk.Label(details_frame, text="", font=("", 12, "bold"))
            name_label.pack(anchor=tk.W, pady=(0, 5))

            # Category and tags
            meta_label = ttk.Label(details_frame, text="", foreground="#666")
            meta_label.pack(anchor=tk.W, pady=(0, 10))

            # Description
            desc_label = ttk.Label(details_frame, text="", wraplength=350, justify=tk.LEFT)
            desc_label.pack(anchor=tk.W, pady=(0, 10))

            # Variables
            var_frame = ttk.LabelFrame(details_frame, text="Variables", padding=5)
            var_frame.pack(fill=tk.X, pady=(0, 10))
            var_text = tk.Text(var_frame, height=6, wrap=tk.WORD, font=("", 9))
            var_text.pack(fill=tk.BOTH, expand=True)
            var_text.config(state=tk.DISABLED)

            # Template content preview
            content_frame = ttk.LabelFrame(details_frame, text="Template Content", padding=5)
            content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            content_text = tk.Text(content_frame, wrap=tk.WORD, font=("", 9))
            content_text.pack(fill=tk.BOTH, expand=True)
            content_text.config(state=tk.DISABLED)

            # Action buttons
            action_frame = ttk.Frame(details_frame)
            action_frame.pack(fill=tk.X)

            btn_use = ttk.Button(
                action_frame,
                text="✅ Use Template",
                command=lambda: self._use_selected_template(templates_listbox, manager_window),
            )
            btn_use.pack(side=tk.LEFT, padx=(0, 5))

            btn_edit = ttk.Button(
                action_frame,
                text="✏️ Edit",
                command=lambda: self._edit_selected_template(templates_listbox, manager_window),
            )
            btn_edit.pack(side=tk.LEFT, padx=5)

            btn_delete = ttk.Button(
                action_frame,
                text="🗑️ Delete",
                command=lambda: self._delete_selected_template(templates_listbox),
            )
            btn_delete.pack(side=tk.LEFT, padx=5)

            # Store current templates for list
            current_templates = []

            def update_template_list():
                """Update template list based on category and search."""
                templates_listbox.delete(0, tk.END)
                current_templates.clear()

                category = category_var.get()
                search = search_var.get().lower()

                # Get templates
                if category == "All":
                    templates = self.template_registry.list_templates()
                else:
                    templates = self.template_registry.list_templates(category=category)

                # Filter by search
                if search:
                    templates = [
                        t
                        for t in templates
                        if search in t.name.lower() or search in t.description.lower()
                    ]

                # Populate list
                for template in templates:
                    templates_listbox.insert(tk.END, f"{template.name} ({template.category})")
                    current_templates.append(template)

                # Select first if available
                if current_templates:
                    templates_listbox.selection_set(0)
                    show_template_details(current_templates[0])

            def show_template_details(template: PromptTemplate):
                """Show details of selected template."""
                name_label.config(text=template.name)

                tags_str = ", ".join(template.tags) if template.tags else "No tags"
                meta_label.config(text=f"Category: {template.category} | Tags: {tags_str}")

                desc_label.config(text=template.description)

                # Show variables
                var_text.config(state=tk.NORMAL)
                var_text.delete("1.0", tk.END)
                if template.variables:
                    for var in template.variables:
                        req = "Required" if var.required else "Optional"
                        default = f" (default: {var.default})" if var.default else ""
                        var_text.insert(
                            tk.END, f"• {var.name} - {req}{default}\n  {var.description}\n\n"
                        )
                else:
                    var_text.insert(tk.END, "No variables defined")
                var_text.config(state=tk.DISABLED)

                # Show content
                content_text.config(state=tk.NORMAL)
                content_text.delete("1.0", tk.END)
                content_text.insert(tk.END, template.template_text)
                content_text.config(state=tk.DISABLED)

            def on_template_select(event):
                """Handle template selection."""
                selection = templates_listbox.curselection()
                if selection and current_templates:
                    idx = selection[0]
                    if idx < len(current_templates):
                        show_template_details(current_templates[idx])

            templates_listbox.bind("<<ListboxSelect>>", on_template_select)
            category_combo.bind("<<ComboboxSelected>>", lambda e: update_template_list())
            search_var.trace("w", lambda *args: update_template_list())

            # Initial load
            update_template_list()

            # Store reference for other methods
            self._template_manager_window = manager_window
            self._current_templates_list = current_templates
            self._templates_listbox = templates_listbox

            # Add refresh callback for child windows
            manager_window._refresh_templates = update_template_list

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show template manager: {e}")

    def _use_selected_template(self, listbox: tk.Listbox, manager_window: tk.Toplevel):
        """Apply selected template to prompt area."""
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("Template Manager", "Please select a template first")
            return

        idx = selection[0]
        if idx >= len(self._current_templates_list):
            return

        template = self._current_templates_list[idx]

        # If template has variables, show dialog to fill them
        if template.variables:
            self._show_variable_dialog(template, manager_window)
        else:
            # No variables, just insert template
            self.txt_prompt.delete("1.0", tk.END)
            self.txt_prompt.insert("1.0", template.template_text)
            self._update_prompt_stats()
            manager_window.destroy()
            self.status_var.set(f"✅ Applied template: {template.name}")

    def _show_variable_dialog(self, template: PromptTemplate, parent_window: tk.Toplevel):
        """Show dialog to fill template variables."""
        try:
            var_dialog = tk.Toplevel(parent_window)
            var_dialog.title(f"Fill Variables - {template.name}")
            var_dialog.geometry("600x500")
            var_dialog.transient(parent_window)
            var_dialog.grab_set()

            # Center on parent
            var_dialog.update_idletasks()
            x = parent_window.winfo_x() + (parent_window.winfo_width() // 2) - (600 // 2)
            y = parent_window.winfo_y() + (parent_window.winfo_height() // 2) - (500 // 2)
            var_dialog.geometry(f"600x500+{x}+{y}")

            # Header
            header = ttk.Frame(var_dialog, padding=10)
            header.pack(fill=tk.X)
            ttk.Label(
                header,
                text=f"Fill in the template variables for: {template.name}",
                font=("", 11, "bold"),
            ).pack(anchor=tk.W)
            ttk.Label(header, text=template.description, wraplength=550).pack(
                anchor=tk.W, pady=(5, 0)
            )

            # Scrollable variable inputs
            canvas_frame = ttk.Frame(var_dialog)
            canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            canvas = tk.Canvas(canvas_frame)
            scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Create input fields for each variable
            variable_entries = {}

            for var in template.variables:
                var_frame = ttk.LabelFrame(scrollable_frame, text=var.name, padding=10)
                var_frame.pack(fill=tk.X, padx=5, pady=5)

                # Description
                ttk.Label(var_frame, text=var.description, wraplength=500).pack(anchor=tk.W)

                # Required/Optional indicator
                req_text = "Required" if var.required else "Optional"
                req_label = ttk.Label(var_frame, text=req_text, foreground="#666", font=("", 8))
                req_label.pack(anchor=tk.W, pady=(2, 0))

                # Input field (Text widget for multiline support)
                input_text = tk.Text(var_frame, height=3, wrap=tk.WORD)
                input_text.pack(fill=tk.X, pady=(5, 0))

                # Set default value if available
                if var.default:
                    input_text.insert("1.0", var.default)
                elif var.name in template.example_values:
                    input_text.insert("1.0", template.example_values[var.name])

                variable_entries[var.name] = input_text

            # Action buttons
            button_frame = ttk.Frame(var_dialog, padding=10)
            button_frame.pack(fill=tk.X)

            def apply_template():
                """Apply template with filled variables."""
                try:
                    # Collect variable values
                    values = {}
                    for var_name, text_widget in variable_entries.items():
                        value = text_widget.get("1.0", tk.END).strip()
                        values[var_name] = value

                    # Render template
                    rendered = template.render(values)

                    # Insert into prompt area
                    self.txt_prompt.delete("1.0", tk.END)
                    self.txt_prompt.insert("1.0", rendered)
                    self._update_prompt_stats()

                    # Close dialogs
                    var_dialog.destroy()
                    parent_window.destroy()

                    self.status_var.set(f"✅ Applied template: {template.name}")

                except ValueError as e:
                    messagebox.showerror("Validation Error", str(e))
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to apply template: {e}")

            ttk.Button(button_frame, text="✅ Apply Template", command=apply_template).pack(
                side=tk.LEFT, padx=5
            )
            ttk.Button(button_frame, text="❌ Cancel", command=var_dialog.destroy).pack(
                side=tk.LEFT, padx=5
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show variable dialog: {e}")

    def _edit_selected_template(self, listbox: tk.Listbox, parent_window: tk.Toplevel):
        """Edit selected template."""
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("Template Manager", "Please select a template first")
            return

        idx = selection[0]
        if idx >= len(self._current_templates_list):
            return

        template = self._current_templates_list[idx]
        self._edit_template(template, parent_window)

    def _edit_template(self, template: Optional[PromptTemplate], parent_window: tk.Toplevel):
        """Show template builder/editor dialog."""
        from app.templates import TemplateVariable

        builder_window = tk.Toplevel(parent_window)
        builder_window.title("✏️ Edit Template" if template else "➕ Create New Template")
        builder_window.geometry("900x700")
        builder_window.transient(parent_window)
        builder_window.grab_set()

        # Initialize data
        if template:
            template_data = {
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "category": template.category,
                "tags": list(template.tags),
                "template_text": template.template_text,
                "variables": [
                    {
                        "name": v.name,
                        "description": v.description,
                        "required": v.required,
                        "default": v.default or "",
                    }
                    for v in template.variables
                ],
            }
        else:
            template_data = {
                "id": "",
                "name": "",
                "description": "",
                "category": "custom",
                "tags": [],
                "template_text": "",
                "variables": [],
            }

        # Main container with scrollbar
        main_canvas = tk.Canvas(builder_window)
        main_scrollbar = ttk.Scrollbar(builder_window, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)

        scrollable_frame.bind(
            "<Configure>", lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )

        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=main_scrollbar.set)

        main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        main_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # === Basic Information Section ===
        basic_frame = ttk.LabelFrame(scrollable_frame, text="📋 Basic Information", padding=15)
        basic_frame.pack(fill=tk.X, padx=5, pady=5)

        # ID (read-only if editing)
        ttk.Label(basic_frame, text="Template ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        id_var = tk.StringVar(value=template_data["id"])
        id_entry = ttk.Entry(basic_frame, textvariable=id_var, width=40)
        id_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        if template:
            id_entry.config(state="readonly")
        ttk.Label(basic_frame, text="(lowercase, hyphens only)", foreground="gray").grid(
            row=0, column=2, sticky=tk.W, padx=(5, 0)
        )

        # Name
        ttk.Label(basic_frame, text="Name:").grid(row=1, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar(value=template_data["name"])
        ttk.Entry(basic_frame, textvariable=name_var, width=40).grid(
            row=1, column=1, columnspan=2, sticky=tk.W, pady=5, padx=(10, 0)
        )

        # Description
        ttk.Label(basic_frame, text="Description:").grid(row=2, column=0, sticky=tk.NW, pady=5)
        desc_text = tk.Text(basic_frame, height=3, width=40, wrap=tk.WORD)
        desc_text.insert("1.0", template_data["description"])
        desc_text.grid(row=2, column=1, columnspan=2, sticky=tk.W, pady=5, padx=(10, 0))

        # Category
        ttk.Label(basic_frame, text="Category:").grid(row=3, column=0, sticky=tk.W, pady=5)
        categories = self.template_registry.get_categories() + ["custom"]
        category_var = tk.StringVar(value=template_data["category"])
        ttk.Combobox(
            basic_frame, textvariable=category_var, values=categories, width=37, state="readonly"
        ).grid(row=3, column=1, columnspan=2, sticky=tk.W, pady=5, padx=(10, 0))

        # Tags
        ttk.Label(basic_frame, text="Tags:").grid(row=4, column=0, sticky=tk.W, pady=5)
        tags_var = tk.StringVar(value=", ".join(template_data["tags"]))
        ttk.Entry(basic_frame, textvariable=tags_var, width=40).grid(
            row=4, column=1, sticky=tk.W, pady=5, padx=(10, 0)
        )
        ttk.Label(basic_frame, text="(comma-separated)", foreground="gray").grid(
            row=4, column=2, sticky=tk.W, padx=(5, 0)
        )

        # === Template Text Section ===
        template_frame = ttk.LabelFrame(scrollable_frame, text="📝 Template Text", padding=15)
        template_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Toolbar
        toolbar = ttk.Frame(template_frame)
        toolbar.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(toolbar, text="Use {{variable_name}} for placeholders").pack(side=tk.LEFT)

        # Insert variable button
        def insert_variable():
            if not template_data["variables"]:
                messagebox.showinfo("No Variables", "Define variables first in the section below")
                return
            var_names = [v["name"] for v in template_data["variables"]]
            # Simple selection dialog
            sel_window = tk.Toplevel(builder_window)
            sel_window.title("Insert Variable")
            sel_window.geometry("300x400")
            sel_window.transient(builder_window)

            ttk.Label(sel_window, text="Select a variable to insert:", font=("", 10, "bold")).pack(
                pady=10
            )

            listbox = tk.Listbox(sel_window, height=15)
            listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            for vname in var_names:
                listbox.insert(tk.END, vname)

            def do_insert():
                selection = listbox.curselection()
                if selection:
                    var_name = var_names[selection[0]]
                    template_text.insert(tk.INSERT, f"{{{{{var_name}}}}}")
                sel_window.destroy()

            ttk.Button(sel_window, text="Insert", command=do_insert).pack(pady=5)
            ttk.Button(sel_window, text="Cancel", command=sel_window.destroy).pack(pady=5)

        ttk.Button(toolbar, text="📌 Insert Variable", command=insert_variable).pack(
            side=tk.RIGHT, padx=5
        )

        # Text area
        text_frame = ttk.Frame(template_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        template_text = tk.Text(text_frame, height=10, wrap=tk.WORD)
        template_text.insert("1.0", template_data["template_text"])
        text_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=template_text.yview)
        template_text.configure(yscrollcommand=text_scroll.set)

        template_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # === Variables Section ===
        var_frame = ttk.LabelFrame(scrollable_frame, text="🔧 Variables", padding=15)
        var_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Variables listbox
        var_list_frame = ttk.Frame(var_frame)
        var_list_frame.pack(fill=tk.BOTH, expand=True)

        var_listbox = tk.Listbox(var_list_frame, height=8)
        var_scroll = ttk.Scrollbar(var_list_frame, orient="vertical", command=var_listbox.yview)
        var_listbox.configure(yscrollcommand=var_scroll.set)

        var_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        var_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def refresh_var_list():
            var_listbox.delete(0, tk.END)
            for v in template_data["variables"]:
                req = "✓" if v["required"] else "○"
                default_hint = f" (default: {v['default']})" if v["default"] else ""
                var_listbox.insert(tk.END, f"{req} {v['name']}{default_hint} - {v['description']}")

        refresh_var_list()

        # Variable buttons
        var_btn_frame = ttk.Frame(var_frame)
        var_btn_frame.pack(fill=tk.X, pady=(10, 0))

        def add_variable():
            var_dialog = tk.Toplevel(builder_window)
            var_dialog.title("Add Variable")
            var_dialog.geometry("500x350")
            var_dialog.transient(builder_window)
            var_dialog.grab_set()

            form_frame = ttk.Frame(var_dialog, padding=20)
            form_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(form_frame, text="Variable Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
            vname_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=vname_var, width=30).grid(
                row=0, column=1, sticky=tk.W, pady=5, padx=(10, 0)
            )

            ttk.Label(form_frame, text="Description:").grid(row=1, column=0, sticky=tk.W, pady=5)
            vdesc_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=vdesc_var, width=30).grid(
                row=1, column=1, sticky=tk.W, pady=5, padx=(10, 0)
            )

            ttk.Label(form_frame, text="Default Value:").grid(row=2, column=0, sticky=tk.W, pady=5)
            vdefault_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=vdefault_var, width=30).grid(
                row=2, column=1, sticky=tk.W, pady=5, padx=(10, 0)
            )

            vrequired_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(form_frame, text="Required", variable=vrequired_var).grid(
                row=3, column=1, sticky=tk.W, pady=5, padx=(10, 0)
            )

            def save_var():
                name = vname_var.get().strip()
                desc = vdesc_var.get().strip()
                if not name:
                    messagebox.showwarning("Invalid Input", "Variable name is required")
                    return

                template_data["variables"].append(
                    {
                        "name": name,
                        "description": desc,
                        "required": vrequired_var.get(),
                        "default": vdefault_var.get().strip(),
                    }
                )
                refresh_var_list()
                var_dialog.destroy()

            btn_frame = ttk.Frame(form_frame)
            btn_frame.grid(row=4, column=0, columnspan=2, pady=20)

            ttk.Button(btn_frame, text="Save", command=save_var).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="Cancel", command=var_dialog.destroy).pack(
                side=tk.LEFT, padx=5
            )

        def edit_variable():
            selection = var_listbox.curselection()
            if not selection:
                messagebox.showinfo("No Selection", "Select a variable to edit")
                return

            idx = selection[0]
            var_data = template_data["variables"][idx]

            var_dialog = tk.Toplevel(builder_window)
            var_dialog.title("Edit Variable")
            var_dialog.geometry("500x350")
            var_dialog.transient(builder_window)
            var_dialog.grab_set()

            form_frame = ttk.Frame(var_dialog, padding=20)
            form_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(form_frame, text="Variable Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
            vname_var = tk.StringVar(value=var_data["name"])
            ttk.Entry(form_frame, textvariable=vname_var, width=30).grid(
                row=0, column=1, sticky=tk.W, pady=5, padx=(10, 0)
            )

            ttk.Label(form_frame, text="Description:").grid(row=1, column=0, sticky=tk.W, pady=5)
            vdesc_var = tk.StringVar(value=var_data["description"])
            ttk.Entry(form_frame, textvariable=vdesc_var, width=30).grid(
                row=1, column=1, sticky=tk.W, pady=5, padx=(10, 0)
            )

            ttk.Label(form_frame, text="Default Value:").grid(row=2, column=0, sticky=tk.W, pady=5)
            vdefault_var = tk.StringVar(value=var_data["default"])
            ttk.Entry(form_frame, textvariable=vdefault_var, width=30).grid(
                row=2, column=1, sticky=tk.W, pady=5, padx=(10, 0)
            )

            vrequired_var = tk.BooleanVar(value=var_data["required"])
            ttk.Checkbutton(form_frame, text="Required", variable=vrequired_var).grid(
                row=3, column=1, sticky=tk.W, pady=5, padx=(10, 0)
            )

            def save_var():
                name = vname_var.get().strip()
                desc = vdesc_var.get().strip()
                if not name:
                    messagebox.showwarning("Invalid Input", "Variable name is required")
                    return

                template_data["variables"][idx] = {
                    "name": name,
                    "description": desc,
                    "required": vrequired_var.get(),
                    "default": vdefault_var.get().strip(),
                }
                refresh_var_list()
                var_dialog.destroy()

            btn_frame = ttk.Frame(form_frame)
            btn_frame.grid(row=4, column=0, columnspan=2, pady=20)

            ttk.Button(btn_frame, text="Save", command=save_var).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="Cancel", command=var_dialog.destroy).pack(
                side=tk.LEFT, padx=5
            )

        def delete_variable():
            selection = var_listbox.curselection()
            if not selection:
                messagebox.showinfo("No Selection", "Select a variable to delete")
                return

            idx = selection[0]
            var_name = template_data["variables"][idx]["name"]

            if messagebox.askyesno("Confirm Delete", f"Delete variable '{var_name}'?"):
                template_data["variables"].pop(idx)
                refresh_var_list()

        ttk.Button(var_btn_frame, text="➕ Add Variable", command=add_variable).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(var_btn_frame, text="✏️ Edit Variable", command=edit_variable).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(var_btn_frame, text="🗑️ Delete Variable", command=delete_variable).pack(
            side=tk.LEFT, padx=5
        )

        # === Preview Section ===
        preview_frame = ttk.LabelFrame(scrollable_frame, text="👁️ Preview", padding=15)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        preview_text = tk.Text(preview_frame, height=8, wrap=tk.WORD, state=tk.DISABLED)
        preview_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=preview_text.yview)
        preview_text.configure(yscrollcommand=preview_scroll.set)

        preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def update_preview():
            try:
                text = template_text.get("1.0", tk.END).strip()
                # Create example values
                example_vals = {}
                for v in template_data["variables"]:
                    if v["default"]:
                        example_vals[v["name"]] = v["default"]
                    else:
                        example_vals[v["name"]] = f"<{v['name']}>"

                # Simple render
                rendered = text
                for vname, vval in example_vals.items():
                    rendered = rendered.replace(f"{{{{{vname}}}}}", vval)

                preview_text.config(state=tk.NORMAL)
                preview_text.delete("1.0", tk.END)
                preview_text.insert("1.0", rendered)
                preview_text.config(state=tk.DISABLED)
            except Exception as e:
                preview_text.config(state=tk.NORMAL)
                preview_text.delete("1.0", tk.END)
                preview_text.insert("1.0", f"Preview error: {e}")
                preview_text.config(state=tk.DISABLED)

        ttk.Button(preview_frame, text="🔄 Update Preview", command=update_preview).pack(
            pady=(5, 0)
        )

        # === Action Buttons ===
        action_frame = ttk.Frame(scrollable_frame)
        action_frame.pack(fill=tk.X, padx=5, pady=15)

        def save_template():
            # Validate
            template_id = id_var.get().strip()
            template_name = name_var.get().strip()
            template_desc = desc_text.get("1.0", tk.END).strip()
            template_cat = category_var.get()
            template_tags = [t.strip() for t in tags_var.get().split(",") if t.strip()]
            template_txt = template_text.get("1.0", tk.END).strip()

            if not template_id or not template_name or not template_txt:
                messagebox.showwarning("Invalid Input", "ID, Name, and Template Text are required")
                return

            # Create PromptTemplate object
            variables = [
                TemplateVariable(
                    name=v["name"],
                    description=v["description"],
                    required=v["required"],
                    default=v["default"] if v["default"] else None,
                )
                for v in template_data["variables"]
            ]

            new_template = PromptTemplate(
                id=template_id,
                name=template_name,
                description=template_desc,
                category=template_cat,
                template_text=template_txt,
                variables=variables,
                tags=template_tags,
            )

            # Save
            try:
                self.template_registry.save_template(new_template)
                messagebox.showinfo(
                    "Success",
                    f"Template '{template_name}' saved successfully!\n\nLocation: {self.template_registry.user_path}",
                )
                builder_window.destroy()
                # Refresh parent template manager if it exists
                if hasattr(parent_window, "_refresh_templates"):
                    parent_window._refresh_templates()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save template: {e}")

        ttk.Button(
            action_frame, text="💾 Save Template", command=save_template, style="Accent.TButton"
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="❌ Cancel", command=builder_window.destroy).pack(
            side=tk.LEFT, padx=5
        )

        # Initial preview
        update_preview()

    def _delete_selected_template(self, listbox: tk.Listbox):
        """Delete selected template."""
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("Template Manager", "Please select a template first")
            return

        idx = selection[0]
        if idx >= len(self._current_templates_list):
            return

        template = self._current_templates_list[idx]

        # Confirm deletion
        if not messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete the template:\n\n{template.name}\n\nThis action cannot be undone.",
        ):
            return

        try:
            if self.template_registry.delete_template(template.id):
                messagebox.showinfo("Success", f"Template '{template.name}' deleted successfully")
                # Refresh list
                listbox.delete(idx)
                self._current_templates_list.pop(idx)
                if self._current_templates_list:
                    listbox.selection_set(0)
            else:
                messagebox.showerror(
                    "Error", "Failed to delete template (it may be a built-in template)"
                )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete template: {e}")


def main():  # pragma: no cover
    root = tk.Tk()
    PromptCompilerUI(root)
    root.mainloop()


if __name__ == "__main__":  # pragma: no cover
    main()
