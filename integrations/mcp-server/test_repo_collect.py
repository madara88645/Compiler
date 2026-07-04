from pathlib import Path

from repo_collect import collect_repo_facts


def test_collects_manifests_tree_and_claude(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"scripts": {"test": "vitest run"}}')
    (tmp_path / "CLAUDE.md").write_text("# guide")
    (tmp_path / "src").mkdir()
    (tmp_path / ".env").write_text("SECRET=xyz")

    facts = collect_repo_facts(str(tmp_path))

    assert "package.json" in facts["files"]
    assert facts["has_claude_md"] is True
    assert "src" in facts["tree"]
    assert ".env" not in facts["files"]  # never collect secrets


def test_collects_nested_manifest(tmp_path: Path):
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "package.json").write_text('{"scripts": {"build": "next build"}}')

    facts = collect_repo_facts(str(tmp_path))

    assert "web/package.json" in facts["files"]
