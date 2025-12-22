import requests
import json
from bs4 import BeautifulSoup

class Scraper:
    def fetch_html(self, url: str) -> str:
        response = requests.get(url)
        response.raise_for_status()
        return response.text

    def extract_main_content(self, html: str) -> str:
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
