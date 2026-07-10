"""Direct unit coverage for heuristics text-parsing helpers that previously
had no dedicated tests: extract_variant_count, detect_summary,
extract_comparison_items (additional cases beyond the existing Turkish-form
regression test), and detect_frontend_download_feature.

These are pure, deterministic string/regex functions that feed directly into
compiled-output heuristics (variant count, summary bullet count, comparison
item extraction, frontend feature detection) — a bug here silently changes
what gets compiled for the end user.
"""

from app.heuristics import (
    detect_frontend_download_feature,
    detect_summary,
    extract_comparison_items,
    extract_variant_count,
)


class TestExtractVariantCount:
    def test_no_keyword_defaults_to_one(self) -> None:
        assert extract_variant_count("Write a poem about the ocean") == 1

    def test_keyword_without_number_defaults_to_three(self) -> None:
        assert extract_variant_count("Give me some variants of this logo") == 3

    def test_keyword_with_number_in_range(self) -> None:
        assert extract_variant_count("Give me 5 options for the headline") == 5

    def test_number_below_two_clamps_to_two(self) -> None:
        assert extract_variant_count("1 alternatif ver") == 2

    def test_number_above_ten_clamps_to_ten(self) -> None:
        assert extract_variant_count("15 variants please") == 10

    def test_case_insensitive_keyword_and_number(self) -> None:
        assert extract_variant_count("SEÇENEK: 4 seçenek istiyorum") == 4


class TestDetectSummary:
    def test_no_keyword(self) -> None:
        assert detect_summary("Explain how quantum computing works") == (False, None)

    def test_keyword_without_bullet_count(self) -> None:
        assert detect_summary("Please summarize this article") == (True, None)

    def test_keyword_with_bullet_count(self) -> None:
        assert detect_summary("Give me a 5 bullet summary") == (True, 5)

    def test_keyword_with_points_count_case_insensitive(self) -> None:
        assert detect_summary("SUMMARIZE this in 10 points") == (True, 10)

    def test_turkish_keyword_with_madde_count(self) -> None:
        assert detect_summary("3 madde ile özetle") == (True, 3)


class TestExtractComparisonItems:
    def test_no_comparison_keyword_returns_empty(self) -> None:
        assert extract_comparison_items("Write a blog post about coffee") == []

    def test_vs_pattern_splits_two_items(self) -> None:
        assert extract_comparison_items("React vs Vue") == ["react", "vue"]

    def test_vs_pattern_splits_three_items(self) -> None:
        assert extract_comparison_items("React vs Vue vs Svelte") == [
            "react",
            "vue",
            "svelte",
        ]

    def test_compare_keyword_with_comma_separated_items(self) -> None:
        assert extract_comparison_items("react, vue compare") == ["react", "vue"]

    def test_single_item_before_compare_yields_empty(self) -> None:
        assert extract_comparison_items("react compare") == []

    def test_duplicate_items_are_deduped(self) -> None:
        assert extract_comparison_items("react vs react") == ["react"]

    def test_long_items_are_truncated_to_forty_chars(self) -> None:
        long_name = "a" * 50
        result = extract_comparison_items(f"{long_name} vs short")
        assert result[0] == long_name[:40]


class TestDetectFrontendDownloadFeature:
    def test_full_match_returns_true(self) -> None:
        assert detect_frontend_download_feature(
            "Add a download button to the dashboard"
        )

    def test_missing_action_word_returns_false(self) -> None:
        assert not detect_frontend_download_feature(
            "Add a button to the dashboard"
        )

    def test_missing_add_verb_returns_false(self) -> None:
        assert not detect_frontend_download_feature(
            "The download button on the dashboard is broken"
        )

    def test_missing_surface_word_returns_false(self) -> None:
        assert not detect_frontend_download_feature("Add a download feature")

    def test_export_synonym_matches(self) -> None:
        assert detect_frontend_download_feature(
            "Let users export data from the browser page"
        )
