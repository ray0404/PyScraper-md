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
