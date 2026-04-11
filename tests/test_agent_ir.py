from app.adapters.agent_ir import (
    _parse_bullets,
    _extract_title,
    _parse_sections,
    _split_multi_agent_blocks,
    parse_agent_markdown,
)


def test_parse_bullets_empty_and_plain_text():
    # Covers:
    # 70->66 (empty bullet)
    # 74->66 (empty numbered item)
    # 72->66 (plain text not matching bullet or number)
    text = """
- \t
    * Valid bullet
• \t
1. \t
    2. Valid number
    Just some plain text
    """
    items = _parse_bullets(text)
    assert items == ["Valid bullet", "Valid number"]


def test_extract_title_missing_or_no_match():
    # Covers:
    # 83->81 (headers that don't match "# ")
    # 93 (no valid title found, returns "AI Agent")
    text = """
    ## Not a title
    ### Also not a title
    Just some text
    """
    assert _extract_title(text) == "AI Agent"


def test_parse_sections_heading_after_section():
    # Covers 111-113: A top level heading (# ) appearing after a pending section
    text = """
## Role
    Some role content
# Another Title
    Some text
    """
    sections = _parse_sections(text)
    assert sections == {"role": "Some role content"}


def test_parse_sections_no_sections():
    # Covers 118->121: No section key ever encountered
    text = """
    Just a bunch of text.
    No headers at all.
    """
    sections = _parse_sections(text)
    assert sections == {}


def test_split_multi_agent_blocks_fences_and_empty():
    # Covers 199 (in_fence toggle)
    # 203->205 (empty block text)
    # 210->213 (empty tail)
    text = """
    Agent 1 code
    ```
    Some code with a fake separator
    ---
    ```
    ---

    ---
    Agent 2 code
    ~~~
    Another fake separator
    ---
    ~~~
    ---
    """
    blocks = _split_multi_agent_blocks(text)
    assert len(blocks) == 2
    assert "Agent 1 code" in blocks[0]
    assert "fake separator" in blocks[0]
    assert "Agent 2 code" in blocks[1]
    assert "Another fake separator" in blocks[1]


def test_parse_agent_markdown_no_title():
    text = """
## Role
    I am an agent without a name.
    """
    ir = parse_agent_markdown(text)
    assert ir.name == "AI Agent"
    assert ir.role == "I am an agent without a name."
