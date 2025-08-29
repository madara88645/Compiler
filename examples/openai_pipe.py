"""
Minimal demo: compile a raw prompt with promptc, then send system/user messages to OpenAI.

Usage (PowerShell):
  # 1) Set your OpenAI API key in env
  #    (for Windows PowerShell)
  #    $env:OPENAI_API_KEY = "sk-..."
  #
  # 2) Run the script with a prompt
  #    python examples/openai_pipe.py "teach me gradient descent in 15 minutes"
  #
  # Optional flags:
  #   --model gpt-4o-mini         # OpenAI model name
  #   --expanded                  # Send Expanded Prompt instead of concise User Prompt
  #   --diagnostics               # Include diagnostics in Expanded Prompt (risk & ambiguity)

Notes:
- This uses IR v1 emitters (system/user/expanded). IR v2 is default for JSON, but v2 renderers
  are not yet shipped. This demo keeps a stable, concise user message.
- Requires package 'openai' (see requirements.txt). Reads OPENAI_API_KEY from environment.
"""
from __future__ import annotations
import os
import sys
import argparse
from typing import List, Dict, Any

try:
    # New style client (openai>=1.0)
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # type: ignore

# Local imports from this repo
from app.compiler import compile_text, optimize_ir
from app.emitters import emit_system_prompt, emit_user_prompt, emit_expanded_prompt


def compile_messages(raw_prompt: str, use_expanded: bool, diagnostics: bool) -> List[Dict[str, str]]:
    ir = optimize_ir(compile_text(raw_prompt))
    system = emit_system_prompt(ir)
    if use_expanded:
        user = emit_expanded_prompt(ir, diagnostics=diagnostics)
    else:
        user = emit_user_prompt(ir)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PromptC → OpenAI demo pipe")
    parser.add_argument("prompt", nargs="?", help="Raw prompt text. If omitted, will prompt stdin.")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI chat model (default: gpt-4o-mini)")
    parser.add_argument("--expanded", action="store_true", help="Send Expanded Prompt instead of concise User Prompt")
    parser.add_argument("--diagnostics", action="store_true", help="Include diagnostics in Expanded Prompt")
    args = parser.parse_args(argv)

    raw = args.prompt
    if not raw:
        print("Enter prompt: ", end="", flush=True)
        raw = sys.stdin.readline().strip()
    if not raw:
        print("No prompt provided.")
        return 1

    # Build messages from compiler
    msgs = compile_messages(raw, use_expanded=args.expanded, diagnostics=args.diagnostics)

    # Ensure openai client is available
    if OpenAI is None:
        print("The 'openai' package is not installed. Please run 'pip install openai' or 'pip install -r requirements.txt'.")
        return 2
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set. In PowerShell:  $env:OPENAI_API_KEY = 'sk-...' ")
        return 3

    # Call OpenAI
    client = OpenAI()
    try:
        resp = client.chat.completions.create(
            model=args.model,
            messages=msgs,  # type: ignore[arg-type]
            temperature=0.7,
        )
    except Exception as e:
        print(f"OpenAI error: {e}")
        return 4

    try:
        content = resp.choices[0].message.content  # type: ignore[attr-defined]
    except Exception:
        content = str(resp)

    print("\n=== Assistant Response ===\n")
    print(content or "<no content>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
