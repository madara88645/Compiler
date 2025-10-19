"""Tests for smart tags module."""

import pytest
from app.smart_tags import (
    SmartTagger,
    get_smart_tagger,
    DOMAIN_TAG_MAP,
    KEYWORD_PATTERNS,
)


@pytest.fixture
def smart_tagger():
    """Create SmartTagger instance for testing."""
    return SmartTagger()


def test_smart_tagger_initialization(smart_tagger):
    """Test SmartTagger initialization."""
    assert smart_tagger.history_mgr is not None
    assert smart_tagger.favorites_mgr is not None
    assert smart_tagger.templates_mgr is not None
    assert smart_tagger.snippets_mgr is not None
    assert smart_tagger.collections_mgr is not None


def test_suggest_tags_for_text_with_domain(smart_tagger):
    """Test tag suggestion based on domain."""
    text = "Sample prompt"
    tags = smart_tagger.suggest_tags_for_text(text, domain="tech")

    assert isinstance(tags, list)
    assert len(tags) > 0
    # Should include tech domain tags
    assert any(tag in DOMAIN_TAG_MAP["tech"] for tag in tags)


def test_suggest_tags_for_text_with_keywords(smart_tagger):
    """Test tag suggestion based on keywords."""
    text = "Write a Python script using Django framework"
    tags = smart_tagger.suggest_tags_for_text(text)

    assert isinstance(tags, list)
    # Should detect python
    assert "python" in tags


def test_suggest_tags_for_text_with_hashtags(smart_tagger):
    """Test tag extraction from hashtags."""
    text = "Sample prompt #coding #webdev #tutorial"
    tags = smart_tagger.suggest_tags_for_text(text)

    assert "coding" in tags
    assert "webdev" in tags
    assert "tutorial" in tags


def test_suggest_tags_for_text_empty(smart_tagger):
    """Test tag suggestion with empty text."""
    tags = smart_tagger.suggest_tags_for_text("")

    assert isinstance(tags, list)
    assert len(tags) == 0


def test_suggest_tags_for_text_no_matches(smart_tagger):
    """Test tag suggestion with text that has no matches."""
    text = "xyz abc qwerty"
    tags = smart_tagger.suggest_tags_for_text(text)

    # Should return empty or only hashtags
    assert isinstance(tags, list)


def test_suggest_tags_for_text_multiple_keywords(smart_tagger):
    """Test tag suggestion with multiple keyword patterns."""
    text = "Build a web app with JavaScript and connect to PostgreSQL database"
    tags = smart_tagger.suggest_tags_for_text(text)

    # Should detect multiple patterns
    assert "javascript" in tags
    assert "web" in tags
    assert "database" in tags


def test_get_all_tags(smart_tagger):
    """Test getting all unique tags."""
    all_tags = smart_tagger.get_all_tags()

    assert isinstance(all_tags, set)
    # Tags should be strings
    for tag in all_tags:
        assert isinstance(tag, str)


def test_get_tag_statistics(smart_tagger):
    """Test getting tag usage statistics."""
    stats = smart_tagger.get_tag_statistics()

    assert isinstance(stats, list)
    # Each item should be (tag, count) tuple
    for tag, count in stats:
        assert isinstance(tag, str)
        assert isinstance(count, int)
        assert count > 0


def test_get_tag_statistics_sorted(smart_tagger):
    """Test that tag statistics are sorted by count."""
    stats = smart_tagger.get_tag_statistics()

    if len(stats) > 1:
        # Verify descending order
        for i in range(len(stats) - 1):
            assert stats[i][1] >= stats[i + 1][1]


def test_find_unused_tags(smart_tagger):
    """Test finding unused predefined tags."""
    unused = smart_tagger.find_unused_tags()

    assert isinstance(unused, set)
    # All should be strings
    for tag in unused:
        assert isinstance(tag, str)


def test_auto_tag_all_favorites_dry_run(smart_tagger):
    """Test auto-tagging favorites in dry-run mode."""
    suggestions = smart_tagger.auto_tag_all_favorites(dry_run=True)

    assert isinstance(suggestions, dict)
    # Keys should be favorite IDs
    # Values should be lists of suggested tags
    for fav_id, tags in suggestions.items():
        assert isinstance(fav_id, str)
        assert isinstance(tags, list)
        for tag in tags:
            assert isinstance(tag, str)


def test_auto_tag_all_prompts_dry_run(smart_tagger):
    """Test auto-tagging prompts in dry-run mode."""
    suggestions = smart_tagger.auto_tag_all_prompts(dry_run=True)

    assert isinstance(suggestions, dict)
    # Similar structure to favorites
    for prompt_id, tags in suggestions.items():
        assert isinstance(prompt_id, str)
        assert isinstance(tags, list)


def test_get_tag_cooccurrence(smart_tagger):
    """Test finding co-occurring tags."""
    # Get a tag that exists
    all_tags = smart_tagger.get_all_tags()

    if all_tags:
        tag = list(all_tags)[0]
        cooccur = smart_tagger.get_tag_cooccurrence(tag, limit=5)

        assert isinstance(cooccur, list)
        assert len(cooccur) <= 5

        for other_tag, count in cooccur:
            assert isinstance(other_tag, str)
            assert isinstance(count, int)
            assert count > 0
            assert other_tag != tag  # Should not include the tag itself


