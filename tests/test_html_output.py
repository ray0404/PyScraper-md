"""Tests for HTML output: cleaned content HTML and full raw HTML.

Covers the Scraper library (scrape() 'html'/'raw_html' keys, to_html(),
content_html()), the --format CLI flag, and the web API/ZIP format
selection. Network and browser calls are mocked; local sample files are
used where a real scrape is needed.
"""
import io
import json
import zipfile

import pytest
from bs4 import BeautifulSoup
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from md_scraper.scraper import Scraper
from md_scraper.cli import cli
from md_scraper.utils import select_output
from md_scraper.web.app import app as flask_app

SAMPLE_URL = "https://example.com/blog/sample"


def _sample_html():
    with open('tests/samples/blog_post.html', 'r') as f:
        return f.read()


def _scrape_sample(**kwargs):
    """Scrape the bundled sample page with fetch_html mocked out."""
    scraper = Scraper()
    with patch.object(Scraper, 'fetch_html', return_value=_sample_html()):
        return scraper.scrape(SAMPLE_URL, **kwargs)


def _text_of(html):
    """Visible text of an HTML fragment, whitespace-normalized."""
    return ' '.join(BeautifulSoup(html, 'lxml').get_text(' ').split())


# ---------------------------------------------------------------------------
# Library: scrape() result keys
# ---------------------------------------------------------------------------

def test_scrape_returns_html_and_raw_html():
    result = _scrape_sample()

    # Raw HTML is the complete fetched document, untouched.
    assert result['raw_html'] == _sample_html()
    assert '<nav>' in result['raw_html']
    assert 'Home' in result['raw_html']
    assert '<footer>' in result['raw_html']

    # Content HTML is the cleaned main content only.
    html = result['html']
    assert '<main>' in html
    assert 'Sample Blog Post' in html
    assert 'main content' in html
    assert '<nav>' not in html
    assert 'Home' not in html
    assert '<footer>' not in html
    assert '2023 Sample Blog' not in html  # footer text, not the <h1>


def test_html_is_content_equivalent_of_markdown():
    result = _scrape_sample()
    markdown = result['markdown']
    html = result['html']

    # Same headings, list items and emphasized text in both outputs.
    assert '# Sample Blog Post' in markdown
    assert '<h1>Sample Blog Post</h1>' in html
    assert '## Subheading' in markdown
    assert '<h2>Subheading</h2>' in html
    assert '- Item 1' in markdown
    assert '<li>Item 1</li>' in html
    assert 'This is the **main content**' in markdown
    assert '<strong>main content</strong>' in html


def test_html_sample_text_matches_markdown_text():
    result = _scrape_sample()
    html_text = _text_of(result['html'])
    # Markdown rendered back to plain text should carry the same words.
    md_text = ' '.join(
        result['markdown'].replace('#', '').replace('*', '').replace('-', '').split()
    )
    assert html_text == md_text


def test_scrape_html_with_local_file(tmp_path):
    """scrape() on a local HTML file also returns both HTML outputs."""
    p = tmp_path / "page.html"
    p.write_text(
        "<html><head><title>Local</title></head><body>"
        "<nav>Nav</nav><main><h1>Local Page</h1><p>Body text.</p></main>"
        "</body></html>",
        encoding="utf-8",
    )
    result = Scraper().scrape(str(p))
    assert '<main>' in result['html']
    assert 'Local Page' in result['html']
    assert 'Nav' not in result['html']
    assert '<nav>Nav</nav>' in result['raw_html']


# ---------------------------------------------------------------------------
# Library: SVG / image actions apply to HTML exactly as to Markdown
# ---------------------------------------------------------------------------

def test_html_svg_as_image_matches_markdown():
    scraper = Scraper()
    html = '<svg width="10" height="10"><circle r="5" /></svg>'
    markdown = scraper.to_markdown(html, svg_action='image')
    html_out = scraper.to_html(html, svg_action='image')
    assert 'data:image/svg+xml;base64,' in markdown
    assert 'data:image/svg+xml;base64,' in html_out
    assert '<svg' not in html_out


