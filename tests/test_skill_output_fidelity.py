"""Value tests for Skills Generator output-fidelity defaults (#1156)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.llm_engine.client import WorkerClient
from app.llm_engine.skill_output_fidelity import (
    CORRUPTION_SAMPLES,
    PRESERVED_CONTENT_CATEGORIES,
    UNSAFE_DEFAULT_TRANSFORMS,
    build_output_fidelity_guidance,
    build_output_fidelity_policy,
    default_formatter_output_schema,
    is_output_formatting_intent,
    output_schema_is_ambiguous,
    would_corrupt_preserved_content,
)


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "app" / "llm_engine" / "prompts"
SKILLS_PROMPT = (PROMPTS_DIR / "skills_generator.md").read_text(encoding="utf-8")


VAGUE_FORMATTING_REQUESTS = (
    "make agent outputs easier to understand",
    "format the response for readability",
    "clean up the output text",
    "pretty-print agent replies",
)

RECENT_REGEX_VARIANT_REQUESTS = (
    "make the response clearer",
    "normalize the output whitespace",
    "wrap output for readability",
    "improve output style for support replies",
)

NON_FORMATTING_REQUESTS = (
    "validate JSON payloads against a schema",
    "scrape product prices from a public page",
    "summarize a PDF for executives",
)


@pytest.mark.parametrize("description", VAGUE_FORMATTING_REQUESTS)
def test_detects_vague_formatting_intents(description: str) -> None:
    assert is_output_formatting_intent(description) is True
    policy = build_output_fidelity_policy(description)
    assert policy.is_formatting_intent is True
    assert policy.preserve == PRESERVED_CONTENT_CATEGORIES
    assert "collapse_newlines" in policy.forbid_by_default
    assert "wrap_at_80_columns" in policy.forbid_by_default


@pytest.mark.parametrize("description", RECENT_REGEX_VARIANT_REQUESTS)
def test_recent_regex_variants_trigger_formatting_policy(description: str) -> None:
    assert is_output_formatting_intent(description) is True
    policy = build_output_fidelity_policy(description)
    assert policy.is_formatting_intent is True
    assert policy.preserve == PRESERVED_CONTENT_CATEGORIES


@pytest.mark.parametrize("description", NON_FORMATTING_REQUESTS)
def test_non_formatting_requests_skip_fidelity_policy(description: str) -> None:
    assert is_output_formatting_intent(description) is False
    assert build_output_fidelity_guidance(description) is None
    policy = build_output_fidelity_policy(description)
    assert policy.preserve == ()
    assert policy.forbid_by_default == ()


def test_generic_wrap_request_still_forbids_fixed_width_wrap_by_default() -> None:
    policy = build_output_fidelity_policy("wrap output for readability")
    assert policy.user_requested_transforms == ()
    assert "wrap_at_80_columns" in policy.forbid_by_default
    assert policy.clarification_needed is True


def test_vague_formatting_policy_preserves_required_categories() -> None:
    policy = build_output_fidelity_policy("make agent outputs easier to understand")
    for category in (
        "code_blocks",
        "markdown_structure",
        "urls",
        "file_paths",
        "numeric_values",
        "tables",
        "error_text",
    ):
        assert category in policy.preserve


def test_default_output_schema_is_single_unambiguous_contract() -> None:
    schema = default_formatter_output_schema()
    assert "**Type:** `dict`" in schema
    assert "formatted_text" in schema
    assert output_schema_is_ambiguous(schema) is False


def test_dual_str_and_formatted_output_schema_is_ambiguous() -> None:
    bad = (
        "**Type:** `str`\n"
        "- `formatted_output` (str): The cleaned text\n"
        "- `notes` (list): Extra metadata\n"
    )
    assert output_schema_is_ambiguous(bad) is True


def test_explicit_wrap_request_lifts_forbid_for_that_transform_only() -> None:
    policy = build_output_fidelity_policy("format output for readability and wrap at 80 columns")
    assert "wrap_at_80_columns" in policy.user_requested_transforms
    assert "wrap_at_80_columns" not in policy.forbid_by_default
    assert "collapse_newlines" in policy.forbid_by_default


@pytest.mark.parametrize(
    ("transform", "sample_key"),
    [
        ("collapse_newlines", "tables"),
        ("collapse_newlines", "code_blocks"),
        ("collapse_newlines", "markdown_structure"),
        ("wrap_at_80_columns", "urls"),
        ("wrap_at_80_columns", "file_paths"),
        ("wrap_at_80_columns", "tables"),
        ("wrap_at_80_columns", "numeric_values"),
        ("wrap_at_80_columns", "error_text"),
        ("strip_markdown_markup", "markdown_structure"),
        ("normalize_urls", "urls"),
        ("reflow_tables", "tables"),
        ("rewrite_error_messages", "error_text"),
    ],
)
def test_unsafe_defaults_corrupt_preserved_content(transform: str, sample_key: str) -> None:
    assert sample_key in CORRUPTION_SAMPLES
    assert transform in UNSAFE_DEFAULT_TRANSFORMS
    assert would_corrupt_preserved_content(transform, sample_key) is True


def test_skills_generator_prompt_documents_fidelity_defaults() -> None:
    assert "## OUTPUT FIDELITY DEFAULTS" in SKILLS_PROMPT
    assert "## OUTPUT SCHEMA CONTRACT" in SKILLS_PROMPT
    assert "newline collapsing" in SKILLS_PROMPT
    assert "80-column" in SKILLS_PROMPT
    assert "formatted_output" in SKILLS_PROMPT
    for phrase in (
        "code blocks",
        "Markdown structure",
        "URLs",
        "file paths",
        "numeric values",
        "tables",
        "error",
    ):
        assert phrase in SKILLS_PROMPT


def test_generate_skill_injects_fidelity_guidance_for_vague_formatting() -> None:
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")

    captured: dict = {}

    def fake_call_api(messages, max_tokens, json_mode, model_override=None, usage_sink=None):
        captured["messages"] = messages
        return "# Skill Definition"

    with patch.object(client, "_call_api", side_effect=fake_call_api):
        result = client.generate_skill(
            "make agent outputs easier to understand",
            include_example_code=False,
        )

    assert result == "# Skill Definition"
    system_messages = [msg["content"] for msg in captured["messages"] if msg["role"] == "system"]
    assert any("Output-fidelity requirements" in message for message in system_messages)
    assert any("Preserve by default" in message for message in system_messages)
    assert any("wrap_at_80_columns" in message for message in system_messages)
    assert any("formatted_text" in message for message in system_messages)


def test_generate_skill_injects_fidelity_guidance_for_normalize_output_request() -> None:
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")

    captured: dict = {}

    def fake_call_api(messages, max_tokens, json_mode, model_override=None, usage_sink=None):
        captured["messages"] = messages
        return "# Skill Definition"

    with patch.object(client, "_call_api", side_effect=fake_call_api):
        result = client.generate_skill(
            "normalize the output whitespace",
            include_example_code=False,
        )

    assert result == "# Skill Definition"
    system_messages = [msg["content"] for msg in captured["messages"] if msg["role"] == "system"]
    assert any("Output-fidelity requirements" in message for message in system_messages)
    assert any("Preserve by default" in message for message in system_messages)
    assert any("clarification step" in message for message in system_messages)


def test_generate_skill_skips_fidelity_guidance_for_unrelated_skills() -> None:
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")

    captured: dict = {}

    def fake_call_api(messages, max_tokens, json_mode, model_override=None, usage_sink=None):
        captured["messages"] = messages
        return "# Skill Definition"

    with patch.object(client, "_call_api", side_effect=fake_call_api):
        client.generate_skill("validate JSON payloads against a schema")

    system_messages = [msg["content"] for msg in captured["messages"] if msg["role"] == "system"]
    assert not any("Output-fidelity requirements" in message for message in system_messages)


def test_ambiguous_readability_request_gets_clarification_step() -> None:
    policy = build_output_fidelity_policy("make outputs clearer")
    assert policy.clarification_needed is True
    assert policy.clarification_question is not None
    guidance = build_output_fidelity_guidance("make outputs clearer")
    assert guidance is not None
    assert "clarification step" in guidance
