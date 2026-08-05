"""Coverage gap: app.rag.uploads.build_storage_name (previously only exercised
indirectly through full upload API tests).
"""
import hashlib

from app.rag.uploads import build_storage_name


def _expected_digest(content: str) -> str:
    return hashlib.sha1(content.encode("utf-8")).hexdigest()[:10]


def test_build_storage_name_normal_name():
    content = "hello world"
    result = build_storage_name("notes.txt", content)
    digest = _expected_digest(content)

    assert result == f"notes-{digest}.txt"
    assert len(digest) == 10


def test_build_storage_name_digest_matches_sha1_of_content():
    content = "some file content used for hashing"
    result = build_storage_name("report.md", content)

    digest = hashlib.sha1(content.encode("utf-8")).hexdigest()[:10]
    assert result == f"report-{digest}.md"

    # Different content must yield a different digest/name.
    other_result = build_storage_name("report.md", "different content")
    assert other_result != result


def test_build_storage_name_invalid_chars_are_sanitized():
    content = "content"
    result = build_storage_name('weird<>:"/\\|?*name.txt', content)
    digest = _expected_digest(content)

    # Each of the 9 invalid chars (< > : " / \ | ? *) becomes its own underscore.
    assert result == f"weird_________name-{digest}.txt"
    assert result.endswith(f"-{digest}.txt")


def test_build_storage_name_unicode_chars():
    content = "content"
    result = build_storage_name("résumé café.docx", content)
    digest = _expected_digest(content)

    # Accented letters and the space are collapsed to underscores by the stem sanitizer.
    assert result == f"r_sum_caf-{digest}.docx"


def test_build_storage_name_empty_stem_falls_back_to_upload():
    content = "content"
    # A stem made entirely of characters stripped by the stem sanitizer (leaving
    # nothing but underscores, which are then trimmed by .strip("._")) collapses
    # to the "upload" fallback.
    result = build_storage_name("!!!.txt", content)
    digest = _expected_digest(content)

    assert result == f"upload-{digest}.txt"


def test_build_storage_name_missing_suffix_defaults_to_txt():
    content = "content"
    result = build_storage_name("no_extension_name", content)
    digest = _expected_digest(content)

    assert result == f"no_extension_name-{digest}.txt"


def test_build_storage_name_empty_display_name_defaults_to_upload():
    content = "content"
    result = build_storage_name("", content)
    digest = _expected_digest(content)

    assert result == f"upload-{digest}.txt"


def test_build_storage_name_format_has_stem_digest_suffix():
    content = "abc123"
    result = build_storage_name("my-file.PDF", content)
    digest = _expected_digest(content)

    stem, _, rest = result.rpartition("-")
    assert stem == "my-file"
    assert rest == f"{digest}.PDF"
