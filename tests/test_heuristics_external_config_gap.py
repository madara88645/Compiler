"""Direct unit coverage for app.heuristics._apply_external_config: a pure
dict merge into module globals (DOMAIN_PATTERNS, AMBIGUOUS_TERMS,
RISK_KEYWORDS). The I/O (reading the YAML/JSON file) lives in the caller,
load_external_config; this function only takes an already-parsed dict and
mutates module state, and has zero direct test of malformed-input handling
today.

Because the function reassigns module-level globals via `global`, every
test here restores the original objects afterward so it cannot leak state
into other test modules that rely on the built-in pattern tables.
"""

import pytest

import app.heuristics as heuristics
from app.heuristics import _apply_external_config


@pytest.fixture(autouse=True)
def _restore_config_globals():
    original_domain_patterns = heuristics.DOMAIN_PATTERNS
    original_ambiguous_terms = heuristics.AMBIGUOUS_TERMS
    original_risk_keywords = heuristics.RISK_KEYWORDS
    yield
    heuristics.DOMAIN_PATTERNS = original_domain_patterns
    heuristics.AMBIGUOUS_TERMS = original_ambiguous_terms
    heuristics.RISK_KEYWORDS = original_risk_keywords


def test_empty_dict_leaves_all_globals_unchanged():
    before_domain = heuristics.DOMAIN_PATTERNS
    before_ambiguous = heuristics.AMBIGUOUS_TERMS
    before_risk = heuristics.RISK_KEYWORDS

    _apply_external_config({})

    assert heuristics.DOMAIN_PATTERNS is before_domain
    assert heuristics.AMBIGUOUS_TERMS is before_ambiguous
    assert heuristics.RISK_KEYWORDS is before_risk


def test_unrelated_keys_are_ignored_without_error():
    before_domain = heuristics.DOMAIN_PATTERNS
    _apply_external_config({"some_other_setting": True, "version": 2})
    assert heuristics.DOMAIN_PATTERNS is before_domain


def test_valid_domain_patterns_replaces_global_and_normalizes_to_lists():
    _apply_external_config({"domain_patterns": {"legal": ("sue", "court"), "medicine": ["clinic"]}})
    assert heuristics.DOMAIN_PATTERNS == {"legal": ["sue", "court"], "medicine": ["clinic"]}
    assert isinstance(heuristics.DOMAIN_PATTERNS["legal"], list)


def test_domain_patterns_filters_out_non_list_non_tuple_values():
    _apply_external_config(
        {
            "domain_patterns": {
                "legal": ["sue", "court"],
                "bad_string_value": "not-a-list",
                "bad_int_value": 42,
                "bad_dict_value": {"nested": True},
            }
        }
    )
    assert heuristics.DOMAIN_PATTERNS == {"legal": ["sue", "court"]}
    assert "bad_string_value" not in heuristics.DOMAIN_PATTERNS
    assert "bad_int_value" not in heuristics.DOMAIN_PATTERNS
    assert "bad_dict_value" not in heuristics.DOMAIN_PATTERNS


def test_domain_patterns_with_non_dict_value_is_ignored_entirely():
    before_domain = heuristics.DOMAIN_PATTERNS
    _apply_external_config({"domain_patterns": ["legal", "medicine"]})
    assert heuristics.DOMAIN_PATTERNS is before_domain


def test_domain_patterns_with_all_invalid_entries_yields_empty_dict():
    _apply_external_config({"domain_patterns": {"bad": "nope", "also_bad": 1}})
    assert heuristics.DOMAIN_PATTERNS == {}


def test_valid_ambiguous_terms_replaces_global_verbatim():
    new_terms = {"scale": {"question": "how big?", "category": "sizing"}}
    _apply_external_config({"ambiguous_terms": new_terms})
    assert heuristics.AMBIGUOUS_TERMS == new_terms


def test_ambiguous_terms_with_non_dict_value_is_ignored():
    before_ambiguous = heuristics.AMBIGUOUS_TERMS
    _apply_external_config({"ambiguous_terms": ["scale", "fast"]})
    assert heuristics.AMBIGUOUS_TERMS is before_ambiguous


def test_valid_risk_keywords_replaces_global_verbatim():
    new_risk = {"financial": ["yatirim"], "legal": ["dava"]}
    _apply_external_config({"risk_keywords": new_risk})
    assert heuristics.RISK_KEYWORDS == new_risk


def test_risk_keywords_with_non_dict_value_is_ignored():
    before_risk = heuristics.RISK_KEYWORDS
    _apply_external_config({"risk_keywords": "not-a-dict"})
    assert heuristics.RISK_KEYWORDS is before_risk


def test_all_three_sections_applied_together():
    payload = {
        "domain_patterns": {"legal": ["sue"]},
        "ambiguous_terms": {"scale": {"question": "how big?"}},
        "risk_keywords": {"financial": ["yatirim"]},
    }
    _apply_external_config(payload)
    assert heuristics.DOMAIN_PATTERNS == {"legal": ["sue"]}
    assert heuristics.AMBIGUOUS_TERMS == {"scale": {"question": "how big?"}}
    assert heuristics.RISK_KEYWORDS == {"financial": ["yatirim"]}


def test_malformed_data_with_none_values_for_known_keys_is_ignored():
    before_domain = heuristics.DOMAIN_PATTERNS
    before_ambiguous = heuristics.AMBIGUOUS_TERMS
    before_risk = heuristics.RISK_KEYWORDS

    _apply_external_config({"domain_patterns": None, "ambiguous_terms": None, "risk_keywords": None})

    assert heuristics.DOMAIN_PATTERNS is before_domain
    assert heuristics.AMBIGUOUS_TERMS is before_ambiguous
    assert heuristics.RISK_KEYWORDS is before_risk


def test_function_mutates_actual_module_global_not_a_local_copy():
    # Regression guard for the `global` statement itself: verify the change
    # is visible through the module object, not just a local return value.
    _apply_external_config({"risk_keywords": {"sentinel": ["marker"]}})
    import app.heuristics as reimported

    assert reimported.RISK_KEYWORDS == {"sentinel": ["marker"]}
