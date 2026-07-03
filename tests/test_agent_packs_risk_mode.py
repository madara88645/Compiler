import json

from app.adapters.agent_packs import AgentPackRequest, ClaudeAgentPackAdapter


class _StubCompiler:
    def generate_agent(self, *a, **k):
        return ""  # force request-grounded IR (no generator dependency)

    def generate_skill(self, *a, **k):
        return ""


def _settings(risk_mode):
    req = AgentPackRequest(
        project_type="svc",
        stack="Python, FastAPI",
        goal="Do a thing",
        pack_type="project-pack",
        risk_mode=risk_mode,
    )
    manifest = ClaudeAgentPackAdapter().build_manifest(req, _StubCompiler())
    settings = next(f.content for f in manifest.files if f.path.endswith("settings.json"))
    return json.loads(settings)


def test_strict_settings_are_tighter_than_balanced():
    balanced = _settings("balanced")
    strict = _settings("strict")

    assert strict != balanced
    # strict uses a non-auto-accept default
    assert strict["permissions"]["defaultMode"] != "acceptEdits"
    assert balanced["permissions"]["defaultMode"] == "acceptEdits"
    # deploy/push CLIs are hard-denied under strict, merely asked under balanced
    assert "Bash(git push:*)" in strict["permissions"]["deny"]
    assert "Bash(git push:*)" in balanced["permissions"]["ask"]
