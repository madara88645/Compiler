import json
import os
import subprocess
import sys
from pathlib import Path

CLI = [sys.executable, "-m", "cli.main"]


def run_cli(args, cwd: Path, env: dict[str, str] | None = None):
    run_env = env if env is not None else os.environ.copy()
    # Force UTF-8 encoding on Windows to handle emojis in JSON output
    run_env["PYTHONIOENCODING"] = "utf-8"
    cp = subprocess.run(
        CLI + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=run_env,
        encoding="utf-8",
    )
    return cp.returncode, cp.stdout.strip(), cp.stderr.strip()


def test_json_path_and_diff(tmp_path: Path):
    # generate two IR files via CLI root command (json-only)
    code, out1, err = run_cli(["compile", "--json-only", "teach me gradient descent"], Path.cwd())
    assert code == 0, f"stdout={out1}\nstderr={err}"
    data1 = json.loads(out1)
    p1 = tmp_path / "a.json"
    p1.write_text(json.dumps(data1), encoding="utf-8")

    code, out2, err = run_cli(
        ["compile", "--json-only", "teach me gradient descent in 10 minutes"], Path.cwd()
    )
    assert code == 0, f"stdout={out2}\nstderr={err}"
    data2 = json.loads(out2)
    p2 = tmp_path / "b.json"
    p2.write_text(json.dumps(data2), encoding="utf-8")

    # json-path should extract a field
    code, jp_out, _ = run_cli(["json-path", str(p1), "language"], Path.cwd())
    assert code == 0, f"stdout={jp_out}"
    assert json.loads(jp_out) in ("en", "tr", "es")

    # diff should show something (or no differences if heuristics match exactly)
    code, d_out, _ = run_cli(["diff", str(p1), str(p2)], Path.cwd())
    assert code == 0
    assert d_out != ""


def test_validate_command(tmp_path: Path):
    # compile a valid IR v2 and validate
    code, out_json, err = run_cli(
        ["compile", "--json-only", "teach me gradient descent"], Path.cwd()
    )
    assert code == 0
    j = tmp_path / "ok.json"
    j.write_text(out_json, encoding="utf-8")

    code, out, err = run_cli(["validate", str(j)], Path.cwd())
    assert code == 0
    assert "[ok]" in out

    # invalid file
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    code, out, err = run_cli(["validate", str(bad)], Path.cwd())
    assert code != 0


def test_batch_command(tmp_path: Path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    (in_dir / "x.txt").write_text("teach me binary search", encoding="utf-8")
    (in_dir / "y.txt").write_text("gift ideas football fan table", encoding="utf-8")

    code, out, err = run_cli(
        ["batch", str(in_dir), "--out-dir", str(out_dir), "--format", "json"], Path.cwd()
    )
    assert code == 0
    assert (out_dir / "x.json").exists()
    assert (out_dir / "y.json").exists()
