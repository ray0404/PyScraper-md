import pytest
from unittest.mock import patch, MagicMock
from md_scraper.web.app import app as flask_app

@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        yield client

def test_api_scrape_closes_scraper(client):
    with patch("md_scraper.web.app.Scraper") as MockScraper:
        mock_instance = MockScraper.return_value
        mock_instance.scrape.return_value = {'url': 'http://example.com'}
        mock_instance.__enter__.return_value = mock_instance

        response = client.post('/api/scrape', json={'url': 'http://example.com'})

        assert response.status_code == 200
        # If it's not used as a context manager, __enter__ won't be called,
        # and __exit__ (which calls close) won't be called.
        # But wait, the current code doesn't use 'with', so it just calls Scraper()
        # and then methods on it.

        # In current code:
        # scraper = Scraper()
        # ...
        # scraper.scrape(...)

        # We want to ensure that close() is called eventually.
        # Currently it is NOT called.

        assert mock_instance.close.called or mock_instance.__exit__.called, "Scraper.close() was not called"

def test_index_scrape_closes_scraper(client):
    with patch("md_scraper.web.app.Scraper") as MockScraper:
        mock_instance = MockScraper.return_value
        mock_instance.scrape.return_value = {'url': 'http://example.com'}
        mock_instance.__enter__.return_value = mock_instance

        response = client.post('/', data={'urls': 'http://example.com'})

        assert response.status_code == 200
        assert mock_instance.close.called or mock_instance.__exit__.called, "Scraper.close() was not called"
