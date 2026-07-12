import os

import pytest

from app.rag.simple_index import ingest_paths
from app.rag.uploads import PathSecurityError, resolve_allowed_path


def test_resolve_allowed_path_rejects_parent_traversal_even_inside_allowed_root(tmp_path):
    allowed_root = tmp_path / "allowed"
    nested_dir = allowed_root / "docs"
    nested_dir.mkdir(parents=True)

    traversal_path = nested_dir / ".." / "secret.txt"

    with pytest.raises(PathSecurityError, match="Path traversal is not allowed."):
        resolve_allowed_path(str(traversal_path), allowed_roots=[allowed_root.resolve()])


def test_resolve_allowed_path_rejects_null_bytes_before_path_resolution(tmp_path):
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    raw_path = f"{allowed_root / 'report.txt'}\x00hidden"

    with pytest.raises(PathSecurityError, match="Null bytes are not allowed in paths."):
        resolve_allowed_path(raw_path, allowed_roots=[allowed_root.resolve()])


def test_ingest_paths_filters_symlinks_by_resolved_target_suffix(tmp_path):
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    outside_name = allowed_root / "real.md"
    outside_name.write_text("linked markdown content", encoding="utf-8")

    linked_txt = allowed_root / "alias.txt"
    os.symlink(outside_name, linked_txt)

    docs, chunks, _ = ingest_paths(
        [str(allowed_root)],
        db_path=str(tmp_path / "idx.db"),
        exts=[".txt"],
        allowed_roots=[allowed_root.resolve()],
    )

    assert docs == 0
    assert chunks == 0
