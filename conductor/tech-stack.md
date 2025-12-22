# Technology Stack - Markdown Scraper

## Backend & Scraping
- **Language:** Python 3.10+
- **Static Scraping:** `BeautifulSoup4` + `requests` for efficient processing of standard HTML pages.
- **Dynamic Scraping:** `Playwright` for rendering JavaScript-heavy websites and ensuring full content capture.
- **HTML to Markdown:** `markdownify` for flexible and customizable conversion of DOM elements to GFM.

## User Interfaces
- **CLI Framework:** `Click` for building a robust, nested, and well-documented command-line interface.
- **Web Framework:** `Flask` for a lightweight web UI to handle URL submissions and previews.

## Infrastructure & Tooling
- **Dependency Management:** `Poetry` (using `pyproject.toml`) for deterministic builds, dependency isolation, and simplified packaging.
- **Testing:** `pytest` for unit and integration testing of scraping and conversion logic.