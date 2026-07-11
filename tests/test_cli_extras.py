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


def test_diff_ignore_path_nested_key(tmp_path: Path):
    """--ignore-path should suppress differences in a nested dict key."""
    a = {"name": "alpha", "metadata": {"version": 1, "sig": "aaa"}}
    b = {"name": "alpha", "metadata": {"version": 1, "sig": "bbb"}}

    fa = tmp_path / "a.json"
    fb = tmp_path / "b.json"
    fa.write_text(json.dumps(a), encoding="utf-8")
    fb.write_text(json.dumps(b), encoding="utf-8")

    # Without ignore: diff should show differences
    code, out, _ = run_cli(["diff", str(fa), str(fb), "--brief"], Path.cwd())
    assert code == 1, "files differ without ignore-path"

    # With ignore: diff should show no differences (brief exits 0)
    code, out, _ = run_cli(
        ["diff", str(fa), str(fb), "--brief", "--ignore-path", "metadata.sig"], Path.cwd()
    )
    assert code == 0, f"expected no diff after ignoring metadata.sig: {out}"


def test_diff_ignore_path_list_index(tmp_path: Path):
    """--ignore-path should handle bracket list indexes like steps[0]."""
    a = {"steps": ["first", "second", "third"]}
    b = {"steps": ["CHANGED", "second", "third"]}

    fa = tmp_path / "a.json"
    fb = tmp_path / "b.json"
    fa.write_text(json.dumps(a), encoding="utf-8")
    fb.write_text(json.dumps(b), encoding="utf-8")

    # Without ignore: differs
    code, _, _ = run_cli(["diff", str(fa), str(fb), "--brief"], Path.cwd())
    assert code == 1

    # With ignore: removing steps[0] from both makes remaining items align
    code, _, _ = run_cli(
        ["diff", str(fa), str(fb), "--brief", "--ignore-path", "steps[0]"], Path.cwd()
    )
    assert code == 0


def test_diff_ignore_path_missing_key_is_silent(tmp_path: Path):
    """--ignore-path should silently skip paths that don't exist in the JSON."""
    a = {"name": "alpha"}
    b = {"name": "alpha"}

    fa = tmp_path / "a.json"
    fb = tmp_path / "b.json"
    fa.write_text(json.dumps(a), encoding="utf-8")
    fb.write_text(json.dumps(b), encoding="utf-8")

    code, _, _ = run_cli(
        ["diff", str(fa), str(fb), "--brief", "--ignore-path", "nonexistent.deep.path"],
        Path.cwd(),
    )
    assert code == 0
