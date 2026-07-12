import yaml

from app.adapters.agent_ir import AgentExportIR
from app.adapters.langchain import to_langchain_yaml


def test_to_langchain_yaml_contains_expected_keys():
    ir = AgentExportIR(name="Agent", model="claude-opus-4-6", raw_system_prompt="You are helpful.")
    output = to_langchain_yaml(ir)
    parsed = yaml.safe_load(output)
    assert parsed == {
        "model": "claude-opus-4-6",
        "system_prompt": "You are helpful.",
        "input_variables": ["input"],
        "template": "{input}",
    }


def test_to_langchain_yaml_preserves_unicode_and_multiline_prompt():
    ir = AgentExportIR(
        name="Agent",
        model="claude-opus-4-6",
        raw_system_prompt="Çözüm üret.\nBirden fazla satır.",
    )
    output = to_langchain_yaml(ir)
    assert "\\u" not in output
    parsed = yaml.safe_load(output)
    assert parsed["system_prompt"] == "Çözüm üret.\nBirden fazla satır."


def test_to_langchain_yaml_is_valid_yaml_roundtrip():
    ir = AgentExportIR(name="Agent", model="m", raw_system_prompt="")
    output = to_langchain_yaml(ir)
    assert yaml.safe_load(output)["system_prompt"] == ""
