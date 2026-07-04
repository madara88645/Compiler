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
    # CLAUDE.md already exists -> merged (existing "# existing guide" has no ## sections,
    # so every generated ## section is appended)
    claude = next(p for p in data["plan"] if p["path"] == "CLAUDE.md")
    assert claude["action"] == "merge"
    claude_file = next(f for f in data["manifest"]["files"] if f["path"] == "CLAUDE.md")
    assert claude_file["content"].startswith("# existing guide")
    assert "Added by Prompt Compiler" in claude_file["content"]
    # a brand-new file is a create
    assert any(p["action"] == "create" for p in data["plan"])
    # detected npm test command surfaced
    assert "npm run test" in str(data["detected"]["commands"])


def test_repo_plan_claude_md_identical_when_all_sections_present():
    # Feed the generated CLAUDE.md back as the existing file: every generated ## heading is
    # already present, so merge finds nothing new -> action "identical". (Generation is
    # deterministic for a fixed goal, so the two generations match.)
    gen_body = {
        "pack_type": "project-pack",
        "goal": "g",
        "repo_facts": {"files": {"package.json": "{}"}, "tree": ["package.json"]},
    }
    gen = client.post("/agent-packs/claude/repo-plan", json=gen_body)
    generated_claude = next(
        f["content"] for f in gen.json()["manifest"]["files"] if f["path"] == "CLAUDE.md"
    )

    body = {
        "pack_type": "project-pack",
        "goal": "g",
        "repo_facts": {"files": {"CLAUDE.md": generated_claude}, "tree": ["CLAUDE.md"]},
    }
    r = client.post("/agent-packs/claude/repo-plan", json=body)
    assert r.status_code == 200
    claude = next(p for p in r.json()["plan"] if p["path"] == "CLAUDE.md")
    assert claude["action"] == "identical"


def test_repo_plan_claude_md_create_when_absent():
    body = {
        "pack_type": "project-pack",
        "goal": "g",
        "repo_facts": {"files": {"package.json": "{}"}, "tree": ["package.json"]},
    }
    r = client.post("/agent-packs/claude/repo-plan", json=body)
    assert r.status_code == 200
    claude = next(p for p in r.json()["plan"] if p["path"] == "CLAUDE.md")
    assert claude["action"] == "create"
