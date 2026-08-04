"""Direct unit tests for PolicyHandler's pure regex/dedup helpers.

test_policy_handler.py exercises these indirectly through compile_text_v2();
this file calls PolicyHandler._has_explicit_path and PolicyHandler._unique
directly to pin down edge cases (cloud-path-before-URL-stripping ordering,
UNC paths, dedup semantics) that aren't individually asserted elsewhere.
"""

from app.heuristics.handlers.policy import PolicyHandler


# --- _has_explicit_path -------------------------------------------------------


def test_has_explicit_path_empty_text_is_false():
    assert PolicyHandler._has_explicit_path("") is False


def test_has_explicit_path_detects_windows_path():
    assert PolicyHandler._has_explicit_path("Open C:\\Users\\me\\notes.txt please") is True


def test_has_explicit_path_detects_posix_path():
    assert PolicyHandler._has_explicit_path("Read /var/log/app/error.log for me") is True


def test_has_explicit_path_detects_unc_path():
    assert PolicyHandler._has_explicit_path(r"Copy from \\fileserver\share\report.docx") is True


def test_has_explicit_path_detects_cloud_path_even_inside_a_url_like_string():
    # Cloud paths (s3://, gs://) are checked BEFORE URL stripping, so they
    # must be detected even though they share the "scheme://" shape a bare
    # URL would have (which the plain URL branch would otherwise strip out).
    assert PolicyHandler._has_explicit_path("Upload the export to s3://my-bucket/out.csv") is True
    assert PolicyHandler._has_explicit_path("Read from gs://data-bucket/input.json") is True


def test_has_explicit_path_ignores_plain_urls():
    text = "Check https://example.com/docs/page for details."
    assert PolicyHandler._has_explicit_path(text) is False


def test_has_explicit_path_detects_relative_file_reference():
    assert PolicyHandler._has_explicit_path("Update ./src/utils/helpers.py next") is True


def test_has_explicit_path_false_for_plain_prose():
    assert PolicyHandler._has_explicit_path("Explain how photosynthesis works") is False


# --- _unique -------------------------------------------------------------------


def test_unique_preserves_first_occurrence_order():
    assert PolicyHandler._unique(["b", "a", "b", "c", "a"]) == ["b", "a", "c"]


def test_unique_strips_whitespace_and_drops_blank_entries():
    assert PolicyHandler._unique([" x ", "", "   ", "x", "y "]) == ["x", "y"]


def test_unique_empty_list_returns_empty_list():
    assert PolicyHandler._unique([]) == []
