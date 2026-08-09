"""Direct unit tests for `_map_sections` in app.adapters.agent_ir.

`_map_sections` normalises raw markdown section keys (as parsed from
`## Header` lines) into a small canonical set using the `_SECTION_ALIASES`
table, keeping the first canonical match on collision. It was previously
only exercised indirectly through full `_build_ir` / markdown-to-agent
conversion tests.
"""

from app.adapters.agent_ir import _map_sections


def test_map_sections_maps_known_alias_to_canonical_key():
    assert _map_sections({"objective": "Ship the feature"}) == {"goals": "Ship the feature"}


def test_map_sections_leaves_already_canonical_keys_unchanged():
    assert _map_sections({"role": "You are an assistant"}) == {"role": "You are an assistant"}


def test_map_sections_drops_unrecognized_keys():
    assert _map_sections({"random_header": "some content"}) == {}


def test_map_sections_first_canonical_wins_on_collision():
    # "goal" and "objectives" both alias to "goals" — dict preserves insertion
    # order, so whichever is encountered first should win.
    sections = {"goal": "first goal text", "objectives": "second goal text"}
    result = _map_sections(sections)
    assert result == {"goals": "first goal text"}


def test_map_sections_merges_multiple_distinct_aliases_into_shared_canonical():
    sections = {
        "rules": "no PII",
        "limitations": "read-only",
        "tech": "Python",
    }
    result = _map_sections(sections)
    # "rules" wins over "limitations" for the "constraints" bucket.
    assert result == {"constraints": "no PII", "tech_stack": "Python"}


def test_map_sections_empty_input_returns_empty_dict():
    assert _map_sections({}) == {}


def test_map_sections_case_sensitive_alias_lookup():
    # The alias table keys are lowercase; an uppercase raw key (as could
    # theoretically be passed directly) will not match and is dropped.
    assert _map_sections({"ROLE": "text"}) == {}
