import os
import pytest
from md_scraper.scraper import Scraper

@pytest.fixture
def sample_html_file(tmp_path):
    p = tmp_path / "test.html"
    p.write_text("<html><body><h1>Local HTML</h1></body></html>", encoding="utf-8")
    return str(p)

@pytest.fixture
def sample_mht_file(tmp_path):
    p = tmp_path / "test.mht"
    content = (
        'MIME-Version: 1.0\n'
        'Content-Type: multipart/related; boundary="boundary"\n\n'
        '--boundary\n'
        'Content-Type: text/html; charset="utf-8"\n\n'
        '<html><body><h1>Local MHT</h1></body></html>\n\n'
        '--boundary--'
    )
    p.write_text(content, encoding="utf-8")
    return str(p)

def test_scrape_local_html(sample_html_file):
    scraper = Scraper()
    result = scraper.scrape(sample_html_file)
    assert "Local HTML" in result['markdown']
    assert result['metadata']['title'] is None  # No title tag in sample

def test_scrape_local_mht(sample_mht_file):
    scraper = Scraper()
    result = scraper.scrape(sample_mht_file)
    assert "Local MHT" in result['markdown']

def test_scrape_local_file_not_found():
    scraper = Scraper()
    with pytest.raises(OSError): # open() raises OSError/FileNotFoundError
        scraper.scrape("non_existent_file.html")
