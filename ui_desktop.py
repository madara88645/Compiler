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
)

# Optional OpenAI client (only used when sending directly from UI)
try:  # openai>=1.0 style client
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dep
    OpenAI = None  # type: ignore


class PromptCompilerUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root = root
        self.root.title("Prompt Compiler")
        self.root.geometry("1200x780")
        self.root.minsize(1000, 650)
        self.current_theme = "light"

        # Input area
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Prompt:").pack(anchor=tk.W)
        self.txt_prompt = tk.Text(top, height=5, wrap=tk.WORD)
        self.txt_prompt.pack(fill=tk.X, pady=(2, 6))

        # Options row
        opts = ttk.Frame(top)
        opts.pack(fill=tk.X)
        self.var_diag = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Diagnostics", variable=self.var_diag).pack(side=tk.LEFT)
        self.var_trace = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Trace", variable=self.var_trace).pack(side=tk.LEFT, padx=(6, 0))

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
        self.tree_constraints = ttk.Treeview(cons_frame, columns=("priority","origin","id","text"), show="headings")
        self.tree_constraints.heading("priority", text="Priority")
        self.tree_constraints.heading("origin", text="Origin")
        self.tree_constraints.heading("id", text="ID")
        self.tree_constraints.heading("text", text="Text")
        self.tree_constraints.column("priority", width=80, anchor=tk.CENTER)
        self.tree_constraints.column("origin", width=120, anchor=tk.W)
        self.tree_constraints.column("id", width=120, anchor=tk.W)
        self.tree_constraints.column("text", width=600, anchor=tk.W)
        self.tree_constraints.pack(fill=tk.BOTH, expand=True)

        self.txt_trace = self._add_tab("Trace")

        self.apply_theme("light")

        # Shortcuts
        self.root.bind("<Control-Return>", lambda _e: self.on_generate())
        self.root.bind("<F5>", lambda _e: self.on_generate())
    def _add_tab(self, title: str) -> tk.Text:
        frame = ttk.Frame(self.nb)
        self.nb.add(frame, text=title)
        bar = ttk.Frame(frame)
        bar.pack(fill=tk.X)
        txt = tk.Text(frame, wrap=tk.NONE)
        txt.pack(fill=tk.BOTH, expand=True)
        ttk.Button(bar, text="Copy", command=lambda t=txt: self._copy_text(t)).pack(side=tk.LEFT, padx=2, pady=2)
        if title == "Expanded Prompt":
            ttk.Label(bar, text="(Diagnostics appear here if enabled)", foreground="#666").pack(side=tk.RIGHT)
        return txt

    # Theme
    def toggle_theme(self):
        self.apply_theme("dark" if self.current_theme == "light" else "light")

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
        for t in [self.txt_prompt, self.txt_system, self.txt_user, self.txt_plan, self.txt_expanded, self.txt_ir, self.txt_ir2, self.txt_trace, getattr(self, 'txt_openai', None)]:
            if t is None:
                continue
            t.configure(bg=panel, fg=fg, insertbackground=fg, relief=tk.FLAT, highlightbackground=bg)
        self.btn_theme.config(text="Light" if dark else "Dark")

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
            system = emit_system_prompt(ir)
            user = emit_user_prompt(ir)
            plan = emit_plan(ir)
            expanded = emit_expanded_prompt(ir, diagnostics=diagnostics)
            ir_json = json.dumps(ir.dict(), ensure_ascii=False, indent=2)
            # Optional extras
            trace_lines = generate_trace(ir) if self.var_trace.get() else []
            ir2 = None
            try:
                ir2 = compile_text_v2(prompt)
                ir2_json = json.dumps(ir2.dict(), ensure_ascii=False, indent=2)
            except Exception:
                ir2_json = ""
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
                # Clear and insert
                if hasattr(self, 'tree_constraints'):
                    for i in self.tree_constraints.get_children():
                        self.tree_constraints.delete(i)
                    for r in rows:
                        self.tree_constraints.insert('', tk.END, values=r)
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
            self.status_var.set(f"Done ({elapsed} ms) • heur v1 {HEURISTIC_VERSION} • heur v2 {HEURISTIC2_VERSION}")
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
            md.append(f"| {pr} | {origin} | {idv} | {str(text).replace('|','\\|')} |")
        data = "\n".join(md)
        self.root.clipboard_clear()
        self.root.clipboard_append(data)
        self.status_var.set("Constraints copied")

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


def main():  # pragma: no cover
    root = tk.Tk()
    PromptCompilerUI(root)
    root.mainloop()


if __name__ == "__main__":  # pragma: no cover
    main()
