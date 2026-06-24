import json as _json

from rich.console import Console
from typer.testing import CliRunner

from cli.main import app as _app
from cli.render import render_prompt_sections, render_summary_card

_runner = CliRunner()


def test_strategist_expansion_failure_is_silent(capsys):
    from app.agents.context_strategist import ContextStrategist

    class _BoomClient:
        def _call_api(self, *args, **kwargs):
            raise RuntimeError("no api key")

    strat = ContextStrategist(client=_BoomClient())
    result = strat._expand_query("write a haiku about the sea")
    captured = capsys.readouterr()
    assert "[STRATEGIST]" not in captured.err
    assert isinstance(result, list)


def test_summary_card_shows_key_fields():
    console = Console(record=True, width=80)
    ir = {
        "persona": "assistant",
        "domain": "software",
        "output_format": "text",
        "goals": ["g1"],
        "constraints": ["c1", "c2"],
        "metadata": {"policy_summary": {"risk_level": "low"}},
    }
    render_summary_card(console, ir)
    out = console.export_text()
    assert "assistant" in out
    assert "software" in out
    assert "low" in out


def test_prompt_sections_preserve_bracket_tokens():
    console = Console(record=True, width=80)
    render_prompt_sections(console, "Use [clarify] and [policy] here", "", "", "")
    out = console.export_text()
    assert "[clarify]" in out
    assert "[policy]" in out
    assert "System Prompt" in out


def test_compile_default_shows_rendered_sections_not_raw_ir():
    result = _runner.invoke(_app, ["compile", "write a haiku about the sea"])
    assert result.exit_code == 0
    assert "System Prompt" in result.stdout
    assert "User Prompt" in result.stdout
    assert '"version": "2.0"' not in result.stdout


def test_compile_json_only_still_outputs_valid_json():
    result = _runner.invoke(_app, ["compile", "write a haiku", "--json-only"])
    assert result.exit_code == 0
    parsed = _json.loads(result.stdout)
    assert parsed.get("version") == "2.0"


def test_compile_quiet_emits_nonempty_system_prompt():
    result = _runner.invoke(_app, ["compile", "write a haiku", "--quiet"])
    assert result.exit_code == 0
    assert result.stdout.strip() != ""


def test_pack_md_includes_metadata_header():
    result = _runner.invoke(_app, ["pack", "build a rest api", "--format", "md"])
    assert result.exit_code == 0
    assert "Domain:" in result.stdout
    assert "IR version:" in result.stdout


def test_compile_json_only_format_md_emits_markdown():
    result = _runner.invoke(_app, ["compile", "write a haiku", "--json-only", "--format", "md"])
    assert result.exit_code == 0
    assert "# System Prompt" in result.stdout
    assert "# IR JSON" in result.stdout
