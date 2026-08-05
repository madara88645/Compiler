"""
Conservative output-fidelity defaults for Skills Generator formatting intents.

Vague requests like "make agent outputs easier to understand" must not invent
destructive transforms (newline collapsing, fixed-width wrapping) that corrupt
Markdown, URLs, paths, tables, numbers, or error text. This module detects those
intents, supplies safe defaults, and documents transforms that would corrupt
preserved content so tests can lock the contract without calling an LLM.
"""

from __future__ import annotations

import functools
import re
import textwrap
from dataclasses import dataclass

# Categories that formatter skills must preserve unless the user asks otherwise.
PRESERVED_CONTENT_CATEGORIES: tuple[str, ...] = (
    "code_blocks",
    "markdown_structure",
    "urls",
    "file_paths",
    "numeric_values",
    "tables",
    "error_text",
)

# Transforms that are unsafe as silent defaults for vague formatting requests.
UNSAFE_DEFAULT_TRANSFORMS: tuple[str, ...] = (
    "collapse_newlines",
    "wrap_at_80_columns",
    "strip_markdown_markup",
    "normalize_urls",
    "reflow_tables",
    "rewrite_error_messages",
)

_FORMAT_INTENT_RAW_PATTERNS: tuple[str, ...] = (
    r"\bformat(?:ting|ter)?\b",
    r"\breformat\b",
    r"\bpretty[\s-]?print\b",
    r"\breadab(?:le|ility)\b",
    r"\beasier to (?:read|understand|scan)\b",
    r"\bmake (?:it |output |outputs |the (?:output|response) )?clear(?:er)?\b",
    r"\bclean(?:\s+up)?\s+(?:the\s+)?(?:output|response|text)\b",
    r"\bnormalize\s+(?:the\s+)?(?:output|text|whitespace)\b",
    r"\bwrap\s+(?:lines?|text|output)\b",
    r"\boutput\s+(?:format|style|clarity)\b",
)

# Samples used by value tests / corruption checks — intentionally fragile under
# naive wrap/collapse transforms.
CORRUPTION_SAMPLES: dict[str, str] = {
    # URL / path tokens longer than 80 chars so fixed-width wrap splits them.
    "urls": (
        "https://example.com/api/v1/organizations/acme-corp/users/"
        "profile?id=42&sort=name&include=roles,permissions,audit"
    ),
    "file_paths": (
        "/Users/mehmet/Developer/personal/Compiler/app/llm_engine/skill_output_fidelity.py:118"
    ),
    "tables": "| name | score |\n| --- | ---: |\n| alpha | 12.5 |\n| beta | 0.003 |",
    # Long unbroken tokens so fixed-width wrap splits mid-value / mid-key.
    "numeric_values": (
        "metric=latency_p99_was_12.50ms_and_retry_after_1.25s_on_attempt_3_of_5_total_runs"
    ),
    "error_text": (
        "ERROR_ValueError_expected_dict_got_str_at_key_formatted_output_during_export_step"
    ),
    "markdown_structure": "## Summary\n\n- Keep **bold** and `inline code`\n- Leave lists intact",
    "code_blocks": "Before\n```python\ndef f(x):\n    return x + 1\n```\nAfter",
}


@dataclass(frozen=True)
class OutputFidelityPolicy:
    """Safe contract for an output-formatting skill."""

    is_formatting_intent: bool
    user_requested_transforms: tuple[str, ...]
    preserve: tuple[str, ...]
    forbid_by_default: tuple[str, ...]
    output_schema_contract: str
    clarification_needed: bool
    clarification_question: str | None


@functools.lru_cache(maxsize=1)
def _get_combined_format_intent_pattern() -> re.Pattern[str]:
    # Bolt Optimization: Combine regexes with OR and cache to eliminate redundant compilation overhead
    return re.compile(r"|".join(_FORMAT_INTENT_RAW_PATTERNS), re.IGNORECASE)


