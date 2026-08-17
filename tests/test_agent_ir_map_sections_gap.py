"""Direct unit coverage for app.adapters.agent_ir._map_sections: the pure
dict alias-normalization step in the agent-markdown parser. It silently
drops unmapped and duplicate-canonical sections, which is untested in
isolation today (only exercised indirectly via _build_ir).
"""

from app.adapters.agent_ir import _map_sections


def test_maps_known_aliases_to_canonical_names():
    sections = {"role": "does X", "goal": "ship Y", "constraints": "no Z"}
    mapped = _map_sections(sections)
    assert mapped == {"role": "does X", "goals": "ship Y", "constraints": "no Z"}


def test_unmapped_section_is_silently_dropped():
    sections = {"role": "does X", "random notes": "this has no alias"}
    mapped = _map_sections(sections)
    assert mapped == {"role": "does X"}
    assert "random notes" not in mapped


def test_all_unmapped_sections_yields_empty_dict():
    sections = {"foo": "bar", "misc": "baz"}
    assert _map_sections(sections) == {}


def test_empty_input_yields_empty_dict():
    assert _map_sections({}) == {}


def test_first_occurrence_wins_for_duplicate_canonical_targets():
    # "goals", "goal", "objective", and "objectives" all map to "goals" —
    # the first one encountered (in dict/insertion order) must win, and
    # later ones for the same canonical target are dropped.
    sections = {
        "objective": "first content",
        "goals": "second content",
        "objectives": "third content",
    }
    mapped = _map_sections(sections)
    assert mapped == {"goals": "first content"}


def test_distinct_aliases_for_same_target_do_not_produce_duplicate_key():
    sections = {"rule": "be nice", "constraint": "no rudeness", "limitations": "keep it short"}
    mapped = _map_sections(sections)
    # Only one "constraints" key can exist in the output dict; the first
    # alias processed (insertion order) determines the surviving value.
    assert mapped == {"constraints": "be nice"}


def test_alias_lookup_is_case_sensitive_and_requires_lowercase_keys():
    # The alias table only defines lowercase keys; _parse_sections lowercases
    # raw section headers before calling this, but _map_sections itself does
    # no normalization, so an uppercase raw key is treated as unmapped.
    sections = {"Role": "does X"}
    assert _map_sections(sections) == {}


def test_tools_and_tech_stack_aliases_both_map_to_tech_stack():
    sections = {"tools": "uses pytest", "tech stack": "python, fastapi"}
    mapped = _map_sections(sections)
    assert mapped == {"tech_stack": "uses pytest"}


def test_multiple_distinct_canonical_targets_all_survive():
    sections = {
        "persona": "a helpful bot",
        "objective": "ship features",
        "rule": "be concise",
        "steps": "1. plan 2. build",
        "capabilities": "python, sql",
    }
    mapped = _map_sections(sections)
    assert mapped == {
        "role": "a helpful bot",
        "goals": "ship features",
        "constraints": "be concise",
        "workflows": "1. plan 2. build",
        "tech_stack": "python, sql",
    }


def test_content_value_is_passed_through_unmodified():
    multiline_content = "line one\nline two\n- bullet"
    sections = {"goals": multiline_content}
    mapped = _map_sections(sections)
    assert mapped["goals"] == multiline_content
