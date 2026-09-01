"""Direct unit tests for app.adapters.agent_ir._map_sections.

Normalises raw markdown section headers to canonical AgentExportIR field
names via the `_SECTION_ALIASES` table, first-write-wins per canonical key.
"""

from __future__ import annotations

from app.adapters.agent_ir import _map_sections


def test_empty_input_returns_empty_dict():
    assert _map_sections({}) == {}


def test_unknown_key_is_dropped():
    assert _map_sections({"unknown_header": "some text"}) == {}


def test_known_key_maps_to_canonical_name():
    assert _map_sections({"role": "You are an assistant."}) == {"role": "You are an assistant."}


def test_alias_maps_to_same_canonical_as_primary():
    assert _map_sections({"persona": "You are a helper."}) == {"role": "You are a helper."}


def test_tech_stack_multi_word_alias():
    result = _map_sections({"tools & capabilities": "Python, FastAPI"})
    assert result == {"tech_stack": "Python, FastAPI"}


def test_first_write_wins_for_duplicate_canonical_targets():
    # "goal" and "objective" both alias to "goals"; "goal" appears first in
    # insertion order and must win over the later-seen "objective".
    sections = {"goal": "First value", "objective": "Second value", "goals": "Third value"}
    assert _map_sections(sections) == {"goals": "First value"}


def test_first_write_wins_regardless_of_which_alias_appears_first():
    sections = {"persona": "P1", "role": "R1"}
    assert _map_sections(sections) == {"role": "P1"}


def test_multiple_distinct_canonical_targets_all_present():
    sections = {
        "role": "R",
        "constraints": "C",
        "workflow": "W",
        "tech": "T",
    }
    assert _map_sections(sections) == {
        "role": "R",
        "constraints": "C",
        "workflows": "W",
        "tech_stack": "T",
    }


def test_mix_of_known_and_unknown_keys():
    sections = {"role": "R", "random_section": "junk"}
    assert _map_sections(sections) == {"role": "R"}


def test_constraint_singular_and_plural_alias_to_same_field():
    sections = {"rule": "R1", "rules": "R2", "limitations": "R3"}
    assert _map_sections(sections) == {"constraints": "R1"}
