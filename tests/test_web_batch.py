import pytest
import io
import zipfile
import json
from unittest.mock import patch, MagicMock
from md_scraper.web.app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_index_batch_scrape(client):
    urls = "https://example.com/1\nhttps://example.com/2"
    
    with patch('md_scraper.scraper.Scraper.scrape') as mock_scrape:
        mock_scrape.side_effect = [
            {'url': 'https://example.com/1', 'markdown': 'Content 1', 'metadata': {'title': 'Page 1'}},
            {'url': 'https://example.com/2', 'markdown': 'Content 2', 'metadata': {'title': 'Page 2'}}
        ]
        
        response = client.post('/', data={'urls': urls}, follow_redirects=True)
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert "Page 1" in html
        assert "Page 2" in html
        assert "Content 1" in html
        assert "Content 2" in html

def test_download_zip(client):
    results = [
        {'url': 'https://example.com/1', 'markdown': 'Content 1', 'metadata': {'title': 'Page 1'}},
        {'url': 'https://example.com/2', 'markdown': 'Content 2', 'metadata': {'title': 'Page 2'}}
    ]
    
    response = client.post('/api/download_zip', 
                           data=json.dumps({'results': results}),
                           content_type='application/json')
    
    assert response.status_code == 200
    assert response.headers['Content-Disposition'] == 'attachment; filename=scraped_pages.zip'
    
    # Verify ZIP content
    zip_buffer = io.BytesIO(response.data)
    with zipfile.ZipFile(zip_buffer, 'r') as zf:
        files = zf.namelist()
        assert "Page_1.md" in files
        assert "Page_2.md" in files
        assert zf.read("Page_1.md").decode('utf-8') == "Content 1"
