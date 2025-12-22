import pytest
from click.testing import CliRunner
from unittest.mock import patch
from md_scraper.cli import cli

def test_scrape_command_success():
    runner = CliRunner()
    url = "https://example.com"
    expected_output = "# Mocked Markdown"
    
    # Mock the Scraper.scrape method
    with patch("md_scraper.cli.Scraper") as mock_scraper_class:
        mock_scraper_instance = mock_scraper_class.return_value
        mock_scraper_instance.scrape.return_value = {
            'markdown': expected_output,
            'metadata': {'title': 'Test'}
        }
        
        result = runner.invoke(cli, ['scrape', url])
        
        assert result.exit_code == 0
        assert expected_output in result.output
        mock_scraper_instance.scrape.assert_called_once_with(url, dynamic=False)

def test_scrape_command_failure():
    runner = CliRunner()
    url = "https://example.com/invalid"
    
    with patch("md_scraper.cli.Scraper") as mock_scraper_class:
        mock_scraper_instance = mock_scraper_class.return_value
        # requests.exceptions.HTTPError usually
        from requests.exceptions import HTTPError
        mock_scraper_instance.scrape.side_effect = HTTPError("404 Client Error")
        
        result = runner.invoke(cli, ['scrape', url])
        
        assert result.exit_code != 0
        assert "Error" in result.output

def test_scrape_command_output_file():
    runner = CliRunner()
    url = "https://example.com"
    expected_output = "# Markdown to file"
    
    with patch("md_scraper.cli.Scraper") as mock_scraper_class:
        mock_scraper_instance = mock_scraper_class.return_value
        mock_scraper_instance.scrape.return_value = {
            'markdown': expected_output,
            'metadata': {}
        }
        
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ['scrape', url, '--output', 'result.md'])
            assert result.exit_code == 0
            with open('result.md', 'r') as f:
                assert f.read() == expected_output

def test_scrape_command_options_passing():
    runner = CliRunner()
    url = "https://example.com"
    
    with patch("md_scraper.cli.Scraper") as mock_scraper_class:
        mock_scraper_instance = mock_scraper_class.return_value
        mock_scraper_instance.scrape.return_value = {
            'markdown': "...",
            'metadata': {}
        }
        
        # Test dynamic and strip passing
        runner.invoke(cli, ['scrape', url, '--dynamic', '--strip', 'a', '--strip', 'img'])
        
        mock_scraper_instance.scrape.assert_called_once_with(
            url, 
            dynamic=True, 
            strip=['a', 'img']
        )
