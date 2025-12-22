import requests

class Scraper:
    def fetch_html(self, url: str) -> str:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
