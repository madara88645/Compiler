"""Tests for stats dashboard module."""

import pytest
from datetime import datetime
from app.stats_dashboard import (
    StatsCalculator,
    get_stats_calculator,
    generate_ascii_bar_chart,
    generate_sparkline,
)


@pytest.fixture
def stats_calc():
    """Create StatsCalculator instance for testing."""
    return StatsCalculator()


def test_stats_calculator_initialization(stats_calc):
    """Test StatsCalculator initialization."""
    assert stats_calc.history_mgr is not None
    assert stats_calc.favorites_mgr is not None
    assert stats_calc.templates_mgr is not None
    assert stats_calc.snippets_mgr is not None
    assert stats_calc.collections_mgr is not None
    assert stats_calc.search_history_mgr is not None


def test_get_overall_stats(stats_calc):
    """Test getting overall statistics."""
    stats = stats_calc.get_overall_stats()

    assert isinstance(stats, dict)
    assert "total_prompts" in stats
    assert "total_favorites" in stats
    assert "total_templates" in stats
    assert "total_snippets" in stats
    assert "total_collections" in stats
    assert "total_searches" in stats

    # All should be non-negative integers
    for key, value in stats.items():
        assert isinstance(value, int)
        assert value >= 0


def test_get_recent_activity(stats_calc):
    """Test getting recent activity stats."""
    stats = stats_calc.get_recent_activity(7)

    assert isinstance(stats, dict)
    assert "prompts_created" in stats
    assert "favorites_added" in stats
    assert "searches_performed" in stats
    assert "days" in stats
    assert stats["days"] == 7

    # All counts should be non-negative
    assert stats["prompts_created"] >= 0
    assert stats["favorites_added"] >= 0
    assert stats["searches_performed"] >= 0


def test_get_recent_activity_30_days(stats_calc):
    """Test getting 30-day activity stats."""
    stats = stats_calc.get_recent_activity(30)

    assert stats["days"] == 30
    assert isinstance(stats["prompts_created"], int)


def test_get_top_domains(stats_calc):
    """Test getting top domains."""
    domains = stats_calc.get_top_domains(5)

    assert isinstance(domains, list)
    assert len(domains) <= 5

    # Each item should be (domain, count) tuple
    for domain, count in domains:
        assert isinstance(domain, str)
        assert isinstance(count, int)
        assert count > 0


def test_get_top_domains_with_limit(stats_calc):
    """Test top domains with different limits."""
    domains_3 = stats_calc.get_top_domains(3)
    domains_10 = stats_calc.get_top_domains(10)

    assert len(domains_3) <= 3
    assert len(domains_10) <= 10


def test_get_top_tags(stats_calc):
    """Test getting top tags."""
    tags = stats_calc.get_top_tags(5)

    assert isinstance(tags, list)
    assert len(tags) <= 5

    # Each item should be (tag, count) tuple
    for tag, count in tags:
        assert isinstance(tag, str)
        assert isinstance(count, int)
        assert count > 0


def test_get_top_templates(stats_calc):
    """Test getting top templates."""
    templates = stats_calc.get_top_templates(3)

    assert isinstance(templates, list)
    assert len(templates) <= 3

    for template in templates:
        assert isinstance(template, dict)
        assert "name" in template
        assert "category" in template
        assert "use_count" in template
        assert "tags" in template


def test_get_top_snippets(stats_calc):
    """Test getting top snippets."""
    snippets = stats_calc.get_top_snippets(3)

    assert isinstance(snippets, list)
    assert len(snippets) <= 3

    for snippet in snippets:
        assert isinstance(snippet, dict)
        assert "title" in snippet
        assert "category" in snippet
        assert "use_count" in snippet
        assert "tags" in snippet


def test_get_quality_metrics(stats_calc):
    """Test getting quality metrics."""
    metrics = stats_calc.get_quality_metrics()

    assert isinstance(metrics, dict)
    assert "average_score" in metrics
    assert "high_quality_count" in metrics
    assert "high_quality_percentage" in metrics

    assert isinstance(metrics["average_score"], float)
    assert isinstance(metrics["high_quality_count"], int)
    assert isinstance(metrics["high_quality_percentage"], float)

    # Percentage should be 0-100
    assert 0 <= metrics["high_quality_percentage"] <= 100


def test_get_daily_activity_trend(stats_calc):
    """Test getting daily activity trend."""
    trend = stats_calc.get_daily_activity_trend(7)

    assert isinstance(trend, list)
    assert len(trend) == 7

    # Each item should be (date, count) tuple
    for date_str, count in trend:
        assert isinstance(date_str, str)
        assert isinstance(count, int)
        assert count >= 0
        # Verify date format
        datetime.strptime(date_str, "%Y-%m-%d")


def test_get_daily_activity_trend_30_days(stats_calc):
    """Test getting 30-day activity trend."""
    trend = stats_calc.get_daily_activity_trend(30)

    assert len(trend) == 30


