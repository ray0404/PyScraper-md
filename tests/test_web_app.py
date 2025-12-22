import pytest
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
    with pytest.MonkeyPatch.context() as mp:
        mock_result = {
            'url': 'https://example.com',
            'markdown': '# Success',
            'metadata': {'title': 'Test Title', 'author': 'Test Author'}
        }
        mp.setattr("md_scraper.web.app.Scraper.scrape", lambda self, url, **kwargs: mock_result)
        
        response = client.post('/', data={'url': 'https://example.com'})
        assert response.status_code == 200
        assert b"# Success" in response.data
        assert b"Test Title" in response.data

def test_scrape_failure(client):
    with pytest.MonkeyPatch.context() as mp:
        def mock_scrape(*args, **kwargs):
            raise Exception("Network error")
        mp.setattr("md_scraper.web.app.Scraper.scrape", mock_scrape)
        
        response = client.post('/', data={'url': 'https://example.com'})
        assert response.status_code == 200
        assert b"Error scraping" in response.data
        assert b"Network error" in response.data
