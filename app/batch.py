from __future__ import annotations
import time
import json
import yaml
from pathlib import Path
from typing import List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from app.compiler import compile_text_v2
from app.emitters import emit_expanded_prompt_v2


@dataclass
class BatchResult:
    total: int = 0
    successful: int = 0
    failed: int = 0
    duration: float = 0.0
    failures: List[dict] = field(default_factory=list)


def batch_process_files(
    input_dir: Path,
    output_dir: Path,
    patterns: List[str] = ["*.txt"],
    output_format: str = "json",
    name_template: str = "{stem}.{ext}",
    recursive: bool = False,
    num_workers: int = 1,
    diagnostics: bool = False,
    jsonl_output_path: Optional[Path] = None,
    show_progress: bool = False,
) -> BatchResult:
    """
    Process a batch of prompt files.
    """
    start_time = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)

    files = []
    if recursive:
        for p in patterns:
            files.extend(list(input_dir.rglob(p)))
    else:
        for p in patterns:
            files.extend(list(input_dir.glob(p)))

    # Unique files only
    files = list(set(files))
    total = len(files)
    result = BatchResult(total=total)

    jsonl_file = None
    if jsonl_output_path:
        jsonl_output_path.parent.mkdir(parents=True, exist_ok=True)
        jsonl_file = open(jsonl_output_path, "w", encoding="utf-8")

    def process_one(f: Path) -> Tuple[Path, bool, Any, str]:
        try:
            text = f.read_text(encoding="utf-8")
            # Heuristic: try v2, if fail try v1?
            # For batch we default to v2 usually, or auto-detect?
            # Let's use v2 for batch as it is the modern standard
            ir = compile_text_v2(text)

            # Generate output content
            if output_format == "json":
                out_content = json.dumps(ir.model_dump(), indent=2, ensure_ascii=False)
            elif output_format in ["yaml", "yml"]:
                out_content = yaml.safe_dump(ir.model_dump(), sort_keys=False, allow_unicode=True)
            else:
                out_content = emit_expanded_prompt_v2(ir, diagnostics=diagnostics)

            # Determine output filename
            ext = output_format if output_format != "expanded" else "md"
            out_name = name_template.format(stem=f.stem, ext=ext)

            # If recursive, preserve relative structure?
            # Simplified: just output to flat or same relative dir
            # Implementing flat output for strict safety unless requested otherwise
            out_path = output_dir / out_name
            out_path.write_text(out_content, encoding="utf-8")

            return f, True, ir.model_dump() if jsonl_file else None, ""
        except Exception as e:
            return f, False, None, str(e)

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(process_one, f): f for f in files}

        for future in as_completed(futures):
            f, success, data, error = future.result()
            if success:
                result.successful += 1
                if jsonl_file and data:
                    jsonl_file.write(json.dumps(data, ensure_ascii=False) + "\n")
            else:
                result.failed += 1
                result.failures.append({"file": str(f), "error": error})

    if jsonl_file:
        jsonl_file.close()

    result.duration = time.perf_counter() - start_time
    return result
