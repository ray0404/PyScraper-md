import pytest
from unittest.mock import patch, MagicMock
from md_scraper.scraper import Scraper

def test_fetch_html_success():
    scraper = Scraper()
    url = "https://example.com"
    html_content = "<html><body><h1>Example</h1></body></html>"
    
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response
        
        result = scraper.fetch_html(url)
        
        mock_get.assert_called_once_with(url)
        assert result == html_content

def test_fetch_html_failure():
    scraper = Scraper()
    url = "https://example.com/404"
    
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 404
        # requests.raise_for_status() raises HTTPError
        from requests.exceptions import HTTPError
        mock_response.raise_for_status.side_effect = HTTPError("404 Client Error")
        mock_get.return_value = mock_response
        
        with pytest.raises(HTTPError):
            scraper.fetch_html(url)

def test_extract_main_content_basic():
    scraper = Scraper()
    html = """
    <html>
        <body>
            <nav>Navigation</nav>
            <main>
                <article>
                    <h1>Title</h1>
                    <p>Main content here.</p>
                </article>
            </main>
            <footer>Footer</footer>
        </body>
    </html>
    """
    extracted = scraper.extract_main_content(html)
    assert "Main content here." in extracted
    assert "Navigation" not in extracted
    assert "Footer" not in extracted

def test_extract_main_content_no_main_tag():
    scraper = Scraper()
    html = """
    <html>
        <body>
            <div class="nav">Nav</div>
            <div class="content">
                <h1>Title</h1>
                <p>Content in div.content</p>
            </div>
            <div class="footer">Foot</div>
        </body>
    </html>
    """
    extracted = scraper.extract_main_content(html)
    assert "Content in div.content" in extracted
    assert "Nav" not in extracted
    assert "Foot" not in extracted

def test_extract_main_content_no_body():
    scraper = Scraper()
    html = "<h1>Minimal</h1>"
    extracted = scraper.extract_main_content(html)
    assert "<h1>Minimal</h1>" in extracted

def test_extract_metadata_og():
    scraper = Scraper()
    html = """
    <html>
        <head>
            <meta property="og:title" content="OG Title">
            <meta property="og:description" content="OG Description">
            <meta name="author" content="OG Author">
        </head>
        <body></body>
    </html>
    """
    metadata = scraper.extract_metadata(html)
    assert metadata['title'] == "OG Title"
    assert metadata['description'] == "OG Description"
    assert metadata['author'] == "OG Author"

def test_extract_metadata_standard():
    scraper = Scraper()
    html = """
    <html>
        <head>
            <title>Standard Title</title>
            <meta name="description" content="Standard Description">
        </head>
        <body></body>
    </html>
    """
    metadata = scraper.extract_metadata(html)
    assert metadata['title'] == "Standard Title"
    assert metadata['description'] == "Standard Description"

def test_extract_metadata_json_ld():
    scraper = Scraper()
    html = """
    <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "NewsArticle",
                "headline": "JSON-LD Title",
                "datePublished": "2023-10-27T12:00:00Z",
                "author": {"@type": "Person", "name": "JSON-LD Author"}
            }
            </script>
        </head>
        <body></body>
    </html>
    """
    metadata = scraper.extract_metadata(html)
    assert metadata['title'] == "JSON-LD Title"
    assert metadata['author'] == "JSON-LD Author"
    assert metadata['date'] == "2023-10-27T12:00:00Z"

def test_extract_metadata_json_ld_list_author():
    scraper = Scraper()
    html = """
    <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "NewsArticle",
                "author": [{"@type": "Person", "name": "Author 1"}, {"@type": "Person", "name": "Author 2"}]
            }
            </script>
        </head>
        <body></body>
    </html>
    """
    metadata = scraper.extract_metadata(html)
    assert metadata['author'] == "Author 1"

def test_extract_metadata_invalid_json_ld():
    scraper = Scraper()
    html = """
    <html>
        <head>
            <script type="application/ld+json">
            { invalid json }
            </script>
        </head>
        <body></body>
    </html>
    """
    metadata = scraper.extract_metadata(html)
    assert metadata['title'] is None

def test_to_markdown_basic():
    scraper = Scraper()
    html = "<h1>Title</h1><p>Paragraph with <strong>bold</strong> text.</p>"
    markdown = scraper.to_markdown(html)
    assert "# Title" in markdown
    assert "Paragraph with **bold** text." in markdown