def is_output_formatting_intent(description: str) -> bool:
    """Return True when the request is primarily about formatting / readability."""
    text = (description or "").strip()
    if not text:
        return False
    return _get_combined_format_intent_pattern().search(text) is not None


def detect_explicit_transform_requests(description: str) -> tuple[str, ...]:
    """Return unsafe-transform ids the user explicitly asked for."""
    text = description or ""
    found: list[str] = []
    mapping = (
        (r"\bcollapse\s+newlines?\b", "collapse_newlines"),
        (r"\bwrap\s+(?:at|to)\s+\d{2,3}\b|\b\d{2,3}[\s-]?column\b", "wrap_at_80_columns"),
        (r"\b(?:strip|remove)\s+markdown\b", "strip_markdown_markup"),
        (r"\breflow\s+tables?\b", "reflow_tables"),
        (r"\brewrite\s+errors?\b", "rewrite_error_messages"),
        (r"\bnormalize\s+urls?\b", "normalize_urls"),
    )
    for pattern, transform_id in mapping:
        if re.search(pattern, text, re.IGNORECASE) and transform_id not in found:
            found.append(transform_id)
    return tuple(found)


def default_formatter_output_schema() -> str:
    """
    One unambiguous output contract for formatter skills.

    Avoids the dual-contract failure mode of ``Type: str`` plus a separate
    ``formatted_output`` field description.
    """
    return (
        "**Type:** `dict`\n"
        "- `formatted_text` (str): The fidelity-preserving formatted result.\n"
        "- `warnings` (list[str]): Non-fatal notes (e.g. skipped transforms); empty when none."
    )


def build_output_fidelity_policy(description: str) -> OutputFidelityPolicy:
    """Derive the conservative fidelity policy for a skill description."""
    formatting = is_output_formatting_intent(description)
    explicit = detect_explicit_transform_requests(description) if formatting else ()
    clarification_needed = False
    clarification_question = None
    if formatting and not explicit and _is_highly_ambiguous(description):
        clarification_needed = True
        clarification_question = (
            "Should the skill only improve readability while preserving Markdown, URLs, "
            "paths, tables, numbers, and error text, or do you also want a specific "
            "transform (for example wrap-at-N or collapse blank lines)?"
        )

    return OutputFidelityPolicy(
        is_formatting_intent=formatting,
        user_requested_transforms=explicit,
        preserve=PRESERVED_CONTENT_CATEGORIES if formatting else (),
        forbid_by_default=tuple(t for t in UNSAFE_DEFAULT_TRANSFORMS if t not in explicit)
        if formatting
        else (),
        output_schema_contract=default_formatter_output_schema() if formatting else "",
        clarification_needed=clarification_needed,
        clarification_question=clarification_question,
    )


def _is_highly_ambiguous(description: str) -> bool:
    """True when the request is vague enough that a short clarification helps."""
    text = (description or "").strip()
    words = re.findall(r"[A-Za-z0-9']+", text)
    concrete = re.search(
        r"\b(json|yaml|markdown|csv|html|xml|table|bullet|numbered)\b",
        text,
        re.IGNORECASE,
    )
    return len(words) <= 12 and concrete is None


