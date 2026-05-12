import pytest
from md_scraper.sanitizer import MarkdownSanitizer

@pytest.fixture
def sanitizer():
    return MarkdownSanitizer()

def test_fix_headers_basic(sanitizer):
    assert sanitizer.sanitize("#Header") == "# Header"
    assert sanitizer.sanitize("##Header") == "## Header"
    assert sanitizer.sanitize("###Header") == "### Header"
    assert sanitizer.sanitize("####Header") == "#### Header"
    assert sanitizer.sanitize("#####Header") == "##### Header"
    assert sanitizer.sanitize("######Header") == "###### Header"

def test_fix_headers_indented(sanitizer):
    # Wrap in newlines to avoid being stripped by the final .strip()
    assert sanitizer.sanitize("Text\n #Header\nEnd") == "Text\n # Header\nEnd"
    assert sanitizer.sanitize("Text\n  ##Header\nEnd") == "Text\n  ## Header\nEnd"
    assert sanitizer.sanitize("Text\n   ###Header\nEnd") == "Text\n   ### Header\nEnd"

    # Check that 4 spaces are NOT treated as header (though .strip() might still affect single line)
    assert sanitizer.sanitize("Text\n    #Header\nEnd") == "Text\n    #Header\nEnd"

def test_fix_headers_already_correct(sanitizer):
    assert sanitizer.sanitize("# Header") == "# Header"
    assert sanitizer.sanitize("Text\n  ## Header\nEnd") == "Text\n  ## Header\nEnd"

def test_fix_headers_not_at_start(sanitizer):
    assert sanitizer.sanitize("Not a #Header") == "Not a #Header"
    assert sanitizer.sanitize("Word #Header") == "Word #Header"

def test_fix_headers_multiline(sanitizer):
    input_md = """#Header 1
Some text here.

##Header 2
More text.
   ###Header 3
Indented text."""

    expected_md = """# Header 1
Some text here.

## Header 2
More text.
   ### Header 3
Indented text."""

    assert sanitizer.sanitize(input_md) == expected_md

def test_other_sanitizations(sanitizer):
    # Excessive newlines
    assert sanitizer.sanitize("Line 1\n\n\n\nLine 2") == "Line 1\n\nLine 2"

    # Trailing whitespace
    assert sanitizer.sanitize("Line with space    \nLine 2") == "Line with space\nLine 2"

    # Empty links/images
    assert sanitizer.sanitize("[]()") == ""
    assert sanitizer.sanitize("![]()") == ""

    # HTML comments
    assert sanitizer.sanitize("Text <!-- comment --> more text") == "Text  more text"
