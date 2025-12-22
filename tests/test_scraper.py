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