def would_corrupt_preserved_content(transform: str, sample_key: str) -> bool:
    """
    Return True when applying ``transform`` to a known sample damages meaning.

    Used as a deterministic negative-case oracle for value tests — not as a
    general formatter implementation.
    """
    if transform not in UNSAFE_DEFAULT_TRANSFORMS:
        return False
    sample = CORRUPTION_SAMPLES.get(sample_key)
    if sample is None:
        return False

    if transform == "collapse_newlines":
        if sample_key not in {"tables", "code_blocks", "markdown_structure"}:
            return False
        collapsed = re.sub(r"\n+", " ", sample)
        return collapsed != sample

    if transform == "wrap_at_80_columns":
        # Soft-wrap after flattening newlines — the unsafe default called out in #1156.
        flattened = sample.replace("\n", " ")
        wrapped_lines = textwrap.wrap(flattened, width=80) if flattened else []
        wrapped = "\n".join(wrapped_lines)
        if sample_key == "urls":
            return sample not in wrapped  # wrap splits the contiguous URL token
        if sample_key == "file_paths":
            return sample not in wrapped
        if sample_key == "tables":
            # Flattening + wrap destroys row/column structure.
            return True
        if sample_key in {"numeric_values", "error_text"}:
            # Contiguous machine-readable tokens must stay intact; wrap breaks them.
            return sample not in wrapped
        return False

    if transform == "strip_markdown_markup":
        if sample_key not in {"markdown_structure", "tables", "code_blocks"}:
            return False
        stripped = re.sub(r"[#*`|_]", "", sample)
        return stripped != sample

    if transform == "normalize_urls":
        if sample_key != "urls":
            return False
        # Naive "normalization" that drops query strings corrupts the link.
        normalized = re.sub(r"\?[^\s]*", "", sample)
        return "id=42" not in normalized

    if transform == "reflow_tables":
        if sample_key != "tables":
            return False
        reflowed = " ".join(sample.split())
        return "\n" in sample and "\n" not in reflowed

    if transform == "rewrite_error_messages":
        if sample_key != "error_text":
            return False
        return "ValueError" not in "Something went wrong."

    return False


def build_output_fidelity_guidance(description: str) -> str | None:
    """
    System-message guidance injected when the user request is a formatting intent.

    Returns None for non-formatting requests so other skills stay unchanged.
    """
    policy = build_output_fidelity_policy(description)
    if not policy.is_formatting_intent:
        return None

    preserve_list = ", ".join(policy.preserve)
    forbid_list = ", ".join(policy.forbid_by_default)
    lines = [
        "Output-fidelity requirements for this formatting skill:",
        f"- Preserve by default: {preserve_list}.",
        "- Do NOT invent destructive defaults such as newline collapsing or fixed-width "
        "line wrapping unless the user explicitly requested them.",
        f"- Forbidden unless explicitly requested: {forbid_list}.",
        "- Use exactly one unambiguous Output Schema contract (not Type: str plus a "
        "separate formatted_output field). Prefer:",
        policy.output_schema_contract,
        "- In Implementation and Testing Strategy, include negative cases showing that "
        "wrapping/normalization must not corrupt URLs, paths, tables, numbers, or errors.",
    ]
    if policy.clarification_needed and policy.clarification_question:
        lines.append(
            "- Because the request is ambiguous, begin the skill Purpose/Implementation "
            f"with a concise clarification step: {policy.clarification_question}"
        )
    else:
        lines.append(
            "- The request is vague but safe defaults apply — do not ask the user to "
            "supply a full implementation contract; ship the fidelity-preserving skill."
        )
    return "\n".join(lines)


def output_schema_is_ambiguous(schema_markdown: str) -> bool:
    """
    Detect the dual-contract failure: top-level Type:str plus a separate
    formatted_output field (or conflicting type claims).
    """
    text = schema_markdown or ""
    type_match = re.search(
        r"\*\*\s*type\s*:?\s*\*\*\s*`?\s*([A-Za-z][A-Za-z0-9_]*)\s*`?",
        text,
        re.IGNORECASE,
    )
    has_formatted_field = bool(
        re.search(r"\bformatted_output\b|\bformatted_text\b", text, re.IGNORECASE)
    )
    if type_match and type_match.group(1).lower() in {"str", "string", "text"}:
        if has_formatted_field:
            return True
    # Two competing Type markers also count as ambiguous.
    type_tags = re.findall(
        r"\*\*\s*type\s*:?\s*\*\*\s*`?\s*[A-Za-z][A-Za-z0-9_]*\s*`?",
        text,
        re.IGNORECASE,
    )
    return len(type_tags) > 1
