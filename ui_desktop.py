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
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import time
from pathlib import Path

from app.compiler import compile_text, compile_text_v2, optimize_ir, HEURISTIC_VERSION, HEURISTIC2_VERSION, generate_trace
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
        self.root.title("Prompt Compiler")
        self.root.geometry("1200x780")
        self.root.minsize(1000, 650)
        self.current_theme = "light"
        # Settings file (per-user)
        self.config_path = Path.home() / ".promptc_ui.json"

        # Input area
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Prompt:").pack(anchor=tk.W)
        self.txt_prompt = tk.Text(top, height=5, wrap=tk.WORD)
        self.txt_prompt.pack(fill=tk.X, pady=(2, 6))
        # Prompt stats (chars/words)
        self.prompt_stats_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.prompt_stats_var, foreground="#666").pack(anchor=tk.W)

        # Options row
        opts = ttk.Frame(top)
        opts.pack(fill=tk.X)
        self.var_diag = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Diagnostics", variable=self.var_diag).pack(side=tk.LEFT)
        self.var_trace = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Trace", variable=self.var_trace).pack(side=tk.LEFT, padx=(6, 0))
        # Toggle: render prompts using IR v2 emitters
        self.var_render_v2 = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Use IR v2 emitters", variable=self.var_render_v2).pack(side=tk.LEFT, padx=(6, 0))
        # Toggle: wrap long lines in output panes
        self.var_wrap = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Wrap output", variable=self.var_wrap).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Button(opts, text="Generate", command=self.on_generate).pack(side=tk.LEFT, padx=4)
        ttk.Button(opts, text="Show Schema", command=self.on_show_schema).pack(side=tk.LEFT, padx=4)
        ttk.Button(opts, text="Clear", command=self.on_clear).pack(side=tk.LEFT, padx=4)
        ttk.Button(opts, text="Save...", command=self.on_save).pack(side=tk.LEFT, padx=4)
        self.btn_theme = ttk.Button(opts, text="Dark", command=self.toggle_theme)
        self.btn_theme.pack(side=tk.LEFT, padx=4)

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
        ttk.Checkbutton(opts, text="Use Expanded", variable=self.var_openai_expanded).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(opts, text="Send to OpenAI", command=self.on_send_openai).pack(side=tk.LEFT, padx=6)

        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(opts, textvariable=self.status_var, foreground="#555").pack(side=tk.RIGHT)

        # Summary line
        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.root, textvariable=self.summary_var, padding=(8, 0)).pack(fill=tk.X)

        # Intents chips (IR v2)
        self.chips_frame = ttk.Frame(self.root, padding=(8, 2))
        self.chips_frame.pack(fill=tk.X)
        self.chips_container = ttk.Frame(self.chips_frame)
        self.chips_container.pack(anchor=tk.W)

        # Notebook outputs
        self.nb = ttk.Notebook(self.root)
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
        ttk.Button(cons_bar, text="Copy", command=self._copy_constraints).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(cons_bar, text="Export CSV", command=self._export_constraints_csv).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(cons_bar, text="Export JSON", command=self._export_constraints_json).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(cons_bar, text="Export Trace", command=self._export_trace).pack(side=tk.LEFT, padx=2, pady=2)
        # Filter: show only live_debug origin constraints
        self.var_only_live_debug = tk.BooleanVar(value=False)
        ttk.Checkbutton(cons_bar, text="Only live_debug", variable=self.var_only_live_debug,
            command=self._render_constraints_table).pack(side=tk.LEFT, padx=6)
        # Text search filter
        ttk.Label(cons_bar, text="Search:").pack(side=tk.LEFT, padx=(6,2))
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
            values=("Any","90","80","70","65","60","50","40","30","20","10"),
        )
        self.cmb_min_priority.pack(side=tk.LEFT)
        self.cmb_min_priority.bind("<<ComboboxSelected>>", lambda _e: self._render_constraints_table())
        self.tree_constraints = ttk.Treeview(cons_frame, columns=("priority","origin","id","text"), show="headings")
        # Add clickable headings for sorting
        self._constraints_sort_state = {"col": None, "reverse": False}
        self.tree_constraints.heading("priority", text="Priority", command=lambda c="priority": self._sort_constraints(c))
        self.tree_constraints.heading("origin", text="Origin", command=lambda c="origin": self._sort_constraints(c))
        self.tree_constraints.heading("id", text="ID", command=lambda c="id": self._sort_constraints(c))
        self.tree_constraints.heading("text", text="Text", command=lambda c="text": self._sort_constraints(c))
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
        self.var_min_priority.trace_add("write", lambda *_: (self._render_constraints_table(), self._save_settings()))

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

    def _add_tab(self, title: str) -> tk.Text:
        frame = ttk.Frame(self.nb)
        self.nb.add(frame, text=title)
        bar = ttk.Frame(frame)
        bar.pack(fill=tk.X)
        txt = tk.Text(frame, wrap=tk.NONE)
        txt.pack(fill=tk.BOTH, expand=True)
        ttk.Button(bar, text="Copy", command=lambda t=txt: self._copy_text(t)).pack(side=tk.LEFT, padx=2, pady=2)
        if title in ("System Prompt", "User Prompt", "Plan", "Expanded Prompt"):
            ttk.Button(bar, text="Copy all", command=self._copy_all_texts).pack(side=tk.LEFT, padx=2, pady=2)
        if title == "IR JSON":
            ttk.Button(bar, text="Export JSON", command=lambda: self._export_text(self.txt_ir, default_ext=".json")).pack(side=tk.LEFT, padx=2, pady=2)
            ttk.Button(bar, text="Copy as cURL", command=self._copy_as_curl).pack(side=tk.LEFT, padx=2, pady=2)
        if title == "IR v2 JSON":
            ttk.Button(bar, text="Export JSON", command=lambda: self._export_text(self.txt_ir2, default_ext=".json")).pack(side=tk.LEFT, padx=2, pady=2)
            ttk.Button(bar, text="Copy as cURL", command=self._copy_as_curl).pack(side=tk.LEFT, padx=2, pady=2)
        if title == "Expanded Prompt":
            ttk.Button(bar, text="Export MD", command=lambda: self._export_markdown_combined()).pack(side=tk.LEFT, padx=2, pady=2)
        if title == "Expanded Prompt":
            ttk.Label(bar, text="(Diagnostics appear here if enabled)", foreground="#666").pack(side=tk.RIGHT)
        return txt

    # Theme
    def toggle_theme(self):
        self.apply_theme("dark" if self.current_theme == "light" else "light")
        self._save_settings()

    def apply_theme(self, theme: str):
        self.current_theme = theme
        dark = theme == "dark"
        bg = "#1e1e1e" if dark else "#ffffff"
        fg = "#e0e0e0" if dark else "#000000"
        panel = "#252526" if dark else "#f5f5f5"
        accent = "#0e639c" if dark else "#0a64a0"
        self.root.configure(bg=bg)
        style = ttk.Style()
        try:
            if dark:
                style.theme_use("clam")
        except Exception:
            pass
        for elem in ["TFrame", "TLabel", "TCheckbutton"]:
            style.configure(elem, background=bg, foreground=fg)
        style.configure("TNotebook", background=bg, foreground=fg)
        style.configure("TNotebook.Tab", background=panel, foreground=fg)
        style.map("TNotebook.Tab", background=[("selected", accent)])
        # Treeview (constraints)
        style.configure("Treeview", background=panel, fieldbackground=panel, foreground=fg)
        style.configure("Treeview.Heading", background=panel, foreground=fg)
        # Chips label style
        style.configure("Chip.TLabel", background=("#2d7dd2" if not dark else "#2563eb"), foreground="#ffffff", padding=(6,2))
        for t in [self.txt_prompt, self.txt_system, self.txt_user, self.txt_plan, self.txt_expanded, self.txt_ir, self.txt_ir2, self.txt_trace, getattr(self, 'txt_openai', None), getattr(self, 'txt_diff', None)]:
            if t is None:
                continue
            t.configure(bg=panel, fg=fg, insertbackground=fg, relief=tk.FLAT, highlightbackground=bg)
        self.btn_theme.config(text="Light" if dark else "Dark")

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
        if (geo := data.get("geometry")):
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
                "render_v2_emitters": bool(getattr(self, 'var_render_v2', tk.BooleanVar(value=False)).get()),
                "only_live_debug": bool(getattr(self, 'var_only_live_debug', tk.BooleanVar(value=False)).get()),
                "wrap": bool(getattr(self, 'var_wrap', tk.BooleanVar(value=False)).get()),
                "min_priority": getattr(self, 'var_min_priority', tk.StringVar(value="Any")).get(),
                "model": (self.var_model.get() or "gpt-4o-mini").strip(),
                "geometry": self.root.winfo_geometry(),
                "selected_tab": selected_idx,
            }
            self.config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
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
        for t in [self.txt_system, self.txt_user, self.txt_plan, self.txt_expanded, self.txt_ir, self.txt_ir2, self.txt_trace, getattr(self, 'txt_openai', None)]:
            if t is None:
                continue
            t.delete("1.0", tk.END)
        self.summary_var.set("")
        self.status_var.set("Cleared")
        # Clear chips and constraints
        for w in self.chips_container.winfo_children():
            w.destroy()
        if hasattr(self, 'tree_constraints'):
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
        self.status_var.set("Generating...")
        self.root.after(30, lambda: self._generate_core(prompt))

    def on_send_openai(self):  # pragma: no cover - UI action
        prompt = self.txt_prompt.get("1.0", tk.END).strip()
        if not prompt:
            messagebox.showwarning("OpenAI", "Enter a prompt text first.")
            return
        if OpenAI is None:
            messagebox.showerror("OpenAI", "Package 'openai' not installed. Run: pip install openai")
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
                    messages=[{"role":"system","content":system}, {"role":"user","content":user}],
                    temperature=0.7,
                )
                try:
                    content = resp.choices[0].message.content  # type: ignore[attr-defined]
                except Exception:
                    content = str(resp)
                self.txt_openai.delete("1.0", tk.END)
                self.txt_openai.insert(tk.END, content or "<no content>")
                # Focus the OpenAI tab
                for i in range(self.nb.index('end')):
                    if self.nb.tab(i, 'text') == 'OpenAI Response':
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
            ir_json = json.dumps(ir.model_dump(), ensure_ascii=False, indent=2)
            ir2_json = json.dumps(ir2.model_dump(), ensure_ascii=False, indent=2) if ir2 is not None else ""
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
                for intent in (getattr(ir2, 'intents', []) or []):
                    lbl = ttk.Label(self.chips_container, text=intent, style="Chip.TLabel")
                    lbl.pack(side=tk.LEFT, padx=4, pady=2)
                # Constraints table sorted by priority desc
                rows = []
                for c in (getattr(ir2, 'constraints', []) or []):
                    pr = getattr(c, 'priority', 0) or 0
                    rows.append((pr, getattr(c,'origin',''), getattr(c,'id',''), getattr(c,'text','')))
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
            self.status_var.set(f"Done ({elapsed} ms) • heur v1 {HEURISTIC_VERSION} • heur v2 {HEURISTIC2_VERSION}{suffix}")
        except Exception as e:  # pragma: no cover
            self.status_var.set("Error")
            messagebox.showerror("Error", str(e))

    def _copy_constraints(self):
        if not hasattr(self, 'tree_constraints'):
            return
        rows = [self.tree_constraints.item(i, 'values') for i in self.tree_constraints.get_children()]
        if not rows:
            return
        # Build Markdown table
        md = ["| Priority | Origin | ID | Text |", "|---:|---|---|---|"]
        for pr, origin, idv, text in rows:
            text_str = str(text).replace('|', '\\|')
            md.append(f"| {pr} | {origin} | {idv} | {text_str} |")
        data = "\n".join(md)
        self.root.clipboard_clear()
        self.root.clipboard_append(data)
        self.status_var.set("Constraints copied")

    def _export_constraints_csv(self):
        if not hasattr(self, 'tree_constraints'):
            return
        rows = [self.tree_constraints.item(i, 'values') for i in self.tree_constraints.get_children()]
        if not rows:
            messagebox.showinfo("Export", "No constraints to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv"), ("All Files","*.*")])
        if not path:
            return
        try:
            # Simple CSV without quotes for readability; escape commas in text
            lines = ["priority,origin,id,text"]
            for pr, origin, idv, text in rows:
                text_s = str(text).replace('\n', ' ').replace('"', '""')
                # surround text with quotes to preserve commas
                lines.append(f"{pr},{origin},{idv},\"{text_s}\"")
            Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
            messagebox.showinfo("Export", f"Saved: {path}")
        except Exception as e:
            messagebox.showerror("Export", str(e))

    def _export_constraints_json(self):
        if not hasattr(self, 'tree_constraints'):
            return
        rows = [self.tree_constraints.item(i, 'values') for i in self.tree_constraints.get_children()]
        if not rows:
            messagebox.showinfo("Export", "No constraints to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON","*.json"), ("All Files","*.*")])
        if not path:
            return
        try:
            data = [
                {"priority": pr, "origin": origin, "id": idv, "text": text}
                for pr, origin, idv, text in rows
            ]
            Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
        ft = [("All Files","*.*")]
        if default_ext == ".json":
            ft = [("JSON","*.json"), ("All Files","*.*")]
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
        path = filedialog.asksaveasfilename(defaultextension=".md", filetypes=[("Markdown","*.md"), ("All Files","*.*")])
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
        if not hasattr(self, 'tree_constraints'):
            return
        rows = getattr(self, '_constraints_rows_all', [])
        if not isinstance(rows, list):
            rows = []
        if bool(getattr(self, 'var_only_live_debug', tk.BooleanVar(value=False)).get()):
            rows_to_show = [r for r in rows if (len(r) > 1 and str(r[1]) == 'live_debug')]
        else:
            rows_to_show = rows
        # Apply min priority filter if set
        try:
            mp_raw = getattr(self, 'var_min_priority', tk.StringVar(value="Any")).get()
            if mp_raw and mp_raw != "Any":
                mp = int(mp_raw)
                rows_to_show = [r for r in rows_to_show if (len(r) > 0 and int(r[0]) >= mp)]
        except Exception:
            pass
        # Apply text search filter
        try:
            term = getattr(self, 'var_constraints_search', tk.StringVar(value="")).get().strip().lower()
            if term:
                rows_to_show = [r for r in rows_to_show if any(term in str(cell).lower() for cell in r)]
        except Exception:
            pass
        # Apply sorting state
        try:
            state = getattr(self, '_constraints_sort_state', None)
            if state and state.get('col'):
                col = state['col']
                idx_map = {'priority':0,'origin':1,'id':2,'text':3}
                ci = idx_map.get(col)
                if ci is not None:
                    rows_to_show = sorted(rows_to_show, key=lambda r: (r[ci] if ci < len(r) else ''), reverse=bool(state.get('reverse')))
        except Exception:
            pass
        for i in self.tree_constraints.get_children():
            self.tree_constraints.delete(i)
        for r in rows_to_show:
            self.tree_constraints.insert('', tk.END, values=r)
        # Persist filter state
        self._save_settings()

    def _sort_constraints(self, column: str):  # pragma: no cover - UI event
        try:
            state = getattr(self, '_constraints_sort_state', {"col": None, "reverse": False})
            if state.get('col') == column:
                state['reverse'] = not state.get('reverse')
            else:
                state['col'] = column
                state['reverse'] = False
            self._constraints_sort_state = state
            self._render_constraints_table()
        except Exception:
            pass

    def _copy_as_curl(self):  # pragma: no cover - UI utility
        try:
            prompt = self.txt_prompt.get("1.0", tk.END).strip()
            diagnostics = 'true' if bool(self.var_diag.get()) else 'false'
            trace = 'true' if bool(self.var_trace.get()) else 'false'
            render_v2_prompts = 'true' if bool(self.var_render_v2.get()) else 'false'
            payload = {
                "text": prompt,
                "diagnostics": diagnostics == 'true',
                "trace": trace == 'true',
                "v2": True,
                "render_v2_prompts": render_v2_prompts == 'true'
            }
            # Minify JSON for curl
            body = json.dumps(payload, ensure_ascii=False)
            # Escape single quotes for POSIX shell: close quote, insert escaped quote, reopen.
            # Replace ' with '\'' pattern (achieved via '"'"' sequence) to keep portability.
            escaped = body.replace("'", "'\"'\"'")
            cmd = (
                "curl -s -X POST http://localhost:8000/compile "
                "-H \"Content-Type: application/json\" "
                f"--data '{escaped}'"
            )
            self.root.clipboard_clear()
            self.root.clipboard_append(cmd)
            self.status_var.set("cURL copied")
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
            path = filedialog.asksaveasfilename(defaultextension=".md", filetypes=[("Markdown","*.md"), ("All Files","*.*")])
            if not path:
                return
            content = []
            content.append("# System Prompt\n\n" + self.txt_system.get("1.0", tk.END).strip())
            content.append("\n\n# User Prompt\n\n" + self.txt_user.get("1.0", tk.END).strip())
            content.append("\n\n# Plan\n\n" + self.txt_plan.get("1.0", tk.END).strip())
            content.append("\n\n# Expanded Prompt\n\n" + self.txt_expanded.get("1.0", tk.END).strip())
            try:
                Path(path).write_text("\n".join(content), encoding="utf-8")
                messagebox.showinfo("Save", f"Saved: {path}")
            except Exception as e:
                messagebox.showerror("Save", str(e))

        def save_ir():
            path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON","*.json"), ("All Files","*.*")])
            if not path:
                return
            try:
                Path(path).write_text(self.txt_ir.get("1.0", tk.END).strip() + "\n", encoding="utf-8")
                messagebox.showinfo("Save", f"Saved: {path}")
            except Exception as e:
                messagebox.showerror("Save", str(e))

        def save_ir2():
            path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON","*.json"), ("All Files","*.*")])
            if not path:
                return
            try:
                Path(path).write_text(self.txt_ir2.get("1.0", tk.END).strip() + "\n", encoding="utf-8")
                messagebox.showinfo("Save", f"Saved: {path}")
            except Exception as e:
                messagebox.showerror("Save", str(e))

        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X, pady=(8,0))
        ttk.Button(btns, text="Save Combined Markdown", command=save_md).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Save IR v1 JSON", command=save_ir).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Save IR v2 JSON", command=save_ir2).pack(side=tk.LEFT, padx=4)

    # Extra helpers
    def _export_trace(self):
        data = self.txt_trace.get("1.0", tk.END).strip()
        if not data:
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text","*.txt"), ("All Files","*.*")])
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
            title = self.nb.tab(idx, 'text')
            mapping = {
                'System Prompt': self.txt_system,
                'User Prompt': self.txt_user,
                'Plan': self.txt_plan,
                'Expanded Prompt': self.txt_expanded,
                'IR JSON': self.txt_ir,
                'IR v2 JSON': self.txt_ir2,
                'OpenAI Response': self.txt_openai,
                'Trace': self.txt_trace,
                'IR Diff': self.txt_diff,
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
                    widget.tag_remove('sel', '1.0', tk.END)
                    widget.tag_add('sel', start, end)
                    widget.mark_set(tk.INSERT, end)
                    widget.see(start)
            except Exception:
                pass
        ttk.Button(frm, text="Find Next", command=do_find).pack(anchor=tk.E, pady=(6,0))

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
        for t in [self.txt_system, self.txt_user, self.txt_plan, self.txt_expanded, self.txt_ir, self.txt_ir2, self.txt_trace, getattr(self, 'txt_openai', None), getattr(self, 'txt_diff', None)]:
            if t is None:
                continue
            try:
                t.configure(wrap=wrap_mode)
            except Exception:
                pass


def main():  # pragma: no cover
    root = tk.Tk()
    PromptCompilerUI(root)
    root.mainloop()


if __name__ == "__main__":  # pragma: no cover
    main()
