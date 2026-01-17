from typer.testing import CliRunner
import cli.commands.rag
from cli.main import app

runner = CliRunner()


def test_rag_pack_cli_args(monkeypatch):
    """Verify that CLI args --dedup and --token-aware are passed to pack."""

    captured_args = {}

    # We need to mock search/search_hybrid in cli.commands.rag?
    # cli.commands.rag imports search, search_hybrid. So we must patch cli.commands.rag.search_hybrid

    def mock_search(*args, **kwargs):
        return []

    monkeypatch.setattr(cli.commands.rag, "search", mock_search)
    monkeypatch.setattr(cli.commands.rag, "search_hybrid", mock_search)
    monkeypatch.setattr(cli.commands.rag, "search_embed", mock_search)

    def mock_pack(
        query,
        results,
        max_chars=4000,
        max_tokens=None,
        token_chars=4.0,
        dedup=False,
        token_aware=False,
    ):
        captured_args["dedup"] = dedup
        captured_args["token_aware"] = token_aware
        return {
            "packed": "mock",
            "included": [],
            "chars": 0,
            "tokens": 0,
            "query": query,
            "budget": {},
        }

    # Patch the function as imported in cli.commands.rag
    monkeypatch.setattr(cli.commands.rag, "pack_context", mock_pack)


    # Run command
    result = runner.invoke(
        app, ["rag", "pack", "test search", "--dedup", "--token-aware", "--max-tokens", "100"]
    )

    if result.exit_code != 0:
        print(result.stdout)

    assert result.exit_code == 0, f"Command failed: {result.stdout}"
    assert captured_args.get("dedup") is True
    assert captured_args.get("token_aware") is True


def test_rag_pack_defaults(monkeypatch):
    captured_args = {}

    def mock_search(*args, **kwargs):
        return []

    monkeypatch.setattr(cli.commands.rag, "search", mock_search)
    monkeypatch.setattr(cli.commands.rag, "search_hybrid", mock_search)

    def mock_pack(
        query,
        results,
        max_chars=4000,
        max_tokens=None,
        token_chars=4.0,
        dedup=False,
        token_aware=False,
    ):
        captured_args["dedup"] = dedup
        captured_args["token_aware"] = token_aware
        return {"packed": "mock", "included": [], "chars": 0, "tokens": 0, "budget": {}}

    monkeypatch.setattr(cli.commands.rag, "pack_context", mock_pack)

    result = runner.invoke(app, ["rag", "pack", "test defaults"])
    assert result.exit_code == 0
    assert captured_args.get("dedup") is False
    assert captured_args.get("token_aware") is False
