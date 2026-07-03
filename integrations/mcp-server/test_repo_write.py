from pathlib import Path

from repo_write import write_pack_files


def test_creates_new_and_never_clobbers(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("OLD")
    files = [
        {"path": "CLAUDE.md", "content": "NEW"},
        {"path": ".claude/settings.json", "content": "{}"},
    ]

    result = write_pack_files(str(tmp_path), files, overwrite=[])

    assert (tmp_path / ".claude/settings.json").read_text() == "{}"  # created
    assert (tmp_path / "CLAUDE.md").read_text() == "OLD"  # NOT clobbered
    assert (tmp_path / "CLAUDE.md.new").read_text() == "NEW"  # written aside
    assert result["created"] == [".claude/settings.json"]
    assert result["conflicts"] == ["CLAUDE.md"]


def test_overwrite_list_allows_replacement(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("OLD")

    result = write_pack_files(
        str(tmp_path), [{"path": "CLAUDE.md", "content": "NEW"}], overwrite=["CLAUDE.md"]
    )

    assert (tmp_path / "CLAUDE.md").read_text() == "NEW"
    assert result["overwritten"] == ["CLAUDE.md"]


def test_rejects_path_escape(tmp_path: Path):
    import pytest

    with pytest.raises(ValueError):
        write_pack_files(str(tmp_path), [{"path": "../evil.txt", "content": "x"}], overwrite=[])