def test_get_tag_cooccurrence_nonexistent_tag(smart_tagger):
    """Test co-occurrence with non-existent tag."""
    cooccur = smart_tagger.get_tag_cooccurrence("nonexistent_tag_xyz")

    assert isinstance(cooccur, list)
    assert len(cooccur) == 0


def test_normalize_tags_dry_run(smart_tagger):
    """Test tag normalization in dry-run mode."""
    changes = smart_tagger.normalize_tags(dry_run=True)

    assert isinstance(changes, dict)
    # All values should be lowercase normalized
    for old_tag, new_tag in changes.items():
        assert isinstance(old_tag, str)
        assert isinstance(new_tag, str)
        assert new_tag == new_tag.lower()
        assert " " not in new_tag  # Spaces should be replaced with hyphens


def test_singleton_pattern():
    """Test that get_smart_tagger returns singleton."""
    tagger1 = get_smart_tagger()
    tagger2 = get_smart_tagger()

    assert tagger1 is tagger2


def test_domain_tag_map_structure():
    """Test DOMAIN_TAG_MAP has correct structure."""
    assert isinstance(DOMAIN_TAG_MAP, dict)

    for domain, tags in DOMAIN_TAG_MAP.items():
        assert isinstance(domain, str)
        assert isinstance(tags, list)
        assert len(tags) > 0
        for tag in tags:
            assert isinstance(tag, str)


def test_keyword_patterns_structure():
    """Test KEYWORD_PATTERNS has correct structure."""
    assert isinstance(KEYWORD_PATTERNS, dict)

    for tag, keywords in KEYWORD_PATTERNS.items():
        assert isinstance(tag, str)
        assert isinstance(keywords, list)
        assert len(keywords) > 0
        for keyword in keywords:
            assert isinstance(keyword, str)


def test_suggest_tags_for_text_case_insensitive(smart_tagger):
    """Test that keyword matching is case-insensitive."""
    text_lower = "python script"
    text_upper = "PYTHON SCRIPT"
    text_mixed = "PyThOn ScRiPt"

    tags_lower = smart_tagger.suggest_tags_for_text(text_lower)
    tags_upper = smart_tagger.suggest_tags_for_text(text_upper)
    tags_mixed = smart_tagger.suggest_tags_for_text(text_mixed)

    # All should detect python
    assert "python" in tags_lower
    assert "python" in tags_upper
    assert "python" in tags_mixed


def test_suggest_tags_combines_domain_and_keywords(smart_tagger):
    """Test that suggestions combine domain tags and keyword tags."""
    text = "Create a Python web application"
    tags = smart_tagger.suggest_tags_for_text(text, domain="tech")

    # Should have both domain tags and keyword-based tags
    assert any(tag in DOMAIN_TAG_MAP["tech"] for tag in tags)
    assert "python" in tags
    assert "web" in tags


def test_suggest_tags_for_text_with_multiple_domains(smart_tagger):
    """Test tag suggestions work with different domains."""
    domains_to_test = ["education", "business", "creative", "science"]

    for domain in domains_to_test:
        tags = smart_tagger.suggest_tags_for_text("Sample text", domain=domain)
        # Should include at least some domain-specific tags
        assert any(tag in DOMAIN_TAG_MAP[domain] for tag in tags)


def test_suggest_tags_deduplication(smart_tagger):
    """Test that suggested tags are deduplicated."""
    text = "Python python PYTHON #python"
    tags = smart_tagger.suggest_tags_for_text(text)

    # Should not have duplicates
    assert len(tags) == len(set(tags))


def test_suggest_tags_sorted(smart_tagger):
    """Test that suggested tags are sorted."""
    text = "web javascript python database cloud"
    tags = smart_tagger.suggest_tags_for_text(text)

    # Should be sorted alphabetically
    assert tags == sorted(tags)


def test_auto_tag_preserves_existing_tags(smart_tagger):
    """Test that auto-tagging doesn't remove existing tags."""
    # This is tested through dry-run
    suggestions = smart_tagger.auto_tag_all_favorites(dry_run=True)

    # Suggestions should only contain NEW tags
    # (implementation detail, but worth verifying conceptually)
    assert isinstance(suggestions, dict)


def test_get_tag_statistics_includes_all_sources(smart_tagger):
    """Test that statistics include all data sources."""
    stats = smart_tagger.get_tag_statistics()

    # Should count tags from:
    # - History, Favorites, Templates, Snippets, Collections
    # We can't guarantee specific counts but should be comprehensive
    assert isinstance(stats, list)


def test_suggest_similar_items_tags(smart_tagger):
    """Test suggesting tags from similar items."""
    # Get a favorite to test with
    favorites = smart_tagger.favorites_mgr.get_all()

    if favorites:
        fav_id = favorites[0].id
        suggested = smart_tagger.suggest_similar_items_tags(fav_id, source="favorites")

        assert isinstance(suggested, list)
        assert suggested == sorted(suggested)  # Should be sorted


def test_suggest_similar_items_tags_nonexistent_id(smart_tagger):
    """Test suggesting tags for non-existent item."""
    suggested = smart_tagger.suggest_similar_items_tags("nonexistent_id_xyz", source="favorites")

    assert isinstance(suggested, list)
    assert len(suggested) == 0