def test_html_svg_strip_and_preserve():
    scraper = Scraper()
    html = '<p>Text</p><svg width="10" height="10"><circle r="5" /></svg>'

    stripped = scraper.to_html(html, svg_action='strip')
    assert '<svg' not in stripped
    assert 'Text' in stripped

    preserved = scraper.to_html(html, svg_action='preserve')
    assert '<svg' in preserved
    assert '<circle' in preserved


def test_html_image_base64_action():
    scraper = Scraper()
    html = '<img src="https://example.com/test.png" alt="pic">'

    with patch('requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"fake image data"
        mock_resp.headers = {'Content-Type': 'image/png'}
        mock_get.return_value = mock_resp

        markdown = scraper.to_markdown(html, image_action='base64')
        html_out = scraper.to_html(html, image_action='base64')

    # Both outputs embed the image; the HTML keeps the processed src.
    assert 'data:image/png;base64,' in markdown
    assert 'data:image/png;base64,' in html_out
    assert 'https://example.com/test.png' not in html_out


def test_to_markdown_restores_image_srcs_by_default():
    """Direct to_markdown() callers keep their soup untouched by default."""
    scraper = Scraper()
    soup = BeautifulSoup(
        '<img src="https://example.com/test.png" alt="pic">', 'lxml'
    )

    with patch('requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"fake image data"
        mock_resp.headers = {'Content-Type': 'image/png'}
        mock_get.return_value = mock_resp

        scraper.to_markdown(soup, image_action='base64')

    # Default restore_original_srcs=True: the caller's soup is unchanged.
    assert soup.find('img')['src'] == 'https://example.com/test.png'

    with patch('requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"fake image data"
        mock_resp.headers = {'Content-Type': 'image/png'}
        mock_get.return_value = mock_resp

        scraper.to_markdown(soup, image_action='base64',
                            restore_original_srcs=False)

    # Opted out: the processed (base64) src stays in the soup.
    assert soup.find('img')['src'].startswith('data:image/png;base64,')


# ---------------------------------------------------------------------------
# Library: strip, to_html(), content_html()
# ---------------------------------------------------------------------------

def test_html_strip_matches_markdown_strip():
    scraper = Scraper()
    html = ('<p>Check <a href="https://example.com">this link</a> and '
            '<img src="img.png" alt="image"></p>')

    markdown = scraper.to_markdown(html, strip=['a', 'img'])
    html_out = scraper.to_html(html, strip=['a', 'img'])

    # Links: tag gone, text kept — in both outputs.
    assert 'this link' in markdown
    assert 'https://example.com' not in markdown
    assert 'this link' in html_out
    assert '<a' not in html_out
    assert 'https://example.com' not in html_out
    # Images: gone entirely — in both outputs.
    assert '<img' not in html_out
    assert 'img.png' not in html_out


def test_to_html_direct():
    scraper = Scraper()
    html = '<h1>Title</h1><p>Paragraph with <strong>bold</strong> text.</p>'
    out = scraper.to_html(html)
    assert '<h1>Title</h1>' in out
    assert '<strong>bold</strong>' in out
    # to_html converts what it is given; it does not extract main content.
    nav_html = '<nav>Nav</nav><main><p>Main</p></main>'
    assert '<nav>Nav</nav>' in scraper.to_html(nav_html)


def test_content_html_fallback_extraction():
    scraper = Scraper()
    out = scraper.content_html(_sample_html())
    assert '<main>' in out
    assert 'Sample Blog Post' in out
    assert '<nav>' not in out
    assert 'Home' not in out


def test_select_output_formats():
    result = {
        'markdown': '# Title',
        'html': '<main><h1>Title</h1></main>',
        'raw_html': '<html><body><main><h1>Title</h1></main></body></html>',
    }
    assert select_output(result, 'markdown') == ('# Title', '.md')
    assert select_output(result, 'html') == ('<main><h1>Title</h1></main>', '.html')
    assert select_output(result, 'html-raw') == (
        '<html><body><main><h1>Title</h1></main></body></html>', '.html')
    # Unknown format falls back to Markdown.
    assert select_output(result, 'bogus') == ('# Title', '.md')


def test_select_output_falls_back_for_old_server_results():
    # A result from an older server has raw_html but no 'html' key.
    result = {'markdown': '# Title', 'raw_html': _sample_html()}
    content, ext = select_output(result, 'html', Scraper())
    assert ext == '.html'
    assert '<main>' in content
    assert 'Sample Blog Post' in content
    assert 'Home' not in content


# ---------------------------------------------------------------------------
# CLI: --format
# ---------------------------------------------------------------------------

def _mocked_cli_result():
    return {
        'markdown': '# Mocked Markdown',
        'html': '<main><h1>Mocked Markdown</h1></main>',
        'raw_html': '<html><body><main><h1>Mocked Markdown</h1></main></body></html>',
        'metadata': {'title': 'Test'},
    }


def _run_cli(args, mock_result=None):
    runner = CliRunner()
    with patch("md_scraper.cli.Scraper") as mock_scraper_class:
        mock_instance = mock_scraper_class.return_value
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.scrape.return_value = (
            mock_result if mock_result is not None else _mocked_cli_result()
        )
        result = runner.invoke(cli, args)
        return result, mock_instance


def test_cli_format_defaults_to_markdown():
    result, _ = _run_cli(['scrape', 'https://example.com'])
    assert result.exit_code == 0
    assert '# Mocked Markdown' in result.output
    assert '<main>' not in result.output


def test_cli_format_html():
    result, _ = _run_cli(['scrape', 'https://example.com', '--format', 'html'])
    assert result.exit_code == 0
    assert '<main><h1>Mocked Markdown</h1></main>' in result.output
    assert '# Mocked Markdown' not in result.output


def test_cli_format_html_raw():
    result, _ = _run_cli(
        ['scrape', 'https://example.com', '--format', 'html-raw'])
    assert result.exit_code == 0
    assert '<html><body>' in result.output


def test_cli_format_invalid_is_rejected():
    result, _ = _run_cli(
        ['scrape', 'https://example.com', '--format', 'pdf'])
    assert result.exit_code != 0


def test_cli_format_html_output_file_uses_html_extension(tmp_path):
    outdir = tmp_path / "outdir"
    outdir.mkdir()
    runner = CliRunner()
    with patch("md_scraper.cli.Scraper") as mock_scraper_class:
        mock_instance = mock_scraper_class.return_value
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.scrape.return_value = _mocked_cli_result()
        result = runner.invoke(cli, [
            'scrape', 'https://example.com', '--format', 'html',
            '--output', str(outdir),
        ])
    assert result.exit_code == 0
    assert (outdir / "Test.html").read_text() == '<main><h1>Mocked Markdown</h1></main>'


def test_cli_format_passed_to_remote_payload():
    runner = CliRunner()
    with patch('md_scraper.cli.requests.post') as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = _mocked_cli_result()
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        result = runner.invoke(cli, [
            'scrape', 'https://example.com',
            '--server', 'https://scraper.example.com',
            '--format', 'html-raw',
        ])
        assert result.exit_code == 0
        payload = mock_post.call_args.kwargs.get('json') or mock_post.call_args[1]['json']
        assert payload['format'] == 'html-raw'
        assert '<html><body>' in result.output


def test_cli_html_falls_back_for_old_server_result():
    """No 'html' key in the result: extract content HTML from raw_html."""
    old_result = {
        'markdown': '# Old Server',
        'raw_html': _sample_html(),
        'metadata': {'title': 'Sample'},
    }
    runner = CliRunner()
    with patch("md_scraper.cli.Scraper") as mock_scraper_class:
        mock_instance = mock_scraper_class.return_value
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.scrape.return_value = old_result
        # The shared scraper is a mock; give its fallback a real behavior.
        mock_instance.content_html.side_effect = (
            lambda raw: Scraper().content_html(raw)
        )
        result = runner.invoke(
            cli, ['scrape', 'https://example.com', '--format', 'html'])
    assert result.exit_code == 0
    assert '<main>' in result.output
    assert 'Sample Blog Post' in result.output
    assert 'Home' not in result.output


def test_cli_format_html_on_local_file(tmp_path):
    """End-to-end: real scraper on a local HTML file with --format html."""
    page = tmp_path / "page.html"
    page.write_text(
        "<html><body><nav>Nav</nav><main><h1>Local</h1><p>Text.</p></main>"
        "</body></html>",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(cli, ['scrape', str(page), '--format', 'html'])
    assert result.exit_code == 0
    assert '<main>' in result.output
    assert 'Local' in result.output
    assert 'Nav' not in result.output


# ---------------------------------------------------------------------------
# Standalone HTML documents: wrap_html_document() + 'html-document' format
# ---------------------------------------------------------------------------

def test_wrap_html_document_structure():
    doc = Scraper.wrap_html_document(
        '<main><h1>Title</h1><p>Text.</p></main>',
        title='My Page',
        source_url='https://example.com/article',
        metadata={'author': 'Jane', 'description': 'A page.'},
    )
    assert doc.startswith('<!DOCTYPE html>\n<html lang="en">')
    assert '<meta charset="utf-8">' in doc
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in doc
    assert '<title>My Page</title>' in doc
    assert '<meta name="author" content="Jane">' in doc
    assert '<meta name="description" content="A page.">' in doc
    assert '<base href="https://example.com/article">' in doc
    assert '<link rel="canonical" href="https://example.com/article">' in doc
    assert '<style>' in doc and 'max-width: 800px' in doc
    assert '<main><h1>Title</h1><p>Text.</p></main>' in doc
    assert '<!-- Scraped from https://example.com/article by md-scraper -->' in doc
    assert doc.rstrip().endswith('</html>')
    # Exactly one body element, and the content sits inside it.
    assert doc.count('<body>') == 1 and doc.count('</body>') == 1
    assert doc.index('<body>') < doc.index('<main>')


def test_wrap_html_document_escapes_title_and_meta():
    doc = Scraper.wrap_html_document('<p>x</p>', title='<b>Bold</b> & "quoted"')
    assert '<title>&lt;b&gt;Bold&lt;/b&gt; &amp; &quot;quoted&quot;</title>' in doc
    assert '<b>Bold</b>' not in doc.split('<body>')[0]


def test_wrap_html_document_title_fallbacks():
    doc = Scraper.wrap_html_document('<p>x</p>', source_url='https://example.com/x')
    assert '<title>https://example.com/x</title>' in doc
    assert '<title>Scraped Page</title>' in Scraper.wrap_html_document('<p>x</p>')


def test_wrap_html_document_no_base_for_local_source():
    doc = Scraper.wrap_html_document('<p>x</p>', title='Local',
                                     source_url='/tmp/page.html')
    assert '<base' not in doc
    assert 'rel="canonical"' not in doc


def test_wrap_html_document_include_base_false():
    doc = Scraper.wrap_html_document('<p>x</p>', title='T',
                                     source_url='https://example.com/x',
                                     include_base=False)
    assert '<base' not in doc
    # The canonical link is still useful without a base element.
    assert '<link rel="canonical" href="https://example.com/x">' in doc


def test_wrap_html_document_returns_full_document_unchanged():
    full = ('<!DOCTYPE html>\n<html><head><title>Old</title></head>'
            '<body><p>x</p></body></html>')
    assert Scraper.wrap_html_document(full) == full
    full2 = '<html lang="en"><head></head><body><p>x</p></body></html>'
    assert Scraper.wrap_html_document(full2) == full2


def test_wrap_html_document_unwraps_body_fragment():
    doc = Scraper.wrap_html_document('<body><p>Inner</p></body>', title='T')
    assert doc.count('<body>') == 1
    assert '<p>Inner</p>' in doc


def test_wrap_html_document_empty():
    assert Scraper.wrap_html_document('') == ''
    assert Scraper.wrap_html_document('   ') == ''


def test_scrape_returns_html_document():
    result = _scrape_sample()
    doc = result['html_document']
    assert doc.startswith('<!DOCTYPE html>')
    assert '<title>Sample Blog Post</title>' in doc
    assert '<base href="https://example.com/blog/sample">' in doc
    assert '<main>' in doc
    assert 'Sample Blog Post' in doc
    assert 'Home' not in doc
    assert '2023 Sample Blog' not in doc
    # The wrapped document contains the same content fragment as 'html'.
    assert result['html'].strip() in doc
    # Same visible body text as the content HTML.
    body_text = _text_of(str(BeautifulSoup(doc, 'lxml').body))
    assert 'Sample Blog Post' in body_text
    assert 'Item 1' in body_text
    assert 'Home' not in body_text


def test_scrape_html_document_omits_base_for_file_assets(tmp_path):
    result = _scrape_sample(image_action='file',
                            assets_dir=str(tmp_path / 'assets'))
    assert '<base' not in result['html_document']
    # The document itself is still produced.
    assert result['html_document'].startswith('<!DOCTYPE html>')


def test_select_output_html_document():
    result = {
        'markdown': '# T',
        'html': '<main><h1>T</h1></main>',
        'html_document': '<!DOCTYPE html>\n<html><body><main><h1>T</h1></main></body></html>',
        'raw_html': '<html><body><main><h1>T</h1></main></body></html>',
        'metadata': {'title': 'T'},
        'url': 'https://example.com',
    }
    content, ext = select_output(result, 'html-document')
    assert ext == '.html'
    assert content.startswith('<!DOCTYPE html>')


def test_select_output_html_document_wraps_locally_for_old_results():
    result = {
        'markdown': '# T',
        'html': '<main><h1>T</h1></main>',
        'raw_html': '<html><body><main><h1>T</h1></main></body></html>',
        'metadata': {'title': 'T'},
        'url': 'https://example.com/x',
    }
    content, ext = select_output(result, 'html-document')
    assert ext == '.html'
    assert content.startswith('<!DOCTYPE html>')
    assert '<title>T</title>' in content
    assert '<base href="https://example.com/x">' in content
    assert '<main><h1>T</h1></main>' in content


def test_select_output_html_document_falls_back_to_raw_html():
    result = {
        'markdown': '# T',
        'raw_html': _sample_html(),
        'metadata': {'title': 'Sample'},
        'url': 'https://example.com/blog/sample',
    }
    content, ext = select_output(result, 'html-document', Scraper())
    assert ext == '.html'
    assert content.startswith('<!DOCTYPE html>')
    assert 'Sample Blog Post' in content
    assert 'Home' not in content


def test_cli_format_html_document():
    result, _ = _run_cli(['scrape', 'https://example.com',
                          '--format', 'html-document'])
    assert result.exit_code == 0
    assert '<!DOCTYPE html>' in result.output
    assert '<title>Test</title>' in result.output
    assert '<main><h1>Mocked Markdown</h1></main>' in result.output


def test_cli_format_html_document_output_file(tmp_path):
    outdir = tmp_path / "outdir"
    outdir.mkdir()
    runner = CliRunner()
    with patch("md_scraper.cli.Scraper") as mock_scraper_class:
        mock_instance = mock_scraper_class.return_value
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.scrape.return_value = _mocked_cli_result()
        result = runner.invoke(cli, [
            'scrape', 'https://example.com', '--format', 'html-document',
            '--output', str(outdir),
        ])
    assert result.exit_code == 0
    assert (outdir / "Test.html").read_text().startswith('<!DOCTYPE html>')


def test_cli_format_html_document_on_local_file(tmp_path):
    """End-to-end: real scraper on a local file with --format html-document."""
    page = tmp_path / "page.html"
    page.write_text(
        "<html><head><title>Local</title></head><body>"
        "<nav>Nav</nav><main><h1>Local</h1><p>Text.</p></main>"
        "</body></html>",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(cli, ['scrape', str(page),
                                  '--format', 'html-document'])
    assert result.exit_code == 0
    assert '<!DOCTYPE html>' in result.output
    assert '<title>Local</title>' in result.output
    assert '<main>' in result.output
    assert 'Nav' not in result.output


# ---------------------------------------------------------------------------
# Web API: /api/scrape gains the keys, /api/download-zip honors format
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        yield client


def test_api_scrape_returns_html_keys(client):
    with patch("md_scraper.web.app.Scraper.scrape") as mock_scrape:
        mock_scrape.return_value = {
            'url': 'https://example.com',
            'markdown': '# Success',
            'html': '<main><h1>Success</h1></main>',
            'raw_html': '<html><body><main><h1>Success</h1></main></body></html>',
            'metadata': {'title': 'Test Title'},
        }
        response = client.post('/api/scrape', json={'url': 'https://example.com'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['html'] == '<main><h1>Success</h1></main>'
        assert data['raw_html'].startswith('<html>')


def test_download_zip_format_html(client):
    results = [{
        'url': 'https://example.com/1',
        'markdown': 'Content 1',
        'html': '<main><h1>Content 1</h1></main>',
        'raw_html': '<html><body>Content 1</body></html>',
        'metadata': {'title': 'Page 1'},
    }]
    response = client.post('/api/download-zip',
                           data=json.dumps({'results': results, 'format': 'html'}),
                           content_type='application/json')
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data), 'r') as zf:
        assert 'Page_1.html' in zf.namelist()
        assert zf.read('Page_1.html').decode('utf-8') == '<main><h1>Content 1</h1></main>'


def test_download_zip_format_html_raw(client):
    results = [{
        'url': 'https://example.com/1',
        'markdown': 'Content 1',
        'html': '<main><h1>Content 1</h1></main>',
        'raw_html': '<html><body>Content 1</body></html>',
        'metadata': {'title': 'Page 1'},
    }]
    response = client.post('/api/download-zip',
                           data=json.dumps({'results': results, 'format': 'html-raw'}),
                           content_type='application/json')
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data), 'r') as zf:
        assert 'Page_1.html' in zf.namelist()
        assert zf.read('Page_1.html').decode('utf-8') == '<html><body>Content 1</body></html>'


def test_download_zip_defaults_to_markdown(client):
    results = [{
        'url': 'https://example.com/1',
        'markdown': 'Content 1',
        'html': '<main><h1>Content 1</h1></main>',
        'raw_html': '<html><body>Content 1</body></html>',
        'metadata': {'title': 'Page 1'},
    }]
    response = client.post('/api/download-zip',
                           data=json.dumps({'results': results}),
                           content_type='application/json')
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data), 'r') as zf:
        assert 'Page_1.md' in zf.namelist()
        assert zf.read('Page_1.md').decode('utf-8') == 'Content 1'


def test_download_zip_format_html_document(client):
    results = [{
        'url': 'https://example.com/1',
        'markdown': 'Content 1',
        'html': '<main><h1>Content 1</h1></main>',
        'html_document': '<!DOCTYPE html>\n<html><body><main><h1>Content 1</h1></main></body></html>',
        'raw_html': '<html><body>Content 1</body></html>',
        'metadata': {'title': 'Page 1'},
    }]
    response = client.post('/api/download-zip',
                           data=json.dumps({'results': results, 'format': 'html-document'}),
                           content_type='application/json')
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data), 'r') as zf:
        assert 'Page_1.html' in zf.namelist()
        assert zf.read('Page_1.html').decode('utf-8').startswith('<!DOCTYPE html>')