def test_get_search_stats(stats_calc):
    """Test getting search statistics."""
    stats = stats_calc.get_search_stats()

    assert isinstance(stats, dict)
    assert "total_searches" in stats
    assert "average_results" in stats
    assert "most_common_queries" in stats

    assert isinstance(stats["total_searches"], int)
    assert isinstance(stats["average_results"], float)
    assert isinstance(stats["most_common_queries"], list)


def test_get_comprehensive_stats(stats_calc):
    """Test getting all stats at once."""
    stats = stats_calc.get_comprehensive_stats()

    assert isinstance(stats, dict)
    assert "overall" in stats
    assert "recent_7_days" in stats
    assert "recent_30_days" in stats
    assert "top_domains" in stats
    assert "top_tags" in stats
    assert "top_templates" in stats
    assert "top_snippets" in stats
    assert "quality" in stats
    assert "daily_trend" in stats
    assert "search" in stats


def test_generate_ascii_bar_chart_empty():
    """Test ASCII bar chart with empty data."""
    chart = generate_ascii_bar_chart([])

    assert isinstance(chart, list)
    assert len(chart) == 1
    assert "No data" in chart[0]


def test_generate_ascii_bar_chart_with_data():
    """Test ASCII bar chart with data."""
    data = [("Item A", 10), ("Item B", 5), ("Item C", 15)]
    chart = generate_ascii_bar_chart(data, max_width=20)

    assert isinstance(chart, list)
    assert len(chart) == 3

    # Each line should contain label and value
    for line in chart:
        assert isinstance(line, str)
        assert len(line) > 0


def test_generate_ascii_bar_chart_zero_values():
    """Test bar chart with zero values."""
    data = [("Item A", 0), ("Item B", 0)]
    chart = generate_ascii_bar_chart(data, max_width=20)

    assert isinstance(chart, list)
    assert len(chart) == 2


def test_generate_sparkline_empty():
    """Test sparkline with empty data."""
    sparkline = generate_sparkline([])

    assert isinstance(sparkline, str)
    assert len(sparkline) > 0


def test_generate_sparkline_all_zeros():
    """Test sparkline with all zero values."""
    sparkline = generate_sparkline([0, 0, 0, 0, 0])

    assert isinstance(sparkline, str)
    assert len(sparkline) > 0


def test_generate_sparkline_with_data():
    """Test sparkline with actual data."""
    data = [1, 3, 2, 5, 4, 6, 3, 2, 4, 5]
    sparkline = generate_sparkline(data, width=20)

    assert isinstance(sparkline, str)
    assert len(sparkline) == 20
    # Should contain sparkline characters
    assert any(c in sparkline for c in ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"])


def test_generate_sparkline_scaling():
    """Test sparkline handles scaling correctly."""
    # Test with values that need sampling
    data = list(range(100))
    sparkline = generate_sparkline(data, width=20)

    assert len(sparkline) == 20


def test_singleton_pattern():
    """Test that get_stats_calculator returns singleton."""
    calc1 = get_stats_calculator()
    calc2 = get_stats_calculator()

    assert calc1 is calc2


def test_get_top_domains_sorted_order(stats_calc):
    """Test that domains are sorted by count."""
    domains = stats_calc.get_top_domains(10)

    if len(domains) > 1:
        # Check that counts are in descending order
        for i in range(len(domains) - 1):
            assert domains[i][1] >= domains[i + 1][1]


def test_get_top_tags_sorted_order(stats_calc):
    """Test that tags are sorted by count."""
    tags = stats_calc.get_top_tags(10)

    if len(tags) > 1:
        # Check that counts are in descending order
        for i in range(len(tags) - 1):
            assert tags[i][1] >= tags[i + 1][1]


def test_quality_metrics_with_no_prompts():
    """Test quality metrics when no prompts exist."""
    # This will depend on actual data, but should not crash
    calc = StatsCalculator()
    metrics = calc.get_quality_metrics()

    assert isinstance(metrics, dict)
    assert "average_score" in metrics


def test_daily_trend_date_format(stats_calc):
    """Test that daily trend has correct date format."""
    trend = stats_calc.get_daily_activity_trend(7)

    for date_str, _ in trend:
        # Should be able to parse as ISO date
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
        assert isinstance(parsed, datetime)


def test_generate_sparkline_width():
    """Test sparkline respects width parameter."""
    data = [1, 2, 3, 4, 5]

    sparkline_10 = generate_sparkline(data, width=10)
    sparkline_30 = generate_sparkline(data, width=30)

    assert len(sparkline_10) == 10
    assert len(sparkline_30) == 30


def test_get_recent_activity_edge_cases(stats_calc):
    """Test recent activity with edge case inputs."""
    # Test with 1 day
    stats_1 = stats_calc.get_recent_activity(1)
    assert stats_1["days"] == 1

    # Test with large number
    stats_365 = stats_calc.get_recent_activity(365)
    assert stats_365["days"] == 365
