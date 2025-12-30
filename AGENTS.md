# Agent Guide: Markdown Scraper

This document provides specialized context for AI agents (like Google Jules) to facilitate autonomous development, testing, and maintenance of this repository.

## 🤖 AI Agent Instructions

- **Context First:** Always read `GEMINI.md` and `README.md` before making changes.
- **Spec-Driven Development:** This project uses a spec-driven approach. When adding features, define the requirements in a temporary spec or update `GEMINI.md` logic first.
- **Verify with Tests:** Every functional change MUST be accompanied by a corresponding unit or integration test in the `tests/` directory.
- **Adhere to Style:** Use Google-style docstrings and Python type hints.

## 🛠 Project Blueprint

### Core Architecture
- **`md_scraper.scraper.Scraper`**: The central class. 
    - `fetch_html`: Static fetching using `requests`.
    - `fetch_html_dynamic`: Dynamic fetching using `Playwright` (headless browser).
    - `extract_main_content`: Heuristic-based boilerplate removal.
    - `extract_metadata`: JSON-LD, OG, and meta tag extraction.
    - `to_markdown`: HTML to GFM conversion using `markdownify`.
    - `scrape`: Unified entry point.

### Entry Points
- **CLI**: `src/md_scraper/cli.py` (powered by `Click`).
- **Web**: `src/md_scraper/web/app.py` (powered by `Flask`).

## 🚀 Key Commands for Agents

### Environment Setup
```bash
poetry install
```

### Validation
```bash
# Run full suite
poetry run pytest

# Check coverage
poetry run pytest --cov=md_scraper
```

### Execution (Testing logic manually)
```bash
# Test CLI (Static)
scraper scrape https://example.com

# Test CLI (Remote/Dynamic - Recommended for Termux)
scraper scrape https://example.com --server https://scraper-751660269987.us-central1.run.app

# Test Interactive Script
./scraper-go.sh

# Test Web (start in background if needed)
poetry run python src/md_scraper/web/app.py &
```

## 🧪 Testing Protocol

- **Unit Tests:** Located in `tests/test_scraper.py` and `tests/test_dynamic_scraper.py`. Mock all network and browser calls.
- **Integration Tests:**
    - CLI: `tests/test_cli.py` using `click.testing.CliRunner`.
    - Web: `tests/test_web_app.py` using Flask's test client.
- **Coverage Goal:** >90%.

## 📦 Dependency Management
We use **Poetry**.
- Add a package: `poetry add <pkg>`
- Update lock: `poetry lock --no-update`

## ⚠️ Environment Specifics
- **Termux Support:** The codebase supports Android/Termux via the `CHROMIUM_PATH` environment variable and `--no-sandbox` flags in `Playwright` configuration. If running in a restricted environment, always check for system binary compatibility.

## ☁️ Deployment Info

- **Platform:** Google Cloud Run
- **Service Name:** `scraper`
- **Region:** `us-central1`
- **URL:** `https://scraper-751660269987.us-central1.run.app`
- **Command:** `gcloud run deploy scraper --source . --region us-central1 --allow-unauthenticated`