def test_api_scrape_returns_html_document_key(client):
    with patch("md_scraper.web.app.Scraper.scrape") as mock_scrape:
        mock_scrape.return_value = {
            'url': 'https://example.com',
            'markdown': '# Success',
            'html': '<main><h1>Success</h1></main>',
            'html_document': '<!DOCTYPE html>\n<html><body><main><h1>Success</h1></main></body></html>',
            'raw_html': '<html><body><main><h1>Success</h1></main></body></html>',
            'metadata': {'title': 'Test Title'},
        }
        response = client.post('/api/scrape', json={'url': 'https://example.com'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['html_document'].startswith('<!DOCTYPE html>')


def test_index_shows_html_document(client):
    with patch("md_scraper.web.app.Scraper.scrape") as mock_scrape:
        mock_scrape.return_value = {
            'url': 'https://example.com',
            'markdown': '# Success',
            'html': '<main><h1>Success</h1></main>',
            'html_document': '<!DOCTYPE html>\n<html><body><main><h1>Success</h1></main></body></html>',
            'raw_html': '<html><body><main><h1>Success</h1></main></body></html>',
            'metadata': {'title': 'Test Title'},
        }
        response = client.post('/', data={'urls': 'https://example.com',
                                          'format': 'html-document'})
        assert response.status_code == 200
        # Jinja escapes the HTML inside the textarea.
        assert b'&lt;!DOCTYPE html&gt;' in response.data
        assert b'HTML document (standalone)' in response.data
