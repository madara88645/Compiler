from app.adapters.agent_packs import AgentPackRequest, ClaudeAgentPackAdapter


class _StubCompiler:
    def generate_agent(self, *a, **k):
        return ""

    def generate_skill(self, *a, **k):
        return ""


def test_detected_commands_land_in_claude_md():
    req = AgentPackRequest(
        project_type="svc",
        stack="Python, FastAPI",
        goal="Add a health route",
        pack_type="project-pack",
        risk_mode="balanced",
        detected_commands={"test": "python -m pytest tests/ -q", "build": "next build"},
        detected_stack="python / fastapi, next",
    )
    manifest = ClaudeAgentPackAdapter().build_manifest(req, _StubCompiler())
    claude_md = next(f.content for f in manifest.files if f.path == "CLAUDE.md")
    assert "python -m pytest tests/ -q" in claude_md
    assert "next build" in claude_md
