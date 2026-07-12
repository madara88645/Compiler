from pathlib import Path

import pytest

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
