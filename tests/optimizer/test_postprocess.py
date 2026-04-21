from __future__ import annotations

import time

import pytest

from app.optimizer.postprocess import strip_wrapper_labels


@pytest.mark.parametrize(
    "text",
    [
        "**Optimized Prompt**:\nHello body",
        "Optimized Prompt:\n\nClean body text",
        "### Result\n\nBody",
        "> **Output**\n\nReal prompt body",
        "Here is the optimized prompt:\n\nBody",
        "Body without any wrapper label",
    ],
)
def test_strip_wrapper_labels_is_idempotent(text: str) -> None:
    once = strip_wrapper_labels(text)
    twice = strip_wrapper_labels(once)
    assert once == twice


def test_strip_wrapper_labels_handles_pathological_decoration_quickly() -> None:
    hostile = "-" * 10_000 + "\nreal body"
    start = time.perf_counter()
    result = strip_wrapper_labels(hostile)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.1, f"strip_wrapper_labels was too slow: {elapsed:.3f}s"
    assert result == hostile


def test_strip_wrapper_labels_preserves_code_fence_prefix() -> None:
    text = "```python\nprint('hi')\n```"
    assert strip_wrapper_labels(text) == text


def test_strip_wrapper_labels_keeps_leading_blank_lines_contract() -> None:
    text = "\n\n**Optimized Prompt**:\nreal body"
    assert strip_wrapper_labels(text) == "real body"


def test_strip_wrapper_labels_noop_on_empty_string() -> None:
    assert strip_wrapper_labels("") == ""
