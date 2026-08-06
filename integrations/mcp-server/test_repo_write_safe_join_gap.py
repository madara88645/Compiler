"""Direct unit tests for repo_write._safe_join.

This is the path-traversal guard behind write_pack_files. Before this file,
it only had one indirect case (via test_repo_write.py::test_rejects_path_escape,
exercised through write_pack_files). It is security-relevant — it decides
whether a manifest entry is allowed to write outside the target repo root —
so it deserves direct coverage of its own branches.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from repo_write import _safe_join


def test_nested_relative_path_stays_inside_root(tmp_path: Path):
    result = _safe_join(str(tmp_path), "a/b/c.txt")
    assert result == str(tmp_path / "a" / "b" / "c.txt")


def test_dot_segment_resolves_back_inside_root(tmp_path: Path):
    result = _safe_join(str(tmp_path), "sub/../file.txt")
    assert result == str(tmp_path / "file.txt")


def test_empty_relative_path_resolves_to_root(tmp_path: Path):
    result = _safe_join(str(tmp_path), "")
    assert result == str(tmp_path)


def test_dot_relative_path_resolves_to_root(tmp_path: Path):
    result = _safe_join(str(tmp_path), ".")
    assert result == str(tmp_path)


def test_simple_parent_escape_is_rejected(tmp_path: Path):
    with pytest.raises(ValueError, match="unsafe path escapes repo root"):
        _safe_join(str(tmp_path), "../evil.txt")


def test_nested_parent_escape_is_rejected(tmp_path: Path):
    with pytest.raises(ValueError):
        _safe_join(str(tmp_path), "a/../../evil.txt")


def test_deeply_nested_parent_escape_is_rejected(tmp_path: Path):
    with pytest.raises(ValueError):
        _safe_join(str(tmp_path), "../../../../etc/passwd")


def test_absolute_path_outside_root_is_rejected(tmp_path: Path):
    # os.path.join discards the root when the second argument is absolute,
    # so this must still be caught by the commonpath check.
    with pytest.raises(ValueError):
        _safe_join(str(tmp_path), os.path.join(os.sep, "etc", "passwd"))


def test_root_with_trailing_separator_still_matches(tmp_path: Path):
    root_with_slash = str(tmp_path) + os.sep
    result = _safe_join(root_with_slash, "file.txt")
    assert result == str(tmp_path / "file.txt")
