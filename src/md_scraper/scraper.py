import requests
import json
from bs4 import BeautifulSoup
from markdownify import markdownify as md

class Scraper:
    """
    A web scraper that converts HTML content from a URL into clean Markdown.
    
    It handles fetching HTML, extracting metadata, identifying main content 
    using heuristics, and converting the resulting DOM to GitHub Flavored Markdown.
    """

    def fetch_html(self, url: str) -> str:
        """
        Fetches the raw HTML content from a given URL.
        
        Args:
            url (str): The URL of the webpage to fetch.
            
        Returns:
            str: The raw HTML content of the page.
            
        Raises:
            requests.exceptions.HTTPError: If the request returned an unsuccessful status code.
        """
        response = requests.get(url)
        response.raise_for_status()
        return response.text

    def extract_main_content(self, html: str) -> str:
        """
        Extracts the primary content area from an HTML string, removing boilerplate.
        
        It attempts to find tags like <main>, <article>, or common content class names.
        Non-content elements such as <nav>, <footer>, <script>, and <style> are removed.
        
        Args:
            html (str): The raw HTML content.
            
        Returns:
            str: The HTML string containing only the main content area.
        """
        soup = BeautifulSoup(html, 'lxml')
        
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

    def extract_metadata(self, html: str) -> dict:
        """
        Extracts metadata (title, author, date, etc.) from an HTML string.
        
        Supports JSON-LD, OpenGraph, and standard meta tags.
        
        Args:
            html (str): The raw HTML content.
            
        Returns:
            dict: A dictionary containing extracted metadata fields.
        """
        soup = BeautifulSoup(html, 'lxml')
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
            
        Returns:
            str: The resulting Markdown string.
        """
        # Default options for GFM-like output
        defaults = {
            'heading_style': 'ATX',
            'bullets': '-',
            'code_language_callback': lambda el: el.get('class', [''])[0].replace('language-', '') if el.get('class') else ''
        }
        # Merge with user options
        config = {**defaults, **options}
        return md(html, **config)

    def scrape(self, url: str, **options) -> dict:
        """
        Orchestrates the full scraping flow: fetch, extract metadata, 
        extract main content, and convert to Markdown.
        
        Args:
            url (str): The URL of the webpage to scrape.
            **options: Additional options for Markdown conversion.
            
        Returns:
            dict: A dictionary containing 'url', 'metadata', 'markdown', and 'raw_html'.
        """
        html = self.fetch_html(url)
        metadata = self.extract_metadata(html)
        main_html = self.extract_main_content(html)
        markdown = self.to_markdown(main_html, **options)
        
        return {
            'url': url,
            'metadata': metadata,
            'markdown': markdown,
            'raw_html': html
        }
