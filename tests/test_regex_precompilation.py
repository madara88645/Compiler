"""Tests for regex pre-compilation in DomainHandler."""
import re
import pytest
from app.heuristics.handlers.domain_expert import DomainHandler


@pytest.fixture
def handler():
    return DomainHandler()


class TestRegexPrecompilation:
    """Verify all patterns are pre-compiled during __init__."""

    def test_domain_keywords_compiled(self, handler):
        assert hasattr(handler, "_domain_keywords")
        assert len(handler._domain_keywords) > 0
        for pat in handler._domain_keywords.values():
            assert isinstance(pat, re.Pattern)

    def test_coding_universal_checks_compiled(self, handler):
        assert hasattr(handler, "_compiled_universal_checks")
        assert "security" in handler._compiled_universal_checks
        for check_name, compiled in handler._compiled_universal_checks.items():
            pat = compiled.get("missing")
            if pat:
                assert isinstance(pat, re.Pattern), f"{check_name} missing_pattern not compiled"
            pat = compiled.get("risk")
            if pat:
                assert isinstance(pat, re.Pattern), f"{check_name} risk_pattern not compiled"

    def test_business_required_elements_compiled(self, handler):
        assert hasattr(handler, "_compiled_business_elements")
        assert len(handler._compiled_business_elements) > 0
        for element_name, pat in handler._compiled_business_elements.items():
            if pat:
                assert isinstance(pat, re.Pattern), f"{element_name} pattern not compiled"

    def test_data_science_checks_compiled(self, handler):
        assert hasattr(handler, "_compiled_ds_checks")
        assert len(handler._compiled_ds_checks) > 0
        for check_name, pat in handler._compiled_ds_checks.items():
            if pat:
                assert isinstance(pat, re.Pattern), f"{check_name} pattern not compiled"

    def test_secret_patterns_compiled(self, handler):
        assert hasattr(handler, "_compiled_secret_patterns")
        assert len(handler._compiled_secret_patterns) >= 4
        for pat in handler._compiled_secret_patterns:
            assert isinstance(pat, re.Pattern)

    def test_adverb_pattern_compiled(self, handler):
        assert hasattr(handler, "_compiled_adverb_pattern")
        assert isinstance(handler._compiled_adverb_pattern, re.Pattern)

    def test_language_indicators_lowercased(self, handler):
        assert hasattr(handler, "_lowered_indicators")
        assert len(handler._lowered_indicators) > 0
        for lang, indicators in handler._lowered_indicators.items():
            for ind in indicators:
                assert ind == ind.lower(), f"Indicator '{ind}' for {lang} not lowercased"


class TestPrecompiledPatternsWork:
    """Verify pre-compiled patterns produce correct results."""

    def test_secret_pattern_detects_api_key(self, handler):
        text = 'api_key = "sk_test_abc123def456ghi789jkl012mno"'
        found = any(p.search(text) for p in handler._compiled_secret_patterns)
        assert found

    def test_secret_pattern_detects_github_token(self, handler):
        # Use a clearly fake token that matches the ghp_ pattern (36 alphanumeric chars)
        text = "token = ghp_" + "x" * 36  # nosec: fake test token
        found = any(p.search(text) for p in handler._compiled_secret_patterns)
        assert found

    def test_secret_pattern_ignores_clean_text(self, handler):
        text = "Please write a function that fetches user data from the API"
        found = any(p.search(text) for p in handler._compiled_secret_patterns)
        assert not found

    def test_adverb_pattern_finds_adverbs(self, handler):
        text = "quickly and carefully process the data"
        matches = handler._compiled_adverb_pattern.findall(text)
        assert len(matches) >= 2