def test_to_markdown_gfm():
    scraper = Scraper()
    html = """
    <table>
        <tr><th>Header</th></tr>
        <tr><td>Data</td></tr>
    </table>
    <pre><code>print("hello")</code></pre>
    """
    markdown = scraper.to_markdown(html)
    # Check for GFM table and code block markers
    assert "| Header |" in markdown
    assert "```" in markdown
    assert "print(\"hello\")" in markdown

def test_to_markdown_options():
    scraper = Scraper()
    html = '<p>Check <a href="https://example.com">this link</a> and <img src="img.png" alt="image"></p>'
    
    # Strip links
    md_no_links = scraper.to_markdown(html, strip=['a'])
    assert "this link" in md_no_links
    assert "https://example.com" not in md_no_links
    
    # Strip images
    md_no_images = scraper.to_markdown(html, strip=['img'])
    assert "image" not in md_no_images
    assert "this link" in md_no_images

def test_to_markdown_svg_as_image():
    scraper = Scraper()
    html = '<svg width="10" height="10"><circle r="5" /></svg>'
    markdown = scraper.to_markdown(html, svg_action='image')
    assert "![svg image](data:image/svg+xml;base64," in markdown

def test_to_markdown_svg_preserve():
    scraper = Scraper()
    html = '<svg width="10" height="10"><circle r="5" /></svg>'
    markdown = scraper.to_markdown(html, svg_action='preserve')
    assert "<svg" in markdown
    assert "<circle" in markdown

def test_to_markdown_svg_strip():
    scraper = Scraper()
    html = '<p>Text</p><svg width="10" height="10"><circle r="5" /></svg>'
    markdown = scraper.to_markdown(html, svg_action='strip')
    assert "<svg" not in markdown
    assert "Text" in markdown

def test_to_markdown_svg_static_fallback():
    scraper = Scraper()
    # SVG with currentColor and no dimensions, but with viewBox
    html = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="..."/></svg>'
    
    # Run conversion
    markdown = scraper.to_markdown(html, svg_action='image')
    
    # Extract the base64 part
    import re
    import base64
    match = re.search(r'data:image/svg\+xml;base64,([^"\)]+)', markdown)
    assert match is not None
    
    decoded = base64.b64decode(match.group(1)).decode('utf-8')
    
    # Verify fixes were applied
    assert 'fill="#000000"' in decoded
    assert 'width="24"' in decoded
    assert 'height="24"' in decoded

def test_to_markdown_image_base64():
    scraper = Scraper()
    html = '<img src="https://example.com/test.png">'
    
    with patch('requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"fake image data"
        mock_resp.headers = {'Content-Type': 'image/png'}
        mock_get.return_value = mock_resp
        
        markdown = scraper.to_markdown(html, image_action='base64')
        assert "data:image/png;base64," in markdown
        assert "ZmFrZSBpbWFnZSBkYXRh" in markdown # base64 of "fake image data"

def test_to_markdown_image_file(tmp_path):
    scraper = Scraper()
    html = '<img src="https://example.com/test.png">'
    assets_dir = tmp_path / "assets"
    
    with patch('requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"fake data"
        mock_get.return_value = mock_resp
        
        markdown = scraper.to_markdown(html, image_action='file', assets_dir=str(assets_dir))
        
        assert "assets/image_0.png" in markdown
        assert (assets_dir / "image_0.png").exists()
        assert (assets_dir / "image_0.png").read_bytes() == b"fake data"


def test_scrape_orchestration():
    scraper = Scraper()
    url = "https://example.com/article"
    html = """
    <html>
        <head><title>Test Article</title></head>
        <body>
            <main>
                <h1>Test Article</h1>
                <p>Content.</p>
            </main>
        </body>
    </html>
    """
    
    with patch.object(Scraper, 'fetch_html', return_value=html):
        result = scraper.scrape(url)
        
        assert result['metadata']['title'] == "Test Article"
        assert "# Test Article" in result['markdown']
        assert "Content." in result['markdown']
        assert result['url'] == url

def test_scrape_integration_sample():
    scraper = Scraper()
    with open('tests/samples/blog_post.html', 'r') as f:
        html = f.read()
    
    url = "https://example.com/blog/sample"
    with patch.object(Scraper, 'fetch_html', return_value=html):
        result = scraper.scrape(url)
        
        assert result['metadata']['title'] == "Sample Blog Post"
        assert result['metadata']['author'] == "John Doe"
        assert "This is the **main content**" in result['markdown']
        assert "## Subheading" in result['markdown']
        assert "- Item 1" in result['markdown']
        # Boilerplate should be gone
        assert "Home" not in result['markdown']
        assert "&copy;" not in result['markdown']
