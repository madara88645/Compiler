import json
import yaml
from unittest.mock import patch
from app.batch import batch_process_files


def test_batch_process_files_flat(tmp_path):
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    input_dir.mkdir()

    # Create test prompt files
    file1 = input_dir / "prompt1.txt"
    file1.write_text("summarize a PDF and write a report", encoding="utf-8")
    file2 = input_dir / "prompt2.txt"
    file2.write_text("create a marketing email", encoding="utf-8")

    # Run batch process with json output
    res = batch_process_files(
        input_dir=input_dir,
        output_dir=output_dir,
        patterns=["*.txt"],
        output_format="json",
        recursive=False,
    )

    assert res.total == 2
    assert res.successful == 2
    assert res.failed == 0
    assert res.duration > 0.0

    # Check outputs
    out_file1 = output_dir / "prompt1.json"
    out_file2 = output_dir / "prompt2.json"
    assert out_file1.exists()
    assert out_file2.exists()

    # Verify content
    data1 = json.loads(out_file1.read_text(encoding="utf-8"))
    assert "persona" in data1
    assert "role" in data1


def test_batch_process_files_yaml_and_expanded(tmp_path):
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    input_dir.mkdir()

    file1 = input_dir / "prompt1.txt"
    file1.write_text("summarize a PDF and write a report", encoding="utf-8")

    # Test yaml format
    res_yaml = batch_process_files(
        input_dir=input_dir,
        output_dir=output_dir,
        patterns=["*.txt"],
        output_format="yaml",
        recursive=False,
    )
    assert res_yaml.successful == 1
    out_yaml = output_dir / "prompt1.yaml"
    assert out_yaml.exists()
    yaml_data = yaml.safe_load(out_yaml.read_text(encoding="utf-8"))
    assert "persona" in yaml_data

    # Test expanded format
    res_exp = batch_process_files(
        input_dir=input_dir,
        output_dir=output_dir,
        patterns=["*.txt"],
        output_format="expanded",
        recursive=False,
    )
    assert res_exp.successful == 1
    out_exp = output_dir / "prompt1.md"
    assert out_exp.exists()


def test_batch_process_files_recursive_and_jsonl(tmp_path):
    input_dir = tmp_path / "inputs"
    sub_dir = input_dir / "nested"
    output_dir = tmp_path / "outputs"
    sub_dir.mkdir(parents=True)

    file1 = input_dir / "prompt1.txt"
    file1.write_text("summarize a PDF", encoding="utf-8")
    file2 = sub_dir / "prompt2.txt"
    file2.write_text("write a report", encoding="utf-8")

    jsonl_path = tmp_path / "output.jsonl"

    res = batch_process_files(
        input_dir=input_dir,
        output_dir=output_dir,
        patterns=["*.txt"],
        output_format="json",
        recursive=True,
        jsonl_output_path=jsonl_path,
    )

    assert res.total == 2
    assert res.successful == 2
    assert jsonl_path.exists()

    # Read jsonl lines
    lines = jsonl_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    assert "persona" in json.loads(lines[0])


def test_batch_process_files_failures(tmp_path):
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    input_dir.mkdir()

    file1 = input_dir / "prompt1.txt"
    file1.write_text("summarize a PDF", encoding="utf-8")

    # Mock compile_text_v2 to raise an exception
    with patch("app.batch.compile_text_v2", side_effect=ValueError("Mock Error")):
        res = batch_process_files(
            input_dir=input_dir, output_dir=output_dir, patterns=["*.txt"], output_format="json"
        )

        assert res.total == 1
        assert res.successful == 0
        assert res.failed == 1
        assert len(res.failures) == 1
        assert res.failures[0]["file"] == str(file1)
        assert "An internal error occurred" in res.failures[0]["error"]
