import pytest
from unittest.mock import patch
from md_scraper.web.app import app as flask_app

@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        yield client

def test_index_route(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b"Markdown Scraper" in response.data

def test_scrape_success(client):
    with patch("md_scraper.web.app.Scraper.scrape") as mock_scrape:
        mock_result = {
            'url': 'https://example.com',
            'markdown': '# Success',
            'metadata': {'title': 'Test Title', 'author': 'Test Author'}
        }
        mock_scrape.return_value = mock_result
        
        response = client.post('/', data={'url': 'https://example.com', 'svg_action': 'preserve'})
        assert response.status_code == 200
        assert b"# Success" in response.data
        assert b"Test Title" in response.data
        mock_scrape.assert_called_once_with('https://example.com', dynamic=False, svg_action='preserve')

def test_scrape_failure(client):
    with pytest.MonkeyPatch.context() as mp:
        def mock_scrape(*args, **kwargs):
            raise Exception("Network error")
        mp.setattr("md_scraper.web.app.Scraper.scrape", mock_scrape)
        
        response = client.post('/', data={'url': 'https://example.com'})
        assert response.status_code == 200
        assert b"Error scraping" in response.data
        assert b"Network error" in response.data
