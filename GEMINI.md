# Gemini Context File (GEMINI.md)

## Project Overview

**Project Name:** `md-scraper` (also known as `pyscraper-md` or `scraper`)
**Purpose:** A robust, developer-centric Python web scraper designed to transform complex web content into clean, high-fidelity **GitHub Flavored Markdown (GFM)**. It supports both static (requests/BS4) and dynamic (Playwright) scraping.
**Key Features:**
*   **Intelligent Extraction:** Removes boilerplate (ads, navs) to focus on main content.
*   **Format:** Outputs clean Markdown with tables, code blocks, and links.
*   **HTML Output:** Every scrape also returns the cleaned main content as HTML (`result['html']`, content-equivalent of the Markdown) and the full fetched document (`result['raw_html']`), selectable via `--format html` / `--format html-raw` in the CLI, `"format"` in the Web API, and the Output Format dropdown in the Web UI.
*   **Standalone HTML Documents:** `--format html-document` (also `result['html_document']` / `Scraper.wrap_html_document()`) wraps the content HTML in a complete document — DOCTYPE, `<html lang="en">`, UTF-8 charset, viewport, title, author/description metas, `<base href>` + canonical link for http(s) sources, a visible `Source:` link at the top of the page (plain text for local-file sources), and a self-contained stylesheet with dark-mode support — so the file renders in a browser immediately, fully offline. The CLI omits its `--- URL: ---` banner on stdout for this format so the output starts with the DOCTYPE. Already-wrapped input is returned unchanged; `<base>` is omitted when images/SVGs were saved as local files, so their relative paths keep working.
*   **Modes:** CLI, Web UI (Flask), and Python Library.
*   **Dynamic Support:** Handles JS-heavy sites via Playwright.
*   **Remote Offloading:** Can delegate scraping to a remote server (Cloud Run), useful for restricted environments like Termux.
*   **TypeScript Engine:** A faithful port of the Python engine lives in `typescript/` (`pyscraper-md-ts`): same pipeline, result shape, and outputs (static + dynamic, crawling, local-file/MHT input, `file` assets, proxy/UA/delay/retries, all four formats), verified byte-identical against Python in `typescript/tests/side-by-side.test.ts`. Usable as a Bun/Node CLI and library, and from Python via `--engine ts` (CLI), `engine: "ts"` (`/api/scrape`, `/api/download-zip`, web UI dropdown), bridged by `src/md_scraper/ts_engine.py` through the TS CLI's `--json` machine mode. See `typescript/README.md`.

## Performance & Features (v0.2.x)

*   **Proxy & UA Rotation:** Supports proxy server URLs (`--proxy`) and User-Agent headers/random rotation (`--user-agent` / `-ua`).
*   **Retries & Delays:** Exponential backoff retry logic (`--retries`) and configurable inter-request delays (`--delay`).
*   **Heuristic Language Detection:** Automatic programming language detection (`bash`, `json`, `sql`, `javascript`, etc.) for markdown code fences.
*   **Robust Semantic Extraction:** Prioritizes W3C `<main>` and `[role="main"]` containers with anchored regex matching to preserve full document verbosity and eliminate boilerplate/noise.
*   **Link Extraction:** Optimized by moving redundant string operations (`base_url` cleaning) out of recursive loops, resulting in a **2.6x speedup** for large page link parsing.
*   **HTML Output Modes:** `scrape()` returns `html` (cleaned main content as HTML, produced from the same processed DOM as the Markdown, so SVG/image/`strip` handling matches), `html_document` (that content wrapped by `wrap_html_document()` into a standalone, browser-ready document) and `raw_html` (complete fetched document). `Scraper.to_html()` converts an HTML fragment through the same pipeline; `Scraper.content_html()` extracts content HTML from a raw document as a fallback for results from older servers. CLI `--format` (`markdown` / `html` / `html-document` / `html-raw`) and the Web API/ZIP `format` field select the output.
*   **Banner Control:** The CLI's `--- URL: ---` stdout banner is governed by the global `--banner` option (before the subcommand): `default` (stdout, except suppressed for `html-document` and `html-raw` so output starts with the DOCTYPE), `stdout` (always on stdout), `stderr` (always on stderr, keeping stdout clean), or `none` (never printed). Implemented via `_banner_target()` in `cli.py`, resolved once per `scrape` invocation from the group context.
*   **Regex Sanitization:** All Markdown sanitization patterns are pre-compiled at the class level in `MarkdownSanitizer`, reducing instantiation overhead and increasing overall throughput by ~2.2%.
*   **Crawler Efficiency:** The crawler subpath check was refactored to use tuple-based `startswith` checks, providing a ~90% performance boost in path validation logic.

