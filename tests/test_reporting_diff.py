from app.reporting.diff import generate_html_diff


def test_generate_html_diff_equal():
    # Test identical texts
    text = "hello world\nline 2"
    result = generate_html_diff(text, text)
    assert result == "hello world\nline 2"


def test_generate_html_diff_empty_old():
    # Test empty old text
    result = generate_html_diff("", "added text")
    assert result == '<span class="diff-added">added text</span>'


def test_generate_html_diff_empty_new():
    # Test empty new text
    result = generate_html_diff("deleted text", "")
    assert result == '<span class="diff-removed">deleted text</span>'


def test_generate_html_diff_changes():
    old_text = "hello apple world"
    new_text = "hello orange world new"
    result = generate_html_diff(old_text, new_text)

    # Assert it contains the common prefix, suffix, and the additions/removals
    assert "hello " in result
    assert "world" in result
    assert (
        '<span class="diff-added">or</span>a<span class="diff-removed">ppl</span><span class="diff-added">ng</span>e'
        in result
    )
    assert '<span class="diff-added"> new</span>' in result


def test_generate_html_diff_delete_only():
    # Test delete opcode explicitly
    old_text = "hello apple world"
    new_text = "hello world"
    result = generate_html_diff(old_text, new_text)
    assert "hello " in result
    assert "world" in result
    assert '<span class="diff-removed">apple </span>' in result


def test_generate_html_diff_escape():
    # Test HTML escaping behavior
    old_text = "hello <b>"
    new_text = "hello <i>"
    result = generate_html_diff(old_text, new_text)
    assert "hello &lt;" in result
    assert '<span class="diff-removed">b</span><span class="diff-added">i</span>' in result
    assert "&gt;" in result
