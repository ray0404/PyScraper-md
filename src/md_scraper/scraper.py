import requests
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
