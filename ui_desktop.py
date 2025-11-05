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
import json
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import time
from pathlib import Path
from datetime import datetime

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
        # Settings file (per-user)
        self.config_path = Path.home() / ".promptc_ui.json"
        self.history_path = Path.home() / ".promptc_history.json"
        self.favorites_path = Path.home() / ".promptc_favorites.json"

        # Progress indicator
        self.progress_var = tk.DoubleVar(value=0)
        self.is_generating = False

        # History and favorites data
        self.history_items = []
        self.favorites_items = []
        self.sidebar_visible = True

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

        # OpenAI quick-send controls
        ttk.Label(opts, text="Model:").pack(side=tk.LEFT, padx=(12, 2))
        self.var_model = tk.StringVar(value="gpt-4o-mini")
        self.cmb_model = ttk.Combobox(
            opts,
            textvariable=self.var_model,
            width=18,
            state="readonly",
            values=(
                "gpt-4o-mini",
                "gpt-4o",
                "gpt-4.1-mini",
                "gpt-4.1",
            ),
        )
        self.cmb_model.pack(side=tk.LEFT)
        self.var_openai_expanded = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Use Expanded", variable=self.var_openai_expanded).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        btn_openai = ttk.Button(opts, text="🤖 Send to OpenAI", command=self.on_send_openai)
        btn_openai.pack(side=tk.LEFT, padx=6)
        self._add_tooltip(btn_openai, "Send compiled prompt directly to OpenAI API")

        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(opts, textvariable=self.status_var, foreground="#555").pack(side=tk.RIGHT)

        # Summary line
        self.summary_var = tk.StringVar(value="")
        ttk.Label(content, textvariable=self.summary_var, padding=(8, 0)).pack(fill=tk.X)

        # Intents chips (IR v2)
        self.chips_frame = ttk.Frame(content, padding=(8, 2))
        self.chips_frame.pack(fill=tk.X)
        self.chips_container = ttk.Frame(self.chips_frame)
        self.chips_container.pack(anchor=tk.W)

        # Notebook outputs
        self.nb = ttk.Notebook(content)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.txt_system = self._add_tab("System Prompt")
        self.txt_user = self._add_tab("User Prompt")
        self.txt_plan = self._add_tab("Plan")
        self.txt_expanded = self._add_tab("Expanded Prompt")
        self.txt_ir = self._add_tab("IR JSON")
        self.txt_ir2 = self._add_tab("IR v2 JSON")
        self.txt_openai = self._add_tab("OpenAI Response")
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

        # Load settings (theme, toggles, model, geometry) and apply
        self._load_settings()
        self.apply_theme(self.current_theme)

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
        # Quick search in text widgets
        self.root.bind("<Control-f>", lambda _e: self._find_in_active())
        # Save geometry on close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        # Save selected tab on change
        try:
            self.nb.bind("<<NotebookTabChanged>>", lambda _e: self._save_settings())
        except Exception:
            pass
        # Ctrl+S save shortcut
        try:
            self.root.bind("<Control-s>", lambda _e: self.on_save())
        except Exception:
            pass
        # Update prompt stats as user types
        try:
            self.txt_prompt.bind("<KeyRelease>", lambda _e: self._update_prompt_stats())
            self._update_prompt_stats()
        except Exception:
            pass
        # Apply initial wrap state
        try:
            self._apply_wrap()
        except Exception:
            pass

        # Load history and populate sidebar
        self._load_history()
        self._create_sidebar()

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
            getattr(self, "txt_openai", None),
            getattr(self, "txt_diff", None),
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
        # Theme
        theme = data.get("theme")
        if theme in ("light", "dark"):
            self.current_theme = theme
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

    def _save_settings(self):  # pragma: no cover - simple IO
        try:
            try:
                selected_idx = self.nb.index(self.nb.select())
            except Exception:
                selected_idx = 0
            payload = {
                "theme": self.current_theme,
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
                "geometry": self.root.winfo_geometry(),
                "selected_tab": selected_idx,
            }
            self.config_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def _on_close(self):  # pragma: no cover - UI callback
        self._save_settings()
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
            getattr(self, "txt_openai", None),
        ]:
            if t is None:
                continue
            t.delete("1.0", tk.END)
        self.summary_var.set("")
        self.status_var.set("Cleared")
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

    def on_send_openai(self):  # pragma: no cover - UI action
        prompt = self.txt_prompt.get("1.0", tk.END).strip()
        if not prompt:
            messagebox.showwarning("OpenAI", "Enter a prompt text first.")
            return
        if OpenAI is None:
            messagebox.showerror(
                "OpenAI", "Package 'openai' not installed. Run: pip install openai"
            )
            return
        if not os.environ.get("OPENAI_API_KEY"):
            messagebox.showerror("OpenAI", "OPENAI_API_KEY is not set in environment.")
            return
        model = (self.var_model.get() or "gpt-4o-mini").strip()
        use_expanded = bool(self.var_openai_expanded.get())
        diagnostics = bool(self.var_diag.get()) if use_expanded else False
        self.status_var.set(f"OpenAI: sending ({model})...")

        def _do_send():
            try:
                ir = optimize_ir(compile_text(prompt))
                system = emit_system_prompt(ir)
                if use_expanded:
                    user = emit_expanded_prompt(ir, diagnostics=diagnostics)
                else:
                    user = emit_user_prompt(ir)
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
                self.txt_openai.delete("1.0", tk.END)
                self.txt_openai.insert(tk.END, content or "<no content>")
                # Focus the OpenAI tab
                for i in range(self.nb.index("end")):
                    if self.nb.tab(i, "text") == "OpenAI Response":
                        self.nb.select(i)
                        break
                self.status_var.set("OpenAI: done")
            except Exception as e:
                self.status_var.set("OpenAI: error")
                messagebox.showerror("OpenAI", str(e))

        # Run slightly later to keep UI responsive
        self.root.after(30, _do_send)

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
            self.summary_var.set(" | ".join(parts))
            suffix = " • v2 emitters" if use_v2_emitters else ""
            self.status_var.set(
                f"✅ Done ({elapsed} ms) • heur v1 {HEURISTIC_VERSION} • heur v2 {HEURISTIC2_VERSION}{suffix}"
            )

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
                "OpenAI Response": self.txt_openai,
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
            getattr(self, "txt_openai", None),
            getattr(self, "txt_diff", None),
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
            from tkinterdnd2 import DND_FILES

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
        """Refresh the history listbox display."""
        try:
            # Clear listbox
            self.history_listbox.delete(0, tk.END)

            # Get search filter
            search_term = self.search_var.get().lower()

            # Add items
            for item in self.history_items:
                preview = item["preview"]

                # Filter by search term
                if search_term and search_term not in preview.lower():
                    continue

                # Add favorite star
                if item.get("is_favorite", False):
                    preview = "⭐ " + preview

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


def main():  # pragma: no cover
    root = tk.Tk()
    PromptCompilerUI(root)
    root.mainloop()


if __name__ == "__main__":  # pragma: no cover
    main()
