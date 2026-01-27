import requests
import json
import os
import base64
import email
import re
from typing import Union
from email import policy
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from markdownify import markdownify as md

# Try to import playwright, but don't crash if missing
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

class Scraper:
    """
    A web scraper that converts HTML content from a URL into clean Markdown.
    
    It handles fetching HTML, extracting metadata, identifying main content 
    using heuristics, and converting the resulting DOM to GitHub Flavored Markdown.
    """

    def __init__(self):
        self._playwright = None
        self._browser = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Closes the browser and Playwright instance if they are active."""
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    def _ensure_browser(self):
        """Lazily initializes Playwright and the Browser instance."""
        if sync_playwright is None:
            raise ImportError("Playwright is not installed. Please install it with 'pip install playwright' and 'playwright install'.")

        if not self._playwright:
            self._playwright = sync_playwright().start()

        if not self._browser:
            # Check for CHROMIUM_PATH environment variable (useful for Termux/custom setups)
            executable_path = os.environ.get("CHROMIUM_PATH")
            launch_args = {
                "headless": True
            }
            if executable_path:
                launch_args["executable_path"] = executable_path
                launch_args["args"] = ['--no-sandbox', '--disable-gpu'] # Often needed for custom binaries

            self._browser = self._playwright.chromium.launch(**launch_args)

        return self._browser

    def fetch_html(self, url: str) -> str:
        """
        Fetches the raw HTML content from a given URL or local file.
        
        Args:
            url (str): The URL of the webpage or path to a local file.
            
        Returns:
            str: The raw HTML content.
            
        Raises:
            requests.exceptions.HTTPError: If the request returned an unsuccessful status code.
            FileNotFoundError: If the local file does not exist.
        """
        # 1. Check if it's a local file
        if os.path.exists(url) and os.path.isfile(url):
            return self._read_local_file(url)

        # 2. Existing requests logic
        response = requests.get(url)
        response.raise_for_status()
        return response.text

    def _read_local_file(self, file_path: str) -> str:
        """
        Reads local HTML or MHT files.
        
        Args:
            file_path (str): Path to the local file.
            
        Returns:
            str: The extracted HTML content.
        """
        lower_path = file_path.lower()
        
        if lower_path.endswith('.mht') or lower_path.endswith('.mhtml'):
            with open(file_path, 'rb') as f:
                msg = email.message_from_binary_file(f, policy=policy.default)
                
            # Find the HTML part
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/html":
                        body = part.get_content()
                        # Prefer the first text/html part
                        break
            else:
                # If not multipart, check content type or assume it's the body
                if msg.get_content_type() == "text/html":
                    body = msg.get_content()
            
            if not body:
                # Fallback: try to just decode the payload if specific part finding failed
                try:
                    body = msg.get_body(preferencelist=('html', 'plain')).get_content()
                except Exception:
                    pass

            if not body:
                raise ValueError(f"Could not find text/html content in MHT file: {file_path}")
            
            return body

        else:
            # Assume HTML/text
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()

    def fetch_html_dynamic(self, url: str) -> str:
        """
        Fetches the rendered HTML content from a given URL using Playwright.
        
        Args:
            url (str): The URL of the webpage to fetch.
            
        Returns:
            str: The rendered HTML content of the page.
            
        Raises:
            ImportError: If Playwright is not installed.
            Exception: If browser launch or page navigation fails.
        """
        browser = self._ensure_browser()
        page = browser.new_page()
        try:
            # Set a reasonable viewport size
            page.set_viewport_size({"width": 1280, "height": 800})
            page.goto(url, wait_until="networkidle")

            # Bake computed styles into SVGs so they render correctly in Markdown
            page.evaluate("""() => {
                document.querySelectorAll('svg').forEach(svg => {
                    const style = window.getComputedStyle(svg);
                    const rect = svg.getBoundingClientRect();

                    // 1. Bake dimensions based on actual rendered size
                    // Use rect if it's non-zero, otherwise fallback to reasonable defaults
                    const width = rect.width > 0 ? rect.width : (parseInt(svg.getAttribute('width')) || 16);
                    const height = rect.height > 0 ? rect.height : (parseInt(svg.getAttribute('height')) || 16);

                    svg.setAttribute('width', width);
                    svg.setAttribute('height', height);

                    // 2. Bake colors from computed styles
                    if (svg.getAttribute('fill') === 'currentColor' || !svg.hasAttribute('fill')) {
                        const fill = style.fill !== 'none' ? style.fill : (style.color || '#000000');
                        svg.setAttribute('fill', fill);
                    }
                    if (svg.getAttribute('stroke') === 'currentColor') {
                        svg.setAttribute('stroke', style.stroke || style.color || '#000000');
                    }

                    // 3. Force visibility (many icons are hidden/transparent by default until hover)
                    svg.style.opacity = '1';
                    svg.style.visibility = 'visible';
                    svg.style.display = 'inline-block';

                    // 4. Clean up to reduce Base64 bloat and avoid CSS interference
                    svg.removeAttribute('class');
                    // We keep the style attribute briefly then clean it if it contains complex logic
                });
            }""")

            content = page.content()
            return content
        finally:
            page.close()

    def extract_main_content(self, html: Union[str, BeautifulSoup]) -> str:
        """
        Extracts the primary content area from an HTML string, removing boilerplate.
        
        It attempts to find tags like <main>, <article>, or common content class names.
        Non-content elements such as <nav>, <footer>, <script>, and <style> are removed.
        
        Args:
            html (Union[str, BeautifulSoup]): The raw HTML content or BeautifulSoup object.
            
        Returns:
            str: The HTML string containing only the main content area.
        """
        if isinstance(html, str):
            soup = BeautifulSoup(html, 'lxml')
        else:
            soup = html
        
        # Remove boilerplate
        for tag in soup(['nav', 'footer', 'header', 'aside', 'script', 'style']):
            tag.decompose()
            
        # Try to find main content
        main_content = soup.find('main')
        if not main_content:
            main_content = soup.find('article')
        if not main_content:
            main_content = soup.find('div', class_=['content', 'main', 'post-content'])
            
        if main_content:
            return str(main_content)
        
        # Fallback to body if nothing found
        return str(soup.body) if soup.body else str(soup)

    def extract_metadata(self, html: Union[str, BeautifulSoup]) -> dict:
        """
        Extracts metadata (title, author, date, etc.) from an HTML string.
        
        Supports JSON-LD, OpenGraph, and standard meta tags.
        
        Args:
            html (Union[str, BeautifulSoup]): The raw HTML content or BeautifulSoup object.
            
        Returns:
            dict: A dictionary containing extracted metadata fields.
        """
        if isinstance(html, str):
            soup = BeautifulSoup(html, 'lxml')
        else:
            soup = html

        metadata = {
            'title': None,
            'description': None,
            'author': None,
            'date': None,
            'tags': []
        }

        # 1. Try JSON-LD
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    metadata['title'] = metadata['title'] or data.get('headline') or data.get('name')
                    metadata['description'] = metadata['description'] or data.get('description')
                    metadata['date'] = metadata['date'] or data.get('datePublished')
                    author_data = data.get('author')
                    if isinstance(author_data, dict):
                        metadata['author'] = metadata['author'] or author_data.get('name')
                    elif isinstance(author_data, list) and author_data:
                        if isinstance(author_data[0], dict):
                            metadata['author'] = metadata['author'] or author_data[0].get('name')
            except (json.JSONDecodeError, TypeError):
                continue

        # 2. Try OpenGraph
        og_title = soup.find('meta', property='og:title')
        if og_title:
            metadata['title'] = metadata['title'] or og_title.get('content')
        
        og_desc = soup.find('meta', property='og:description')
        if og_desc:
            metadata['description'] = metadata['description'] or og_desc.get('content')

        # 3. Standard Meta Tags
        author_tag = soup.find('meta', attrs={'name': 'author'})
        if author_tag:
            metadata['author'] = metadata['author'] or author_tag.get('content')
        
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        if desc_tag:
            metadata['description'] = metadata['description'] or desc_tag.get('content')

        # 4. Fallback to <title> tag
        if not metadata['title'] and soup.title:
            metadata['title'] = soup.title.string

        return metadata

    def to_markdown(self, html: str, **options) -> str:
        """
        Converts an HTML string to GitHub Flavored Markdown.
        
        Args:
            html (str): The HTML content to convert.
            **options: Additional options passed to the markdownify library.
                svg_action (str): Action for inline <svg> tags. 
                    'image' (default): Convert to base64 image.
                    'preserve': Keep as raw HTML.
                    'strip': Remove entirely.
                    'file': Save to local file and use relative link.
                image_action (str): Action for <img> tags.
                    'remote' (default): Keep original URL.
                    'base64': Convert remote images to base64.
                    'file': Download to local file and use relative link.
                assets_dir (str): Directory to save images if 'file' action is used.
                base_url (str): Base URL to resolve relative image paths.
            
        Returns:
            str: The resulting Markdown string.
        """
        svg_action = options.pop('svg_action', 'image')
        image_action = options.pop('image_action', 'remote')
        assets_dir = options.pop('assets_dir', None)
        base_url = options.pop('base_url', None)
        
        soup = BeautifulSoup(html, 'lxml')

        # 1. Handle SVGs
        placeholders = {}
        if svg_action == 'strip':
            for svg in soup.find_all('svg'):
                svg.decompose()
        elif svg_action in ['image', 'file']:
            for i, svg in enumerate(soup.find_all('svg')):
                # Fallback fixes for visibility
                if svg.get('fill') == 'currentColor' or not svg.has_attr('fill'):
                    svg['fill'] = '#000000'
                
                # Dimensions
                if not svg.get('width') or not svg.get('height'):
                    viewbox = svg.get('viewbox') or svg.get('viewBox')
                    if viewbox:
                        try:
                            _, _, w, h = map(float, viewbox.replace(',', ' ').split())
                            if not svg.get('width'): svg['width'] = str(int(w))
                            if not svg.get('height'): svg['height'] = str(int(h))
                        except: pass
                    if not svg.get('width'): svg['width'] = "16"
                    if not svg.get('height'): svg['height'] = "16"

                svg_str = str(svg)
                
                if svg_action == 'file' and assets_dir:
                    os.makedirs(assets_dir, exist_ok=True)
                    filename = f"svg_icon_{i}.svg"
                    filepath = os.path.join(assets_dir, filename)
                    with open(filepath, 'w') as f:
                        f.write(svg_str)
                    # Use relative path for Markdown
                    img_tag = soup.new_tag('img', src=os.path.join(os.path.basename(assets_dir), filename), alt="svg icon")
                else:
                    # Default: base64 image
                    encoded = base64.b64encode(svg_str.encode('utf-8')).decode('utf-8')
                    img_tag = soup.new_tag('img', src=f"data:image/svg+xml;base64,{encoded}", alt="svg image")
                
                svg.replace_with(img_tag)
        elif svg_action == 'preserve':
            for i, svg in enumerate(soup.find_all('svg')):
                placeholder = f"MDScraperSVG{i}"
                placeholders[placeholder] = str(svg)
                svg.replace_with(placeholder)

        # 2. Handle standard Images
        if image_action != 'remote':
            from urllib.parse import urljoin
            for i, img in enumerate(soup.find_all('img')):
                src = img.get('src')
                if not src or src.startswith('data:'):
                    continue
                
                # Resolve relative URLs
                if base_url:
                    src = urljoin(base_url, src)
                
                try:
                    if image_action == 'base64':
                        resp = requests.get(src, timeout=10)
                        if resp.status_code == 200:
                            content_type = resp.headers.get('Content-Type', 'image/png')
                            encoded = base64.b64encode(resp.content).decode('utf-8')
                            img['src'] = f"data:{content_type};base64,{encoded}"
                    
                    elif image_action == 'file' and assets_dir:
                        os.makedirs(assets_dir, exist_ok=True)
                        resp = requests.get(src, timeout=10)
                        if resp.status_code == 200:
                            ext = src.split('.')[-1].split('?')[0] or 'png'
                            filename = f"image_{i}.{ext}"
                            filepath = os.path.join(assets_dir, filename)
                            with open(filepath, 'wb') as f:
                                f.write(resp.content)
                            img['src'] = os.path.join(os.path.basename(assets_dir), filename)
                except Exception as e:
                    # Fallback to remote URL on failure
                    continue

        # Default options for GFM-like output
        defaults = {
            'heading_style': 'ATX',
            'bullets': '-',
            'code_language_callback': lambda el: el.get('class', [''])[0].replace('language-', '') if el.get('class') else ''
        }
        
        # Merge with user options
        config = {**defaults, **options}
        markdown = md(str(soup), **config)

        # Restore preserved SVGs
        if svg_action == 'preserve':
            for placeholder, svg_content in placeholders.items():
                markdown = markdown.replace(placeholder, svg_content)

        return markdown

    def extract_nav_links(self, html: Union[str, BeautifulSoup], base_url: str) -> list:
        """
        Extracts navigation links from the HTML to facilitate smart crawling.
        Prioritizes <nav>, <aside>, and sidebar-like elements.
        
        Args:
            html (Union[str, BeautifulSoup]): The raw HTML content or BeautifulSoup object.
            base_url (str): The base URL to resolve relative links.
            
        Returns:
            list: A list of absolute URLs found in the navigation sections.
        """
        if isinstance(html, str):
            soup = BeautifulSoup(html, 'lxml')
        else:
            soup = html

        links = []
        
        # Heuristic: look for nav, aside, or divs with sidebar-like classes
        nav_elements = soup.find_all(['nav', 'aside'])
        nav_elements.extend(soup.find_all('div', class_=re.compile(r'sidebar|menu|nav|toc', re.I)))
        
        # Search scope: found elements, or fallback to body if none found
        search_scope = nav_elements if nav_elements else [soup.body] if soup.body else [soup]

        base_domain = urlparse(base_url).netloc
        seen = set()
        
        for element in search_scope:
            if not element: continue
            for a in element.find_all('a', href=True):
                href = a['href']
                full_url = urljoin(base_url, href)
                parsed = urlparse(full_url)
                
                # Strict Filter: Must be same domain
                if parsed.netloc != base_domain:
                    continue
                
                # Filter: Remove anchors/fragments and queries to avoid dupes
                clean_url = full_url.split('#')[0].split('?')[0]
                
                # Avoid self-ref
                if clean_url == base_url.split('#')[0].split('?')[0]:
                    continue

                if clean_url in seen:
                    continue
                    
                seen.add(clean_url)
                links.append(clean_url)
                
        return links

    def extract_links(self, html: Union[str, BeautifulSoup], base_url: str) -> list:
        """
        Extracts all unique internal links from the HTML.
        
        Args:
            html (Union[str, BeautifulSoup]): The raw HTML content or BeautifulSoup object.
            base_url (str): The base URL to resolve relative links.
            
        Returns:
            list: A list of absolute URLs found on the page.
        """
        if isinstance(html, str):
            soup = BeautifulSoup(html, 'lxml')
        else:
            soup = html

        links = []
        base_domain = urlparse(base_url).netloc
        seen = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            # Skip empty or javascript links
            if not href or href.startswith(('javascript:', 'mailto:', 'tel:')):
                continue

            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            
            # Strict Filter: Must be same domain
            if parsed.netloc != base_domain:
                continue
            
            # Filter: Remove anchors/fragments and queries to avoid dupes
            # Keep query params? Usually crawling wants unique pages. 
            # For KB/Docs, queries might be search params (skip) or versioning (maybe keep).
            # For safety/simplicity, let's strip them for now unless they seem vital.
            clean_url = full_url.split('#')[0].split('?')[0]
            
            # Avoid self-ref
            if clean_url == base_url.split('#')[0].split('?')[0]:
                continue

            if clean_url in seen:
                continue
                
            seen.add(clean_url)
            links.append(clean_url)
            
        return links

    def scrape(self, url: str, dynamic: bool = False, **options) -> dict:
        """
        Orchestrates the full scraping flow: fetch, extract metadata, 
        extract main content, and convert to Markdown.
        
        Args:
            url (str): The URL of the webpage to scrape.
            dynamic (bool): Whether to use Playwright for dynamic rendering.
            **options: Additional options for Markdown conversion.
            
        Returns:
            dict: A dictionary containing 'url', 'metadata', 'markdown', 'raw_html', and 'nav_links'.
        """
        if dynamic:
            html = self.fetch_html_dynamic(url)
        else:
            html = self.fetch_html(url)
            
        # Parse once to avoid redundant parsing
        soup = BeautifulSoup(html, 'lxml')

        # Read-only operations first
        metadata = self.extract_metadata(soup)
        nav_links = self.extract_nav_links(soup, url)
        internal_links = self.extract_links(soup, url)
        
        # Destructive operation last (modifies soup)
        main_html = self.extract_main_content(soup)

        # Convert to markdown
        markdown = self.to_markdown(main_html, **options)
        
        return {
            'url': url,
            'metadata': metadata,
            'markdown': markdown,
            'raw_html': html,
            'nav_links': nav_links,
            'internal_links': internal_links
        }
