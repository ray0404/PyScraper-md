import re
import time
from urllib.parse import urlparse

_FILENAME_SANITIZE_RE = re.compile(r'(?u)[^-\w.]')

def sanitize_filename(name):
    """Sanitize a string to be safe for filenames."""
    s = str(name).strip().replace(' ', '_')
    s = _FILENAME_SANITIZE_RE.sub('', s)
    return s[:50]

def _content_html(result, scraper):
    """Content HTML for a result, extracting locally if the key is missing.

    Results from an older server may have 'raw_html' but no 'html' key. In
    that case the content HTML is extracted locally from the raw document
    (main-content extraction only, no SVG/image processing) instead of
    returning nothing. `scraper`, when given, is reused for the fallback;
    otherwise a temporary Scraper is created.
    """
    html = result.get('html')
    if html is not None:
        return html
    raw_html = result.get('raw_html', '')
    if not raw_html:
        return ''
    if scraper is not None:
        return scraper.content_html(raw_html)
    # Lazy import to keep this module free of the scraper's heavier
    # dependencies at import time.
    from md_scraper.scraper import Scraper
    with Scraper() as temp_scraper:
        return temp_scraper.content_html(raw_html)


def select_output(result, output_format, scraper=None):
    """Pick the output text and file extension for a scrape result.

    Args:
        result (dict): A scrape result dict with 'markdown', 'html',
            'html_document' and/or 'raw_html' keys.
        output_format (str): One of 'markdown' (default), 'html' (cleaned
            main content as HTML), 'html-document' (that content wrapped
            in a complete standalone HTML document) or 'html-raw' (full
            fetched document).
        scraper: Optional Scraper instance, reused for the fallback below.
            When None, a temporary Scraper is created if needed.

    Returns:
        tuple[str, str]: (content, file extension).
    """
    if output_format == 'html-raw':
        return result.get('raw_html', ''), '.html'

    if output_format in ('html', 'html-document'):
        html = _content_html(result, scraper)
        if output_format == 'html-document':
            doc = result.get('html_document')
            if doc is None:
                # Older result without a pre-wrapped document: wrap the
                # content HTML locally.
                from md_scraper.scraper import Scraper
                doc = Scraper.wrap_html_document(
                    html,
                    title=result.get('metadata', {}).get('title'),
                    source_url=result.get('url'),
                    metadata=result.get('metadata', {}),
                )
            return doc, '.html'
        return html, '.html'

    return result.get('markdown', ''), '.md'


def get_title_from_result(result, url):
    """Extract a title for the file from metadata or URL."""
    meta = result.get('metadata', {})
    title = meta.get('title')
    
    if not title:
        # Fallback to URL parts
        try:
            path = urlparse(url).path
            if path and path != '/':
                title = path.strip('/').split('/')[-1]
            else:
                title = urlparse(url).netloc
        except:
            title = 'scraped_page'
            
    if not title:
        title = f'scraped_{int(time.time())}'
        
    return sanitize_filename(title)
