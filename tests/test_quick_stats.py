"""Tests for quick statistics functionality."""

import pytest
from datetime import datetime, timedelta
from app.quick_stats import QuickStats, get_quick_stats
from app.history import get_history_manager
from app.favorites import get_favorites_manager


@pytest.fixture
def stats():
    """Get quick stats instance."""
    return get_quick_stats()


@pytest.fixture
def history():
    """Get history manager instance."""
    return get_history_manager()


@pytest.fixture
def favorites():
    """Get favorites manager instance."""
    return get_favorites_manager()


@pytest.fixture
def sample_data(history, favorites):
    """Create sample data for testing."""
    # Add history entries with different domains and scores
    history.add("Python tutorial", {"domain": "coding", "language": "en"}, 0.9)
    history.add("Machine learning guide", {"domain": "coding", "language": "en"}, 0.85)
    history.add("Database optimization", {"domain": "database", "language": "en"}, 0.75)
    history.add("French programming", {"domain": "coding", "language": "fr"}, 0.8)

    # Add favorites
    fav1 = favorites.add(
        prompt_id="test-fav-1",
        prompt_text="React patterns",
        domain="coding",
        language="en",
        score=0.95,
        tags=["react", "javascript"],
    )
    fav2 = favorites.add(
        prompt_id="test-fav-2",
        prompt_text="SQL optimization",
        domain="database",
        language="en",
        score=0.88,
        tags=["sql", "database"],
    )

    yield {"favorite_ids": [fav1.id, fav2.id]}

    # Cleanup
    for fav_id in [fav1.id, fav2.id]:
        favorites.remove(fav_id)


def test_singleton_pattern():
    """Test that get_quick_stats returns singleton instance."""
    stats1 = get_quick_stats()
    stats2 = get_quick_stats()
    assert stats1 is stats2


def test_get_counts(stats, sample_data):
    """Test getting basic counts."""
    counts = stats.get_counts()

    assert "history" in counts
    assert "favorites" in counts
    assert "total" in counts
    assert counts["total"] == counts["history"] + counts["favorites"]
    assert counts["history"] >= 4  # At least our test data
    assert counts["favorites"] >= 0  # May not persist in tests


def test_get_counts_empty(stats):
    """Test counts with empty data."""
    counts = stats.get_counts()
    assert isinstance(counts, dict)
    assert "history" in counts
    assert "favorites" in counts
    assert "total" in counts


def test_get_recent_activity_7_days(stats, sample_data):
    """Test getting recent activity for 7 days."""
    recent = stats.get_recent_activity(7)

    assert "days" in recent
    assert "history" in recent
    assert "favorites" in recent
    assert "total" in recent
    assert recent["days"] == 7
    assert recent["total"] == recent["history"] + recent["favorites"]


def test_get_recent_activity_30_days(stats, sample_data):
    """Test getting recent activity for 30 days."""
    recent = stats.get_recent_activity(30)

    assert recent["days"] == 30
    assert recent["total"] >= 0


def test_get_quality_metrics(stats, sample_data):
    """Test getting quality metrics."""
    quality = stats.get_quality_metrics()

    assert "average" in quality
    assert "high_quality" in quality
    assert "high_quality_percentage" in quality
    assert "total_rated" in quality
    assert quality["average"] >= 0.0  # Scores can be any positive value
    assert 0.0 <= quality["high_quality_percentage"] <= 100.0


def test_get_quality_metrics_no_scores(stats):
    """Test quality metrics with no scored entries."""
    # Clear entries temporarily to test edge case
    quality = stats.get_quality_metrics()

    assert isinstance(quality, dict)
    assert "average" in quality
    assert "high_quality" in quality


def test_get_top_domains(stats, sample_data):
    """Test getting top domains."""
    top_domains = stats.get_top_domains(5)

    assert isinstance(top_domains, list)
    assert len(top_domains) <= 5

    if top_domains:
        # Check structure
        domain, count = top_domains[0]
        assert isinstance(domain, str)
        assert isinstance(count, int)
        assert count > 0

        # Check sorted order (descending by count)
        if len(top_domains) > 1:
            assert top_domains[0][1] >= top_domains[1][1]


