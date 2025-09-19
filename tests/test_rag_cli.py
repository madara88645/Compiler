from __future__ import annotations
import json
from pathlib import Path
from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


def write_sample(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    # Two small files to ensure >1 chunks possible
    (src / "a.txt").write_text(
        """
Gradient descent adjusts parameters by moving opposite the gradient.
Learning rates control step size.
""".strip(),
        encoding="utf-8",
    )
    (src / "b.md").write_text(
        """
# Teaching persona
A teaching assistant explains concepts clearly with steps and examples.
""".strip(),
        encoding="utf-8",
    )
    return src


def test_rag_index_and_query(tmp_path: Path):
    src = write_sample(tmp_path)
    db_path = tmp_path / "index.db"

    # Index the folder
    result = runner.invoke(
        app, ["rag", "index", str(src), "--db-path", str(db_path), "--ext", ".txt", "--ext", ".md"]
    )
    assert result.exit_code == 0, result.output
    assert db_path.exists(), "Database file should be created"

    # Query a term from the .txt file
    q1 = runner.invoke(
        app, ["rag", "query", "gradient descent", "--db-path", str(db_path), "--k", "3", "--json"]
    )
    assert q1.exit_code == 0, q1.output
    data = json.loads(q1.output)
    assert isinstance(data, list)
    # We expect at least one hit containing our .txt
    assert any("a.txt" in (r.get("path") or "") for r in data)

    # Query a term from the .md file
    q2 = runner.invoke(
        app, ["rag", "query", "teaching persona", "--db-path", str(db_path), "--k", "3", "--json"]
    )
    assert q2.exit_code == 0, q2.output
    data2 = json.loads(q2.output)
    assert isinstance(data2, list)
    assert any("b.md" in (r.get("path") or "") for r in data2)