## Architecture & Key Files

The project follows a modular structure managed by **Poetry**.

*   **`src/md_scraper/scraper.py`**: The core `Scraper` class containing all extraction logic (`fetch_html`, `fetch_html_dynamic`, `to_markdown`, `to_html`, `content_html`, `wrap_html_document`). `scrape()` returns `markdown`, `html` (content-equivalent HTML), `html_document` (standalone browser-ready document), and `raw_html` (full document).
*   **`src/md_scraper/cli.py`**: The CLI entry point using `Click`. Defines commands like `scrape`. `--engine python|ts` (default `python`) selects the engine; with `--server` the choice is sent to the server.
*   **`src/md_scraper/web/app.py`**: The Flask application for the Web UI and API endpoints. `/api/scrape` and `/api/download-zip` accept `engine: "python" | "ts"` (default `"python"`); the web UI has an Engine dropdown.
*   **`src/md_scraper/ts_engine.py`**: Bridge to the TypeScript engine — locates the TS CLI (`PYSCRAPER_TS_CMD` env override, else `bun run typescript/src/cli.ts`, else `node typescript/dist/cli.js`) and runs it via its `--json` mode (`scrape_ts` / `crawl_ts` / `wrap_ts` / `content_html_ts`).
*   **`typescript/`**: The TypeScript port (`pyscraper-md-ts`). `src/scraper.ts` (Scraper/Crawler, fetch, extraction), `src/html.ts` (hand-rolled tolerant HTML parser + serializer), `src/markdown.ts` (markdownify-compatible converter), `src/sanitizer.ts`, `src/cli.ts` (CLI + `--json` machine mode), `src/index.ts` (library entry). Dependency-free except optional `playwright` for dynamic mode. Tests in `typescript/tests/` (`bun test`), including a TS-vs-Python side-by-side suite.
*   **`scraper-go.sh`**: An interactive Bash script for batch processing and user-friendly CLI interaction.
*   **`Dockerfile`**: Docker configuration for deploying the Flask app (with Playwright support) to Google Cloud Run.
*   **`pyproject.toml`**: Dependency management and build configuration.

## Setup & Development

### Prerequisites
*   Python 3.13+
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

Or run Gunicorn:
```bash
poetry run gunicorn --bind 0.0.0.0:8080 --workers 1 --threads 8 md_scraper.web.app:app
```

Or run Gunicorn in the background using `nohup`:
```bash
nohup poetry run gunicorn --bind 0.0.0.0:8080 --workers 1 --threads 8 md_scraper.web.app:app > output.log 2>&1 &
```

### 3. Docker
```bash
# Build the image
docker build -t scraper .

# Run the container
docker run -p 8080:8080 --name scraper_container scraper
```
> **Note:** Ensure port 8080 is free. If not, map to another port (e.g., `-p 8081:8080`) or kill the process occupying it.

### 4. TypeScript Engine
```bash
cd typescript

# Bun (no build step) — primary
bun run src/cli.ts scrape https://example.com
bun run src/cli.ts scrape http://quotes.toscrape.com/js/ --dynamic

# Node (build first)
npm install && npm run build
node dist/cli.js scrape https://example.com

# From Python instead of the Python engine
PYTHONPATH=src python -m md_scraper.cli scrape https://example.com --engine ts
# (or, once installed: scraper scrape https://example.com --engine ts)

# From the web app: POST /api/scrape with {"engine": "ts"}, or pick
# "TypeScript" in the web UI's Engine dropdown.
```
Dynamic scraping needs Playwright + Chromium (`bun install` pulls the
optional `playwright` dep); the browser path comes from `CHROMIUM_PATH`
when set, the proxy from `--proxy` / `PYSCRAPER_PROXY` env, and
`ignore_https_errors` is a per-scrape option (default `false`). On a
VM where Chromium can only reach loopback, point the proxy at a
loopback relay, e.g. `PYSCRAPER_PROXY=http://127.0.0.1:8891`.

## Testing

The project uses `pytest` for unit and integration testing.

```bash
# Run all tests
poetry run pytest

# Run with coverage report
poetry run pytest --cov=md_scraper

# TypeScript engine tests (Bun) — includes the TS-vs-Python side-by-side suite
cd typescript && bun test
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
