import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from app.llm_engine.hybrid import HybridCompiler


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_hybrid_engine.py <prompt_text>")
        print("Example: python scripts/test_hybrid_engine.py 'Teach me python'")
        sys.exit(1)

    text = sys.argv[1]

    print(f"--- Testing HybridCompiler with input: '{text}' ---")

    # Check for API Key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("WARNING: OPENAI_API_KEY not found. Expecting fallback to heuristics.")

    compiler = HybridCompiler(api_key=api_key)

    try:
        result = compiler.compile(text)

        print("\n--- Result (JSON) ---")
        # Dump model to json
        print(result.model_dump_json(indent=2))

        print("\n--- Diagnostics ---")
        for d in result.diagnostics:
            icon = "🔴" if d.severity == "error" else "🟡" if d.severity == "warning" else "🔵"
            print(f"{icon} [{d.category}] {d.message} -> {d.suggestion}")

        print("\n--- Thought Process ---")
        print(result.thought_process)

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")


if __name__ == "__main__":
    main()
