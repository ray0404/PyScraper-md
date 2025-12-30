import re
import time
from urllib.parse import urlparse

def sanitize_filename(name):
    """Sanitize a string to be safe for filenames."""
    s = str(name).strip().replace(' ', '_')
    s = re.sub(r'(?u)[^-\w.]', '', s)
    return s[:50]

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
