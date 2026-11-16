import re
import time
from urllib.parse import urlparse

_FILENAME_SANITIZE_RE = re.compile(r'(?u)[^-\w.]')

def sanitize_filename(name):
    """Sanitize a string to be safe for filenames."""
    s = str(name).strip().replace(' ', '_')
    s = _FILENAME_SANITIZE_RE.sub('', s)
    return s[:50]

def select_output(result, output_format, scraper=None):
    """Pick the output text and file extension for a scrape result.

    Args:
        result (dict): A scrape result dict with 'markdown', 'html' and/or
            'raw_html' keys.
        output_format (str): One of 'markdown' (default), 'html' (cleaned
            main content as HTML) or 'html-raw' (full fetched document).
        scraper: Optional Scraper instance, reused for the fallback below.
            When None, a temporary Scraper is created if needed.

    Returns:
        tuple[str, str]: (content, file extension).

    Fallback: results from an older server may have 'raw_html' but no
    'html' key. In that case the content HTML is extracted locally from
    the raw document (main-content extraction only, no SVG/image
    processing) instead of returning nothing.
    """
    if output_format == 'html-raw':
        return result.get('raw_html', ''), '.html'

    if output_format == 'html':
        html = result.get('html')
        if html is None:
            raw_html = result.get('raw_html', '')
            if raw_html:
                if scraper is not None:
                    html = scraper.content_html(raw_html)
                else:
                    # Lazy import to keep this module free of the
                    # scraper's heavier dependencies at import time.
                    from md_scraper.scraper import Scraper
                    with Scraper() as temp_scraper:
                        html = temp_scraper.content_html(raw_html)
            else:
                html = ''
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
