from __future__ import annotations

import os


def _safe_join(root: str, rel: str) -> str:
    root_abs = os.path.abspath(root)
    target = os.path.abspath(os.path.join(root_abs, rel))
    if os.path.commonpath([root_abs, target]) != root_abs:
        raise ValueError(f"unsafe path escapes repo root: {rel}")
    return target


def write_pack_files(repo_path: str, files: list[dict], overwrite: list[str]) -> dict:
    """Write manifest files into a local repo with a no-clobber policy.

    An existing path is only replaced when its path is listed in ``overwrite``; otherwise the
    new content is written to ``<path>.new`` and reported as a conflict.
    """
    created: list[str] = []
    overwritten: list[str] = []
    conflicts: list[str] = []
    for f in files:
        rel, content = f["path"], f["content"]
        target = _safe_join(repo_path, rel)
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        if os.path.exists(target):
            if rel in overwrite:
                with open(target, "w", encoding="utf-8") as fh:
                    fh.write(content)
                overwritten.append(rel)
            else:
                with open(target + ".new", "w", encoding="utf-8") as fh:
                    fh.write(content)
                conflicts.append(rel)
        else:
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(content)
            created.append(rel)
    return {"created": created, "overwritten": overwritten, "conflicts": conflicts}
