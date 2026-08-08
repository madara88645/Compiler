"""Direct unit coverage for app.adapters.agent_ir._map_sections.

`_map_sections` normalises the raw ## header keys parsed out of Agent
Generator markdown (e.g. "persona", "objective", "tools & capabilities")
into the canonical IR field names (`role`, `goals`, `tech_stack`, ...) via
the `_SECTION_ALIASES` table. It is pure dict-remapping with no I/O, but
was previously only exercised indirectly through `parse_agent_markdown`
end-to-end tests, so its alias resolution and first-wins collision
behavior were never asserted directly.
"""

from app.adapters.agent_ir import _map_sections


class TestMapSections:
    def test_canonical_key_passes_through(self):
        assert _map_sections({"role": "R content"}) == {"role": "R content"}

    def test_alias_key_maps_to_canonical(self):
        assert _map_sections({"persona": "P content"}) == {"role": "P content"}

    def test_multiple_distinct_canonicals(self):
        sections = {"tools": "T1", "constraints": "C1"}
        assert _map_sections(sections) == {"tech_stack": "T1", "constraints": "C1"}

    def test_unknown_header_is_dropped(self):
        assert _map_sections({"random_header": "text"}) == {}

    def test_first_alias_wins_when_multiple_map_to_same_canonical(self):
        # dict preserves insertion order, and _map_sections keeps the first
        # value seen for a given canonical key.
        sections = {"goals": "G1", "objective": "G2", "objectives": "G3"}
        assert _map_sections(sections) == {"goals": "G1"}

    def test_later_alias_wins_if_it_appears_first_in_input(self):
        sections = {"objective": "G2", "goals": "G1"}
        assert _map_sections(sections) == {"goals": "G2"}

    def test_empty_sections_returns_empty_dict(self):
        assert _map_sections({}) == {}

    def test_tech_stack_aliases_all_resolve(self):
        for alias in ("tech stack", "tech", "technology stack", "tools", "capabilities"):
            assert _map_sections({alias: "content"}) == {"tech_stack": "content"}