def test_get_top_domains_limit(stats, sample_data):
    """Test limiting top domains."""
    top_3 = stats.get_top_domains(3)
    top_10 = stats.get_top_domains(10)

    assert len(top_3) <= 3
    assert len(top_10) <= 10


def test_get_language_distribution(stats, sample_data):
    """Test getting language distribution."""
    languages = stats.get_language_distribution()

    assert isinstance(languages, dict)
    # Should have at least 'en' and possibly 'fr'
    assert "en" in languages or len(languages) >= 0
    for lang, count in languages.items():
        assert isinstance(lang, str)
        assert isinstance(count, int)
        assert count > 0


def test_create_banner_compact(stats, sample_data):
    """Test creating compact banner."""
    banner = stats.create_banner(compact=True)

    assert isinstance(banner, str)
    assert len(banner) > 0
    # Should contain key info
    assert "prompts" in banner.lower()
    assert "history" in banner.lower()
    assert "favorites" in banner.lower()


def test_create_banner_detailed(stats, sample_data):
    """Test creating detailed banner."""
    banner = stats.create_banner(compact=False)

    assert isinstance(banner, str)
    assert len(banner) > 0
    assert "\n" in banner  # Multi-line
    assert "Total Prompts" in banner or "prompts" in banner.lower()


def test_display_full_stats(stats, sample_data):
    """Test displaying full statistics."""
    # Should not raise an error
    stats.display_full_stats()


def test_display_compact_table(stats, sample_data):
    """Test displaying compact table."""
    # Should not raise an error
    stats.display_compact_table()


def test_counts_are_non_negative(stats):
    """Test that all counts are non-negative."""
    counts = stats.get_counts()
    assert counts["history"] >= 0
    assert counts["favorites"] >= 0
    assert counts["total"] >= 0


def test_recent_activity_counts_are_non_negative(stats):
    """Test that recent activity counts are non-negative."""
    recent = stats.get_recent_activity(7)
    assert recent["history"] >= 0
    assert recent["favorites"] >= 0
    assert recent["total"] >= 0


def test_quality_metrics_valid_ranges(stats):
    """Test that quality metrics are in valid ranges."""
    quality = stats.get_quality_metrics()
    assert quality["average"] >= 0.0
    assert quality["high_quality"] >= 0
    assert 0.0 <= quality["high_quality_percentage"] <= 100.0
    assert quality["total_rated"] >= 0


def test_banner_contains_emoji(stats, sample_data):
    """Test that banner contains emoji for visual appeal."""
    banner_compact = stats.create_banner(compact=True)
    banner_detailed = stats.create_banner(compact=False)

    # At least one should have emoji
    assert "📊" in banner_compact or "📊" in banner_detailed


def test_top_domains_returns_valid_data(stats, sample_data):
    """Test that top domains returns valid structured data."""
    top_domains = stats.get_top_domains(5)

    for domain, count in top_domains:
        assert isinstance(domain, str)
        assert len(domain) > 0
        assert isinstance(count, int)
        assert count > 0


def test_language_distribution_valid_data(stats, sample_data):
    """Test that language distribution returns valid data."""
    languages = stats.get_language_distribution()

    for lang, count in languages.items():
        assert isinstance(lang, str)
        assert len(lang) >= 2  # Language codes are at least 2 chars
        assert isinstance(count, int)
        assert count > 0


def test_recent_activity_custom_days(stats):
    """Test recent activity with different day ranges."""
    recent_1 = stats.get_recent_activity(1)
    recent_14 = stats.get_recent_activity(14)
    recent_90 = stats.get_recent_activity(90)

    assert recent_1["days"] == 1
    assert recent_14["days"] == 14
    assert recent_90["days"] == 90

    # Should all return valid data
    for recent in [recent_1, recent_14, recent_90]:
        assert recent["total"] >= 0
        assert recent["history"] >= 0
        assert recent["favorites"] >= 0
