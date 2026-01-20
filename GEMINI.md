# Gemini Context File (GEMINI.md)

## Project Overview

**Project Name:** `md-scraper` (also known as `pyscraper-md` or `scraper`)
**Purpose:** A robust, developer-centric Python web scraper designed to transform complex web content into clean, high-fidelity **GitHub Flavored Markdown (GFM)**. It supports both static (requests/BS4) and dynamic (Playwright) scraping.
**Key Features:**
*   **Intelligent Extraction:** Removes boilerplate (ads, navs) to focus on main content.
*   **Format:** Outputs clean Markdown with tables, code blocks, and links.
*   **Modes:** CLI, Web UI (Flask), and Python Library.
*   **Dynamic Support:** Handles JS-heavy sites via Playwright.
*   **Remote Offloading:** Can delegate scraping to a remote server (Cloud Run), useful for restricted environments like Termux.

## Architecture & Key Files

The project follows a modular structure managed by **Poetry**.

*   **`src/md_scraper/scraper.py`**: The core `Scraper` class containing all extraction logic (`fetch_html`, `fetch_html_dynamic`, `to_markdown`).
*   **`src/md_scraper/cli.py`**: The CLI entry point using `Click`. Defines commands like `scrape`.
*   **`src/md_scraper/web/app.py`**: The Flask application for the Web UI and API endpoints.
*   **`scraper-go.sh`**: An interactive Bash script for batch processing and user-friendly CLI interaction.
*   **`Dockerfile`**: Docker configuration for deploying the Flask app (with Playwright support) to Google Cloud Run.
*   **`pyproject.toml`**: Dependency management and build configuration.

## Setup & Development

### Prerequisites
*   Python 3.12+
*   **Poetry** (Package Manager)

### Installation
```bash
# Install dependencies
poetry install

# Install Playwright browsers (if using dynamic scraping locally)
poetry run playwright install chromium
```

## Building & Running

### 1. Command Line Interface (CLI)
The CLI is exposed as `scraper` (if installed) or `poetry run scraper`.

```bash
# Scrape a static URL
poetry run scraper scrape https://example.com

# Scrape a dynamic URL (requires Playwright)
poetry run scraper scrape https://example.com --dynamic

# Scrape using a remote server (offload processing)
poetry run scraper scrape https://example.com --server https://scraper-751660269987.us-central1.run.app

# Batch processing
./scraper-go.sh
```

### 2. Web Interface
Start the Flask development server:
```bash
poetry run python src/md_scraper/web/app.py
# Access at http://127.0.0.1:8080
```

### 3. Docker
```bash
# Build the image
docker build -t scraper .

# Run the container
docker run -p 8080:8080 scraper
```

## Testing

The project uses `pytest` for unit and integration testing.

```bash
# Run all tests
poetry run pytest

# Run with coverage report
poetry run pytest --cov=md_scraper
```
**Conventions:**
*   Unit tests mock network and browser calls.
*   CLI tests use `click.testing.CliRunner`.
*   Web tests use Flask's test client.

## Deployment

The application is deployed on **Google Cloud Run**.
*   **Service Name:** `scraper`
*   **Region:** `us-central1`
*   **Command:** `gcloud run deploy scraper --source . --region us-central1 --allow-unauthenticated`

## AI Agent Instructions

*   **Context Awareness:** Always check `GEMINI.md` and `README.md` before starting tasks.
*   **Spec-Driven:** Understand requirements fully before implementation.
*   **Testing:** **CRITICAL**. Every functional change must be accompanied by tests. Verify changes using `poetry run pytest`.
*   **Style:** Adhere to Google-style docstrings and Python type hints.
*   **Environment:** Be aware of environment differences (e.g., Termux vs. standard Linux). When in doubt, prefer the `scraper-go.sh` or remote server approach for complex environments.
