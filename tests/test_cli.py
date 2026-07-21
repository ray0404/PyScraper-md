import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from md_scraper.cli import cli

def test_scrape_command_success():
    runner = CliRunner()
    url = "https://example.com"
    expected_output = "# Mocked Markdown"

    # Mock the Scraper class to support context manager
    with patch("md_scraper.cli.Scraper") as mock_scraper_class:
        mock_scraper_instance = mock_scraper_class.return_value
        mock_scraper_instance.__enter__.return_value = mock_scraper_instance
        mock_scraper_instance.scrape.return_value = {
            'markdown': expected_output,
            'metadata': {'title': 'Test'}
        }

        result = runner.invoke(cli, ['scrape', url])

        assert result.exit_code == 0
        assert expected_output in result.output

def test_scrape_command_failure():
    runner = CliRunner()
    url = "https://example.com/invalid"

    with patch("md_scraper.cli.Scraper") as mock_scraper_class:
        mock_scraper_instance = mock_scraper_class.return_value
        mock_scraper_instance.__enter__.return_value = mock_scraper_instance
        # requests.exceptions.HTTPError usually
        from requests.exceptions import HTTPError
        mock_scraper_instance.scrape.side_effect = HTTPError("404 Client Error")

        result = runner.invoke(cli, ['scrape', url])

        # It should exit with non-zero on fatal error (single URL)
        assert result.exit_code != 0

def test_scrape_command_output_file():
    runner = CliRunner()
    url = "https://example.com"
    expected_output = "# Markdown to file"

    with patch("md_scraper.cli.Scraper") as mock_scraper_class:
        mock_scraper_instance = mock_scraper_class.return_value
        mock_scraper_instance.__enter__.return_value = mock_scraper_instance
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
        mock_scraper_instance.__enter__.return_value = mock_scraper_instance
        mock_scraper_instance.scrape.return_value = {
            'markdown': "...",
            'metadata': {}
        }

        # Test dynamic and strip passing
        runner.invoke(cli, ['scrape', url, '--dynamic', '--strip', 'a', '--strip', 'img'])

        mock_scraper_instance.scrape.assert_called_once()
        kwargs = mock_scraper_instance.scrape.call_args.kwargs
        assert kwargs['dynamic'] is True
        assert kwargs['strip'] == ['a', 'img']
        assert kwargs['svg_action'] == 'image'
        assert kwargs['image_action'] == 'remote'

def test_scrape_command_svg_action_passing():
    runner = CliRunner()
    url = "https://example.com"

    with patch("md_scraper.cli.Scraper") as mock_scraper_class:
        mock_scraper_instance = mock_scraper_class.return_value
        mock_scraper_instance.__enter__.return_value = mock_scraper_instance
        mock_scraper_instance.scrape.return_value = {'markdown': "", 'metadata': {}}

        runner.invoke(cli, ['scrape', url, '--svg-action', 'preserve'])

        mock_scraper_instance.scrape.assert_called_once()
        kwargs = mock_scraper_instance.scrape.call_args.kwargs
        assert kwargs['svg_action'] == 'preserve'

def test_scrape_command_proxy_ua_delay_retries():
    runner = CliRunner()
    url = "https://example.com"

    with patch("md_scraper.cli.Scraper") as mock_scraper_class:
        mock_scraper_instance = mock_scraper_class.return_value
        mock_scraper_instance.__enter__.return_value = mock_scraper_instance
        mock_scraper_instance.scrape.return_value = {'markdown': "ok", 'metadata': {}}

        result = runner.invoke(cli, [
            'scrape', url,
            '--proxy', 'http://127.0.0.1:8080',
            '-ua', 'CustomUA/2.0',
            '--delay', '0.5',
            '--retries', '5'
        ])

        assert result.exit_code == 0
        mock_scraper_class.assert_called_with(
            proxy='http://127.0.0.1:8080',
            user_agent='CustomUA/2.0',
            delay=0.5,
            retries=5
        )
