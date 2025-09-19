import sys
import subprocess
from pathlib import Path

CLI = [sys.executable, "-m", "cli.main"]


def run_cli(args, cwd: Path):
    cp = subprocess.run(CLI + args, cwd=str(cwd), capture_output=True, text=True)
    return cp.returncode, cp.stdout.strip(), cp.stderr.strip()


def test_batch_name_template_and_json_path_raw(tmp_path: Path):
    inp = tmp_path / "inputs"
    outd = tmp_path / "outs"
    inp.mkdir()
    (inp / "alpha.txt").write_text("teach me hashing basics", encoding="utf-8")
    (inp / "beta.txt").write_text("gift ideas tech friend table", encoding="utf-8")
    code, out, err = run_cli(
        [
            "batch",
            str(inp),
            "--out-dir",
            str(outd),
            "--format",
            "json",
            "--name-template",
            "{stem}-X.{ext}",
        ],
        Path.cwd(),
    )
    assert code == 0, err
    # Expect templated filenames
    assert (outd / "alpha-X.json").exists()
    assert (outd / "beta-X.json").exists()
    # Raw json-path output (should be unquoted if scalar)
    any_file = next(outd.glob("*.json"))
    code, raw_out, _ = run_cli(["json-path", str(any_file), "language", "--raw"], Path.cwd())
    assert code == 0
    assert raw_out in ("en", "tr", "es")


def test_validate_summary_and_api_schemas(tmp_path: Path):
    # Produce a valid IR file
    code, out, err = run_cli(["compile", "--json-only", "teach me recursion"], Path.cwd())
    assert code == 0
    valid = tmp_path / "valid.json"
    valid.write_text(out, encoding="utf-8")
    # Corrupt file
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    code, v_out, v_err = run_cli(["validate", str(valid), str(invalid)], Path.cwd())
    assert code != 0  # invalid triggers non-zero
    assert "Summary:" in v_out or "Summary:" in v_err
    # Simple schema endpoint checks (skip if server not running)
    import socket

    def port_open(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.25)
            return s.connect_ex(("127.0.0.1", port)) == 0

    if port_open(8000):  # opportunistic integration check
        import urllib.request
        import json as _j

        for p in ("/schema/ir_v1", "/schema/ir_v2"):
            with urllib.request.urlopen(f"http://127.0.0.1:8000{p}") as resp:
                data = _j.loads(resp.read().decode("utf-8"))
                assert "schema" in data and isinstance(data["schema"], str)
