import pytest
from typer.testing import CliRunner
from cli.main import app
import json

runner = CliRunner()

def test_json_path_output_formatting(tmp_path):
    test_file = tmp_path / "test.json"
    data = {"hello": "world", "nested": {"key": "value"}}
    test_file.write_text(json.dumps(data, ensure_ascii=False))

    result = runner.invoke(app, ["json-path", str(test_file), "nested"])
    assert result.exit_code == 0
    # Expected behavior: json.dumps will format it exactly with a space after colon
    assert '{"key": "value"}' in result.stdout

def test_json_path_string_output(tmp_path):
    test_file = tmp_path / "test.json"
    data = {"greeting": "hello world"}
    test_file.write_text(json.dumps(data, ensure_ascii=False))

    result = runner.invoke(app, ["json-path", str(test_file), "greeting"])
    assert result.exit_code == 0
    # json.dumps of string will be "hello world" with quotes
    assert '"hello world"' in result.stdout

def test_diff_json_output(tmp_path):
    f1 = tmp_path / "1.json"
    f2 = tmp_path / "2.json"
    f1.write_text('{"a": 1, "b": 2}')
    f2.write_text('{"a": 1, "b": 3}')
    result = runner.invoke(app, ["diff", str(f1), str(f2)])
    assert result.exit_code == 0
    # We should see difflib output formatted exactly with indent 2 because of orjson OPT_INDENT_2
    assert '-  "b": 2' in result.stdout or '-  "b": 2,' in result.stdout
