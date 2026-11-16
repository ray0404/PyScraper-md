"""Helper for the side-by-side tests: scrape one target with the Python
engine and print the result JSON. Usage: py_scrape.py <src-dir> <url> [opts-json]."""
import sys
import json

sys.path.insert(0, sys.argv[1])
from md_scraper.scraper import Scraper

url = sys.argv[2]
opts = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
with Scraper() as scraper:
    print(json.dumps(scraper.scrape(url, **opts)))
