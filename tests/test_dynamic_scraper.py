import pytest
from unittest.mock import MagicMock, patch
from md_scraper.scraper import Scraper

def test_fetch_html_dynamic_success():
    scraper = Scraper()
    url = "https://example.com/dynamic"
    expected_html = "<html><body><div id='app'>Loaded</div></body></html>"
    
    # Mock playwright.sync_api.sync_playwright
    with patch("md_scraper.scraper.sync_playwright") as mock_sync_playwright:
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()
        
        mock_sync_playwright.return_value.__enter__.return_value = mock_p
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page
        mock_page.content.return_value = expected_html
        
        html = scraper.fetch_html_dynamic(url)
        
        assert html == expected_html
        mock_p.chromium.launch.assert_called_once()
        mock_page.goto.assert_called_with(url)

def test_fetch_html_dynamic_missing_playwright():
    # Simulate ImportError when importing playwright
    with patch.dict('sys.modules', {'playwright.sync_api': None}):
        scraper = Scraper()
        # We need to ensure the module-level import also fails or is handled
        # Since we put the import inside the method or try-except block
        with pytest.raises(ImportError, match="Playwright is not installed"):
            scraper.fetch_html_dynamic("https://example.com")

def test_scrape_with_dynamic_flag():
    scraper = Scraper()
    url = "https://example.com/dynamic"
    
    with patch.object(Scraper, 'fetch_html', return_value="static") as mock_static:
        with patch.object(Scraper, 'fetch_html_dynamic', return_value="dynamic") as mock_dynamic:
            with patch.object(Scraper, 'extract_metadata', return_value={}):
                with patch.object(Scraper, 'extract_main_content', return_value=""):
                    with patch.object(Scraper, 'to_markdown', return_value=""):
                        
                        # Default (False)
                        scraper.scrape(url)
                        mock_static.assert_called_once()
                        mock_dynamic.assert_not_called()
                        
                        mock_static.reset_mock()
                        mock_dynamic.reset_mock()
                        
                        # Explicit False
                        scraper.scrape(url, dynamic=False)
                        mock_static.assert_called_once()
                        mock_dynamic.assert_not_called()
                        
                        mock_static.reset_mock()
                        mock_dynamic.reset_mock()
                        
                        # Explicit True
                        scraper.scrape(url, dynamic=True)
                        mock_static.assert_not_called()
                        mock_dynamic.assert_called_once()
