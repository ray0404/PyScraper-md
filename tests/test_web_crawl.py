import pytest
from flask import json
from md_scraper.web.app import app
import md_scraper.web.app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_api_crawl_parameters(client, monkeypatch):
    """Test that the API accepts crawl parameters and invokes Crawler logic."""
    
    # Capture the args passed to Crawler
    captured_args = {}
    
    class MockCrawler:
        def __init__(self, start_urls, max_depth=3, max_pages=10, same_domain=True, only_subpaths=False):
            captured_args['start_urls'] = start_urls
            captured_args['max_depth'] = max_depth
            captured_args['max_pages'] = max_pages
            captured_args['only_subpaths'] = only_subpaths
            self.start_urls = start_urls
            self.queue = [] 

        def __iter__(self):
            # Return a single item to simulate one page scrape
            yield self.start_urls[0], 0

        def add_links(self, links, current_depth):
            pass

    monkeypatch.setattr(md_scraper.web.app, 'Crawler', MockCrawler)

    # Mock Scraper to avoid actual network calls
    class MockScraper:
        def scrape(self, url, **kwargs):
            return {
                'url': url,
                'markdown': '# Mock Content',
                'metadata': {},
                'nav_links': [],
                'internal_links': []
            }
    
    monkeypatch.setattr(md_scraper.web.app, 'Scraper', MockScraper)

    payload = {
        'url': 'https://example.com/start',
        'crawl': True,
        'depth': 5,
        'max_pages': 20,
        'only_subpaths': True
    }
    
    response = client.post('/api/scrape', json=payload)
    
    if response.status_code != 200:
        print(f"Error Response: {response.get_json()}")

    assert response.status_code == 200
    assert captured_args['start_urls'] == ['https://example.com/start']
    assert captured_args['max_depth'] == 5
    assert captured_args['max_pages'] == 20
    assert captured_args['only_subpaths'] is True