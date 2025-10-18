"""Statistics dashboard for PromptC usage metrics."""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

from app.history import get_history_manager
from app.favorites import get_favorites_manager
from app.templates_manager import get_templates_manager
from app.snippets import get_snippets_manager
from app.collections import get_collections_manager
from app.search_history import get_search_history_manager


class StatsCalculator:
    """Calculate various statistics about PromptC usage."""

    def __init__(self):
        """Initialize stats calculator."""
        self.history_mgr = get_history_manager()
        self.favorites_mgr = get_favorites_manager()
        self.templates_mgr = get_templates_manager()
        self.snippets_mgr = get_snippets_manager()
        self.collections_mgr = get_collections_manager()
        self.search_history_mgr = get_search_history_manager()

    def get_overall_stats(self) -> Dict[str, int]:
        """Get overall item counts.

        Returns:
            Dictionary with counts for each data type
        """
        return {
            "total_prompts": len(self.history_mgr.get_recent(limit=10000)),
            "total_favorites": len(self.favorites_mgr.get_all()),
            "total_templates": len(self.templates_mgr.list_templates()),
            "total_snippets": len(self.snippets_mgr.get_all()),
            "total_collections": len(self.collections_mgr.get_all()),
            "total_searches": len(self.search_history_mgr.get_recent(limit=100)),
        }

    def get_recent_activity(self, days: int = 7) -> Dict[str, int]:
        """Get activity counts for recent days.

        Args:
            days: Number of days to look back

        Returns:
            Dictionary with activity counts
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.isoformat()

        recent_prompts = [
            e
            for e in self.history_mgr.get_recent(limit=10000)
            if e.timestamp >= cutoff_str
        ]
        recent_favs = [
            f for f in self.favorites_mgr.get_all() if f.timestamp >= cutoff_str
        ]
        recent_searches = [
            s
            for s in self.search_history_mgr.get_recent(limit=100)
            if s.timestamp >= cutoff_str
        ]

        return {
            "prompts_created": len(recent_prompts),
            "favorites_added": len(recent_favs),
            "searches_performed": len(recent_searches),
            "days": days,
        }

    def get_top_domains(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Get most common domains.

        Args:
            limit: Maximum number of domains to return

        Returns:
            List of (domain, count) tuples sorted by count
        """
        domains = [
            e.domain for e in self.history_mgr.get_recent(limit=10000) if e.domain
        ]
        counter = Counter(domains)
        return counter.most_common(limit)

    def get_top_tags(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Get most used tags across all items.

        Args:
            limit: Maximum number of tags to return

        Returns:
            List of (tag, count) tuples sorted by count
        """
        all_tags = []

        # From favorites
        for fav in self.favorites_mgr.get_all():
            all_tags.extend(fav.tags)

        # From templates
        for template in self.templates_mgr.list_templates():
            all_tags.extend(template.tags)

        # From snippets
        for snippet in self.snippets_mgr.get_all():
            all_tags.extend(snippet.tags)

        counter = Counter(all_tags)
        return counter.most_common(limit)

    def get_top_templates(self, limit: int = 5) -> List[Dict]:
        """Get most used templates.

        Args:
            limit: Maximum number of templates to return

        Returns:
            List of template dictionaries with usage info
        """
        templates = self.templates_mgr.list_templates()
        # Templates don't have use_count tracking yet, so just return first N
        
        results = []
        for template in templates[:limit]:
            results.append(
                {
                    "name": template.name,
                    "category": template.category,
                    "use_count": 0,  # Not tracked yet
                    "tags": template.tags,
                }
            )

        return results

    def get_top_snippets(self, limit: int = 5) -> List[Dict]:
        """Get most used snippets.

        Args:
            limit: Maximum number of snippets to return

        Returns:
            List of snippet dictionaries with usage info
        """
        snippets = self.snippets_mgr.get_all()
        sorted_snippets = sorted(snippets, key=lambda s: s.use_count, reverse=True)

        results = []
        for snippet in sorted_snippets[:limit]:
            results.append(
                {
                    "title": snippet.title,
                    "category": snippet.category,
                    "use_count": snippet.use_count,
                    "tags": snippet.tags,
                }
            )

        return results

    def get_quality_metrics(self) -> Dict[str, float]:
        """Get quality metrics for prompts.

        Returns:
            Dictionary with quality statistics
        """
        prompts = self.history_mgr.get_recent(limit=10000)
        if not prompts:
            return {
                "average_score": 0.0,
                "high_quality_count": 0,
                "high_quality_percentage": 0.0,
            }

        scores = [p.score for p in prompts if p.score is not None]
        if not scores:
            return {
                "average_score": 0.0,
                "high_quality_count": 0,
                "high_quality_percentage": 0.0,
            }

        avg_score = sum(scores) / len(scores)
        high_quality = len([s for s in scores if s >= 80.0])
        high_quality_pct = (high_quality / len(scores)) * 100

        return {
            "average_score": round(avg_score, 2),
            "high_quality_count": high_quality,
            "high_quality_percentage": round(high_quality_pct, 2),
        }

    def get_daily_activity_trend(self, days: int = 30) -> List[Tuple[str, int]]:
        """Get daily activity counts for trend visualization.

        Args:
            days: Number of days to look back

        Returns:
            List of (date, count) tuples for each day
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        prompts = self.history_mgr.get_recent(limit=10000)

        # Count prompts per day
        daily_counts = defaultdict(int)
        for prompt in prompts:
            try:
                prompt_date = datetime.fromisoformat(prompt.timestamp)
                if prompt_date >= cutoff_date:
                    date_str = prompt_date.strftime("%Y-%m-%d")
                    daily_counts[date_str] += 1
            except Exception:
                continue

        # Fill in missing days with 0
        result = []
        current = cutoff_date
        for _ in range(days):
            date_str = current.strftime("%Y-%m-%d")
            result.append((date_str, daily_counts.get(date_str, 0)))
            current += timedelta(days=1)

        return result

    def get_search_stats(self) -> Dict:
        """Get search-related statistics.

        Returns:
            Dictionary with search statistics
        """
        searches = self.search_history_mgr.get_recent(limit=100)

        if not searches:
            return {
                "total_searches": 0,
                "average_results": 0.0,
                "most_common_queries": [],
            }

        total = len(searches)
        avg_results = sum(s.result_count for s in searches) / total if total > 0 else 0

        # Get most common queries
        query_counter = Counter(s.query for s in searches)
        most_common = query_counter.most_common(5)

        return {
            "total_searches": total,
            "average_results": round(avg_results, 1),
            "most_common_queries": most_common,
        }

    def get_comprehensive_stats(self) -> Dict:
        """Get all statistics in one call.

        Returns:
            Dictionary containing all available statistics
        """
        return {
            "overall": self.get_overall_stats(),
            "recent_7_days": self.get_recent_activity(7),
            "recent_30_days": self.get_recent_activity(30),
            "top_domains": self.get_top_domains(10),
            "top_tags": self.get_top_tags(10),
            "top_templates": self.get_top_templates(5),
            "top_snippets": self.get_top_snippets(5),
            "quality": self.get_quality_metrics(),
            "daily_trend": self.get_daily_activity_trend(14),
            "search": self.get_search_stats(),
        }


def generate_ascii_bar_chart(data: List[Tuple[str, int]], max_width: int = 40) -> List[str]:
    """Generate ASCII bar chart from data.

    Args:
        data: List of (label, value) tuples
        max_width: Maximum width of bars

    Returns:
        List of strings representing chart lines
    """
    if not data:
        return ["No data available"]

    max_value = max(value for _, value in data) if data else 1
    if max_value == 0:
        max_value = 1

    lines = []
    for label, value in data:
        bar_length = int((value / max_value) * max_width)
        bar = "█" * bar_length
        lines.append(f"{label:20} {bar} {value}")

    return lines


def generate_sparkline(values: List[int], width: int = 20) -> str:
    """Generate sparkline from values.

    Args:
        values: List of numeric values
        width: Width of sparkline

    Returns:
        Sparkline string
    """
    if not values or all(v == 0 for v in values):
        return "─" * width

    # Sample values to fit width
    if len(values) > width:
        step = len(values) / width
        sampled = [values[int(i * step)] for i in range(width)]
    elif len(values) < width:
        # Pad with last value if fewer values than width
        sampled = values + [values[-1]] * (width - len(values))
    else:
        sampled = values

    max_val = max(sampled) if sampled else 1
    if max_val == 0:
        max_val = 1

    # Sparkline characters
    chars = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
    result = []

    for val in sampled:
        index = int((val / max_val) * (len(chars) - 1))
        result.append(chars[index])

    return "".join(result)


# Singleton instance
_stats_calculator_instance = None


def get_stats_calculator() -> StatsCalculator:
    """Get the singleton StatsCalculator instance.

    Returns:
        StatsCalculator instance
    """
    global _stats_calculator_instance
    if _stats_calculator_instance is None:
        _stats_calculator_instance = StatsCalculator()
    return _stats_calculator_instance
