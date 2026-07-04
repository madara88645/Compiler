from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_repo_plan_returns_manifest_and_diffs():
    body = {
        "pack_type": "project-pack",
        "goal": "Add a health route",
        "risk_mode": "strict",
        "repo_facts": {
            "files": {
                "package.json": '{"scripts": {"test": "vitest run"}}',
                "CLAUDE.md": "# existing guide",
            },
            "tree": ["package.json", "CLAUDE.md", "src"],
            "has_claude_md": True,
            "has_claude_dir": False,
        },
    }
    r = client.post("/agent-packs/claude/repo-plan", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["manifest"]["pack_type"] == "project-pack"
    # CLAUDE.md already exists -> flagged as an overwrite in the plan
    claude = next(p for p in data["plan"] if p["path"] == "CLAUDE.md")
    assert claude["action"] == "overwrite"
    # a brand-new file is a create
    assert any(p["action"] == "create" for p in data["plan"])
    # detected npm test command surfaced
    assert "npm run test" in str(data["detected"]["commands"])
