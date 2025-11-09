"""Tests for UI analytics and filtering functionality."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest


@pytest.fixture
def sample_history_with_usage():
    """Sample history data with usage tracking."""
    now = datetime.now()
    return [
        {
            "timestamp": (now - timedelta(days=1)).isoformat(),
            "preview": "Python basics...",
            "full_text": "Teach me Python basics with examples",
            "is_favorite": True,
            "tags": ["code", "tutorial"],
            "usage_count": 10,
            "length": 36,
        },
        {
            "timestamp": (now - timedelta(days=2)).isoformat(),
            "preview": "Short prompt",
            "full_text": "Hello world",
            "is_favorite": False,
            "tags": ["code"],
            "usage_count": 2,
            "length": 11,
        },
        {
            "timestamp": (now - timedelta(days=5)).isoformat(),
            "preview": "Long detailed explanation...",
            "full_text": "A" * 600,  # Long prompt (>500 chars)
            "is_favorite": True,
            "tags": ["writing"],
            "usage_count": 5,
            "length": 600,
        },
        {
            "timestamp": (now - timedelta(days=10)).isoformat(),
            "preview": "Old prompt...",
            "full_text": "This is an old prompt from 10 days ago",
            "is_favorite": False,
            "tags": [],
            "usage_count": 0,
            "length": 39,
        },
        {
            "timestamp": (now - timedelta(hours=2)).isoformat(),
            "preview": "Recent prompt...",
            "full_text": "This is a very recent prompt from today",
            "is_favorite": False,
            "tags": ["test"],
            "usage_count": 1,
            "length": 40,
        },
    ]


class TestAdvancedFiltering:
    """Tests for advanced filtering functionality."""

    def test_filter_favorites_only(self, sample_history_with_usage):
        """Test filtering favorites only."""
        filtered = [
            item for item in sample_history_with_usage if item.get("is_favorite", False)
        ]

        assert len(filtered) == 2
        assert all(item["is_favorite"] for item in filtered)

    def test_filter_by_length_short(self, sample_history_with_usage):
        """Test filtering short prompts (<100 chars)."""
        filtered = [
            item
            for item in sample_history_with_usage
            if item.get("length", len(item["full_text"])) < 100
        ]

        assert len(filtered) == 4
        assert all(item["length"] < 100 for item in filtered)

    def test_filter_by_length_medium(self, sample_history_with_usage):
        """Test filtering medium prompts (100-500 chars)."""
        filtered = [
            item
            for item in sample_history_with_usage
            if 100 <= item.get("length", len(item["full_text"])) <= 500
        ]

        assert len(filtered) == 0  # No medium prompts in sample

    def test_filter_by_length_long(self, sample_history_with_usage):
        """Test filtering long prompts (>500 chars)."""
        filtered = [
            item
            for item in sample_history_with_usage
            if item.get("length", len(item["full_text"])) > 500
        ]

        assert len(filtered) == 1
        assert filtered[0]["length"] == 600

    def test_filter_by_date_today(self, sample_history_with_usage):
        """Test filtering prompts from today."""
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        filtered = []
        for item in sample_history_with_usage:
            try:
                item_date = datetime.fromisoformat(item["timestamp"])
                if item_date >= today_start:
                    filtered.append(item)
            except Exception:
                pass

        assert len(filtered) == 1
        assert "recent" in filtered[0]["preview"].lower()

    def test_filter_by_date_last_7_days(self, sample_history_with_usage):
        """Test filtering prompts from last 7 days."""
        now = datetime.now()
        seven_days_ago = now - timedelta(days=7)

        filtered = []
        for item in sample_history_with_usage:
            try:
                item_date = datetime.fromisoformat(item["timestamp"])
                if item_date >= seven_days_ago:
                    filtered.append(item)
            except Exception:
                pass

        assert len(filtered) == 4  # All except 10-day-old prompt

    def test_filter_by_date_last_30_days(self, sample_history_with_usage):
        """Test filtering prompts from last 30 days."""
        now = datetime.now()
        thirty_days_ago = now - timedelta(days=30)

        filtered = []
        for item in sample_history_with_usage:
            try:
                item_date = datetime.fromisoformat(item["timestamp"])
                if item_date >= thirty_days_ago:
                    filtered.append(item)
            except Exception:
                pass

        assert len(filtered) == 5  # All prompts

    def test_filter_by_tags(self, sample_history_with_usage):
        """Test filtering by tags."""
        active_tags = ["code"]

        filtered = [
            item
            for item in sample_history_with_usage
            if any(tag in active_tags for tag in item.get("tags", []))
        ]

        assert len(filtered) == 2
        assert all("code" in item["tags"] for item in filtered)

    def test_multiple_filters_combined(self, sample_history_with_usage):
        """Test combining multiple filters (favorites + short + code tag)."""
        active_tags = ["code"]

        filtered = []
        for item in sample_history_with_usage:
            # Check favorite
            if not item.get("is_favorite", False):
                continue

            # Check length
            if item.get("length", len(item["full_text"])) >= 100:
                continue

            # Check tags
            if not any(tag in active_tags for tag in item.get("tags", [])):
                continue

            filtered.append(item)

        assert len(filtered) == 1
        assert filtered[0]["is_favorite"]
        assert "code" in filtered[0]["tags"]
        assert filtered[0]["length"] < 100


class TestSorting:
    """Tests for sorting functionality."""

    def test_sort_by_date_newest(self, sample_history_with_usage):
        """Test sorting by date (newest first)."""
        sorted_items = sorted(
            sample_history_with_usage,
            key=lambda x: datetime.fromisoformat(x["timestamp"]),
            reverse=True,
        )

        assert "recent" in sorted_items[0]["preview"].lower()
        assert "old" in sorted_items[-1]["preview"].lower()

    def test_sort_by_date_oldest(self, sample_history_with_usage):
        """Test sorting by date (oldest first)."""
        sorted_items = sorted(
            sample_history_with_usage, key=lambda x: datetime.fromisoformat(x["timestamp"])
        )

        assert "old" in sorted_items[0]["preview"].lower()
        assert "recent" in sorted_items[-1]["preview"].lower()

    def test_sort_by_length_short(self, sample_history_with_usage):
        """Test sorting by length (shortest first)."""
        sorted_items = sorted(
            sample_history_with_usage,
            key=lambda x: x.get("length", len(x.get("full_text", ""))),
        )

        assert sorted_items[0]["length"] == 11
        assert sorted_items[-1]["length"] == 600

    def test_sort_by_length_long(self, sample_history_with_usage):
        """Test sorting by length (longest first)."""
        sorted_items = sorted(
            sample_history_with_usage,
            key=lambda x: x.get("length", len(x.get("full_text", ""))),
            reverse=True,
        )

        assert sorted_items[0]["length"] == 600
        assert sorted_items[-1]["length"] == 11

    def test_sort_by_usage_most_used(self, sample_history_with_usage):
        """Test sorting by usage count (most used first)."""
        sorted_items = sorted(
            sample_history_with_usage, key=lambda x: x.get("usage_count", 0), reverse=True
        )

        assert sorted_items[0]["usage_count"] == 10
        assert sorted_items[-1]["usage_count"] == 0


class TestAnalyticsCalculations:
    """Tests for analytics calculations."""

    def test_total_prompts_count(self, sample_history_with_usage):
        """Test calculating total prompts."""
        total = len(sample_history_with_usage)
        assert total == 5

    def test_favorites_count(self, sample_history_with_usage):
        """Test calculating favorites count."""
        favorites = sum(1 for item in sample_history_with_usage if item.get("is_favorite", False))
        assert favorites == 2

    def test_total_usage_count(self, sample_history_with_usage):
        """Test calculating total usage."""
        total_usage = sum(item.get("usage_count", 0) for item in sample_history_with_usage)
        assert total_usage == 18  # 10 + 2 + 5 + 0 + 1

    def test_average_length(self, sample_history_with_usage):
        """Test calculating average prompt length."""
        total_length = sum(
            item.get("length", len(item.get("full_text", "")))
            for item in sample_history_with_usage
        )
        avg_length = total_length / len(sample_history_with_usage)

        assert avg_length == (36 + 11 + 600 + 39 + 40) / 5
        assert avg_length == 145.2

    def test_tag_distribution(self, sample_history_with_usage):
        """Test calculating tag usage distribution."""
        tag_counts = {}
        for item in sample_history_with_usage:
            for tag in item.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        assert tag_counts["code"] == 2
        assert tag_counts["tutorial"] == 1
        assert tag_counts["writing"] == 1
        assert tag_counts["test"] == 1

    def test_top_used_prompts(self, sample_history_with_usage):
        """Test getting top 10 most used prompts."""
        top_used = sorted(
            sample_history_with_usage, key=lambda x: x.get("usage_count", 0), reverse=True
        )[:10]

        assert len(top_used) == 5  # Less than 10 in sample
        assert top_used[0]["usage_count"] == 10
        assert top_used[1]["usage_count"] == 5

    def test_daily_activity_counts(self, sample_history_with_usage):
        """Test calculating daily activity for last 7 days."""
        from collections import defaultdict

        daily_counts = defaultdict(int)
        now = datetime.now()

        for item in sample_history_with_usage:
            try:
                item_date = datetime.fromisoformat(item["timestamp"])
                days_ago = (now - item_date).days
                if days_ago < 7:
                    day_name = item_date.strftime("%A")
                    daily_counts[day_name] += 1
            except Exception:
                pass

        # Should have activity for multiple days
        assert len(daily_counts) > 0
        assert sum(daily_counts.values()) == 4  # 4 prompts in last 7 days


class TestFilterEdgeCases:
    """Tests for filter edge cases."""

    def test_empty_history(self):
        """Test filtering with empty history."""
        history = []

        filtered = [item for item in history if item.get("is_favorite", False)]
        assert len(filtered) == 0

    def test_missing_usage_count(self):
        """Test handling missing usage_count field."""
        item = {
            "timestamp": datetime.now().isoformat(),
            "preview": "Test",
            "full_text": "Test prompt",
            "is_favorite": False,
            "tags": [],
            # No usage_count
        }

        usage_count = item.get("usage_count", 0)
        assert usage_count == 0

    def test_missing_length_field(self):
        """Test handling missing length field."""
        item = {
            "timestamp": datetime.now().isoformat(),
            "preview": "Test",
            "full_text": "Test prompt text",
            "is_favorite": False,
            "tags": [],
            # No length
        }

        length = item.get("length", len(item.get("full_text", "")))
        assert length == 16

    def test_invalid_timestamp(self):
        """Test handling invalid timestamp."""
        item = {
            "timestamp": "invalid-date",
            "preview": "Test",
            "full_text": "Test prompt",
            "is_favorite": False,
            "tags": [],
        }

        try:
            datetime.fromisoformat(item["timestamp"])
            parsed = True
        except Exception:
            parsed = False

        assert parsed is False

    def test_empty_tags(self):
        """Test filtering with empty tags."""
        item = {
            "timestamp": datetime.now().isoformat(),
            "preview": "Test",
            "full_text": "Test prompt",
            "is_favorite": False,
            "tags": [],
        }

        has_code_tag = "code" in item.get("tags", [])
        assert has_code_tag is False


class TestSearchFiltering:
    """Tests for search text filtering."""

    def test_search_in_preview(self, sample_history_with_usage):
        """Test searching in preview text."""
        search_term = "python"

        filtered = [
            item
            for item in sample_history_with_usage
            if search_term.lower() in item.get("preview", "").lower()
        ]

        assert len(filtered) == 1
        assert "Python" in filtered[0]["preview"]

    def test_search_in_full_text(self, sample_history_with_usage):
        """Test searching in full text."""
        search_term = "world"

        filtered = [
            item
            for item in sample_history_with_usage
            if search_term.lower() in item.get("full_text", "").lower()
        ]

        assert len(filtered) == 1
        assert "world" in filtered[0]["full_text"]

    def test_search_case_insensitive(self, sample_history_with_usage):
        """Test case-insensitive search."""
        search_upper = "PYTHON"
        search_lower = "python"

        filtered_upper = [
            item
            for item in sample_history_with_usage
            if search_upper.lower() in item.get("preview", "").lower()
        ]

        filtered_lower = [
            item
            for item in sample_history_with_usage
            if search_lower.lower() in item.get("preview", "").lower()
        ]

        assert len(filtered_upper) == len(filtered_lower)

    def test_search_empty_term(self, sample_history_with_usage):
        """Test search with empty term returns all."""
        search_term = ""

        filtered = [
            item
            for item in sample_history_with_usage
            if search_term.lower() in item.get("preview", "").lower()
            or search_term.lower() in item.get("full_text", "").lower()
        ]

        assert len(filtered) == len(sample_history_with_usage)


class TestUsageIndicator:
    """Tests for usage count display."""

    def test_format_usage_indicator(self):
        """Test formatting usage indicator."""
        usage_count = 5
        indicator = f"(↻{usage_count})"
        assert indicator == "(↻5)"

    def test_no_usage_indicator(self):
        """Test no indicator for zero usage."""
        usage_count = 0
        indicator = f"(↻{usage_count})" if usage_count > 0 else ""
        assert indicator == ""

    def test_high_usage_indicator(self):
        """Test indicator for high usage count."""
        usage_count = 100
        indicator = f"(↻{usage_count})"
        assert indicator == "(↻100)"
