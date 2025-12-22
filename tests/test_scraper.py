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
