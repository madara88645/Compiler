import pytest

from app.heuristics.handlers.context_suggestions import ContextSuggestionHandler


@pytest.fixture
def handler():
    return ContextSuggestionHandler()


# --------------------------------------------------------------------------
# Exact filename matching
# --------------------------------------------------------------------------


def test_exact_filename_match(handler):
    text = "Take a look at auth.py and fix the bug."
    suggestions = handler._find_suggestions(text, ["app/services/auth.py"])

    assert len(suggestions) == 1
    assert suggestions[0]["path"] == "app/services/auth.py"
    assert suggestions[0]["name"] == "auth.py"
    assert suggestions[0]["reason"] == "Mentioned 'auth.py'"


def test_no_match_returns_empty_list(handler):
    text = "Please write a poem about the ocean."
    suggestions = handler._find_suggestions(text, ["app/services/auth.py"])
    assert suggestions == []


# --------------------------------------------------------------------------
# Stem matching via word-boundary regex
# --------------------------------------------------------------------------


def test_stem_match_as_distinct_word(handler):
    text = "Please fix the auth logic in the backend."
    suggestions = handler._find_suggestions(text, ["app/services/auth.py"])

    assert len(suggestions) == 1
    assert suggestions[0]["path"] == "app/services/auth.py"
    assert suggestions[0]["reason"] == "Topic 'auth' detected"


def test_stem_match_requires_word_boundary_not_substring(handler):
    # "authentication" contains "auth" as a substring but not as a distinct
    # word, so a stem of "auth" should not match it.
    text = "We need better authentication in this service."
    suggestions = handler._find_suggestions(text, ["app/services/auth.py"])
    assert suggestions == []


def test_short_stem_is_skipped_to_avoid_noise(handler):
    # Stems shorter than 3 chars (e.g. "db" from db.py) are skipped entirely,
    # even when the filename is mentioned verbatim in the text — the length
    # guard runs before the exact-filename check.
    text = "Please update db.py now."
    suggestions = handler._find_suggestions(text, ["app/db.py"])
    assert suggestions == []


# --------------------------------------------------------------------------
# Dedup
# --------------------------------------------------------------------------


def test_same_path_not_suggested_twice(handler):
    # Filename and stem both appear in text, but the same path must only be
    # suggested once (exact filename match takes priority via `continue`).
    text = "Look at auth.py — the auth module needs work."
    suggestions = handler._find_suggestions(text, ["app/services/auth.py"])

    assert len(suggestions) == 1
    assert suggestions[0]["reason"] == "Mentioned 'auth.py'"


def test_duplicate_paths_in_input_deduped(handler):
    text = "Check auth.py carefully."
    suggestions = handler._find_suggestions(
        text, ["app/services/auth.py", "app/services/auth.py"]
    )
    assert len(suggestions) == 1


# --------------------------------------------------------------------------
# Cap at 5
# --------------------------------------------------------------------------


def test_suggestions_capped_at_five(handler):
    text = "Please review auth.py, billing.py, users.py, orders.py, payments.py, and reports.py."
    file_paths = [
        "app/auth.py",
        "app/billing.py",
        "app/users.py",
        "app/orders.py",
        "app/payments.py",
        "app/reports.py",
    ]

    suggestions = handler._find_suggestions(text, file_paths)

    assert len(suggestions) == 5
    # The cap simply truncates the accumulation order — first five files
    # that matched, in the order they were scanned.
    assert [s["path"] for s in suggestions] == file_paths[:5]


def test_fewer_than_five_matches_returns_all(handler):
    text = "Please review auth.py and billing.py."
    file_paths = ["app/auth.py", "app/billing.py", "app/unrelated.py"]

    suggestions = handler._find_suggestions(text, file_paths)

    assert len(suggestions) == 2
    assert {s["path"] for s in suggestions} == {"app/auth.py", "app/billing.py"}


# --------------------------------------------------------------------------
# Case-insensitivity (text is lowercased before matching)
# --------------------------------------------------------------------------


def test_matching_is_case_insensitive(handler):
    text = "Please check Auth.PY for issues."
    suggestions = handler._find_suggestions(text, ["app/services/auth.py"])
    assert len(suggestions) == 1
