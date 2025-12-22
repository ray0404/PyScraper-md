# Markdown Scraper 🚀

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Poetry](https://img.shields.io/badge/package%20manager-poetry-blueviolet.svg)](https://python-poetry.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A robust, developer-centric Python web scraper designed to transform complex web content into clean, high-fidelity **GitHub Flavored Markdown (GFM)**. Perfect for archival, research, LLM context gathering, and technical documentation.

## ✨ Key Features

-   **Intelligent Extraction:** Uses heuristics to identify the main content area (article, main, etc.) while stripping away navigation, ads, and footers.
-   **High-Fidelity GFM:** Produces clean Markdown including tables, code blocks (with language detection), and links.
-   **Static & Dynamic Support:** 
    -   Fast static scraping using `BeautifulSoup4` & `requests`.
    -   Robust dynamic scraping for JS-heavy SPAs using `Playwright`.
-   **Metadata Extraction:** Automatically captures title, author, date, and descriptions from JSON-LD, OpenGraph, and standard meta tags.
-   **Multiple Interfaces:** 
    -   **CLI:** Powerful command-line tool for terminal workflows.
    -   **Web UI:** Lightweight Flask-based interface for browser-based scraping.
    -   **Python Library:** Clean API for integration into your own Python projects.
-   **Highly Configurable:** Toggle image stripping, link removal, and more.

## 🛠️ Tech Stack

-   **Backend:** Python 3.12+
-   **Scraping:** `BeautifulSoup4`, `Playwright`, `requests`, `lxml`
-   **Conversion:** `markdownify`
-   **CLI:** `Click`
-   **Web UI:** `Flask` + `Pico.css`
-   **Testing:** `pytest`, `pytest-cov`, `pytest-flask`

## 🚀 Getting Started

### Prerequisites

-   [Poetry](https://python-poetry.org/docs/#installation) installed on your system.

### Installation

```bash
git clone https://github.com/yourusername/md-scraper.git
cd md-scraper
poetry install
```

**Note for Termux users:**
If developing on Android/Termux, install Chromium via `pkg install chromium` and set the `CHROMIUM_PATH` environment variable.

### Usage

#### Command Line Interface (CLI)

The CLI is available via the `scraper` command:

```bash
# Scrape a static page to stdout
poetry run scraper scrape https://example.com/article

# Scrape and save to a file
poetry run scraper scrape https://example.com/article -o my_article.md

# Scrape a dynamic (JS-heavy) site
poetry run scraper scrape https://react-site.com --dynamic

# Strip specific tags (e.g., remove all images and links)
poetry run scraper scrape https://example.com -s img -s a
```

#### Web Interface

Start the local development server:

```bash
poetry run python src/md_scraper/web/app.py
```
Open your browser and navigate to `http://127.0.0.1:5000`.

#### As a Python Library

```python
from md_scraper.scraper import Scraper

scraper = Scraper()
result = scraper.scrape("https://example.com/blog-post", dynamic=False)

print(result['metadata']['title'])
print(result['markdown'])
```

## 🧪 Testing

We maintain a comprehensive test suite with high coverage.

```bash
# Run all tests
poetry run pytest

# Run with coverage report
poetry run pytest --cov=md_scraper
```

## 🏗️ Architecture

-   `src/md_scraper/scraper.py`: Core `Scraper` class logic.
-   `src/md_scraper/cli.py`: CLI entry point and command definitions.
-   `src/md_scraper/web/`: Flask application and Jinja2 templates.
-   `tests/`: Unit and integration tests.

## 🤝 Contributing

Contributions are welcome! Please ensure you:
1.  Follow the existing code style (Google-style docstrings).
2.  Add tests for any new features or bug fixes.
3.  Ensure the full test suite passes.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.