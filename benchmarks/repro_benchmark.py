import time
import os
import sys

# Ensure we can import from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from md_scraper.scraper import Scraper
from bs4 import BeautifulSoup

def benchmark():
    scraper = Scraper()

    # Large HTML content to make parsing time significant
    with open('benchmark.html', 'w') as f:
        f.write("<html><body>")
        for i in range(10000):
            f.write(f"<div><p>This is paragraph {i}. <a href='link{i}'>Link</a></p><svg><rect width='10' height='10'/></svg></div>")
        f.write("</body></html>")

    with open('benchmark.html', 'r') as f:
        html = f.read()

    print(f"HTML size: {len(html) / 1024 / 1024:.2f} MB")

    start_total = time.time()

    # Emulate what scrape() does
    start_parse1 = time.time()
    soup = BeautifulSoup(html, 'lxml')
    end_parse1 = time.time()
    print(f"First parse time: {end_parse1 - start_parse1:.4f}s")

    # Metadata extraction (lightweight)
    scraper.extract_metadata(soup)

    # Link extraction
    scraper.extract_links(soup, "http://example.com")

    # Main content extraction (destructive)
    start_extract = time.time()
    main_html = scraper.extract_main_content(soup)
    end_extract = time.time()
    print(f"Extract main content time: {end_extract - start_extract:.4f}s")

    # To markdown (currently parses again)
    start_to_md = time.time()
    markdown = scraper.to_markdown(main_html)
    end_to_md = time.time()
    print(f"To markdown time (including re-parse): {end_to_md - start_to_md:.4f}s")

    end_total = time.time()
    print(f"Total time: {end_total - start_total:.4f}s")

    os.remove('benchmark.html')

if __name__ == "__main__":
    benchmark()
