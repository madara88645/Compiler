from app.rag.uploads import build_storage_name, normalize_display_name


# --------------------------------------------------------------------------
# normalize_display_name
# --------------------------------------------------------------------------


def test_normalize_display_name_strips_directory_components():
    assert normalize_display_name("/etc/passwd") == "passwd"
    assert normalize_display_name("some/dir/notes.txt") == "notes.txt"


def test_normalize_display_name_trims_whitespace():
    assert normalize_display_name("  report.pdf  ") == "report.pdf"


def test_normalize_display_name_none_falls_back_to_default():
    assert normalize_display_name(None) == "upload.txt"


def test_normalize_display_name_empty_string_falls_back_to_default():
    assert normalize_display_name("") == "upload.txt"
    assert normalize_display_name("   ") == "upload.txt"


def test_normalize_display_name_dot_and_dotdot_fall_back_to_default():
    assert normalize_display_name(".") == "upload.txt"
    assert normalize_display_name("..") == "upload.txt"


# --------------------------------------------------------------------------
# build_storage_name
# --------------------------------------------------------------------------


def test_build_storage_name_preserves_extension_and_appends_digest():
    name = build_storage_name("notes.txt", "hello world")
    assert name.startswith("notes-")
    assert name.endswith(".txt")


def test_build_storage_name_is_deterministic_for_same_content():
    first = build_storage_name("notes.txt", "same content")
    second = build_storage_name("notes.txt", "same content")
    assert first == second


def test_build_storage_name_differs_for_different_content():
    first = build_storage_name("notes.txt", "content a")
    second = build_storage_name("notes.txt", "content b")
    assert first != second


def test_build_storage_name_sanitizes_invalid_filename_characters():
    name = build_storage_name('weird<>:"name.txt', "x")
    assert "<" not in name
    assert ">" not in name
    assert ":" not in name
    assert '"' not in name


def test_build_storage_name_defaults_extension_when_missing():
    name = build_storage_name("README", "x")
    assert name.endswith(".txt")
    assert name.startswith("README-")


def test_build_storage_name_truncates_long_extension():
    long_suffix = "." + ("a" * 40)
    name = build_storage_name(f"file{long_suffix}", "x")
    # suffix is capped to the first 16 characters (including the leading dot)
    ext = name.rsplit("-", 1)[-1]
    assert ext.count(".") >= 1
    assert len(ext.split(".", 1)[-1]) <= 16 - 1


def test_build_storage_name_blank_stem_falls_back_to_upload():
    # sanitizing "???.txt" leaves a stem of only underscores, which strips to
    # empty and must fall back to "upload".
    name = build_storage_name("???.txt", "x")
    assert name.split("-", 1)[0] == "upload"
