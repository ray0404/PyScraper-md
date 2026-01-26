# Agent Operational Handbook: Markdown Scraper

This document serves as the authoritative guide for AI agents (including Google Jules) operating within the `md-scraper` repository. It establishes strict protocols, architectural understanding, and development standards to ensure high-velocity, high-quality contributions.

## 1. Prime Directives & Operational Protocols

### 1.1 Contextual Grounding
*   **Primary Truth:** You **MUST** treat `GEMINI.md` and `README.md` as the immutable sources of truth for project context, architectural decisions, and technical specifications.
*   **Reference First:** Before generating a single line of code or a plan, read these documents to align with existing patterns.
*   **Update Responsibility:** If you implement a significant architectural change, you are responsible for updating `GEMINI.md` to reflect the new state.

### 1.2 The "No Broken Windows" Policy
*   **Test-Driven Mindset:** No functional change is complete without a corresponding test.
    *   **New Features:** Must include unit tests covering happy paths and edge cases.
    *   **Bug Fixes:** Must include a reproduction test case that fails before the fix and passes after.
*   **Linting & Types:** Code must be statically correct. Respect existing typing conventions (Type Hints are mandatory for new code).

### 1.3 Environment Awareness
*   **Cross-Platform Reality:** This project runs on Linux servers (Cloud Run), local Dev machines (Mac/Linux/Windows), and restricted environments like **Android/Termux**.
*   **Playwright Caution:** Dynamic scraping relies on Playwright. Always consider:
    *   Is the browser binary available? (Check `CHROMIUM_PATH` for Termux).
    *   Are we running headless? (Default: Yes).
    *   Are we using `--no-sandbox`? (Critical for containerized/root environments).

---

## 2. Architectural Deep Dive

The application is structured as a modular Python package (`md_scraper`) managed by Poetry, with three distinct interface layers.

### 2.1 Core Logic (`src/md_scraper/scraper.py`)
The `Scraper` class is the heart of the application. Its pipeline is strictly sequential:
1.  **Ingestion:** Receives a URL and configuration flags (dynamic mode, stripping options).
2.  **Fetching Strategy:**
    *   **Static:** Uses `requests` + `User-Agent` rotation. Fast, low overhead.
    *   **Dynamic:** Spins up a `Playwright` context. Renders JS, waits for network idle or specific selectors.
3.  **Content Cleaning:**
    *   Uses `BeautifulSoup4` to remove "noise" tags (`<script>`, `<style>`, `<nav>`, `<footer>`, `<aside>`).
    *   Applies heuristic filtering to isolate the "main article" content.
4.  **Metadata Extraction:**
    *   Parses JSON-LD (Schema.org) blocks.
    *   Extracts OpenGraph (`og:`) and Twitter Card tags.
5.  **Transformation:**
    *   Converts the cleaned HTML DOM into GitHub Flavored Markdown (GFM) using `markdownify`.
    *   Handles relative-to-absolute URL conversion for images and links.
6.  **Link Extraction:**
    *   `extract_links`: Extracts all same-domain links for the Crawler.

### 2.2 Crawler Engine (`src/md_scraper/crawler.py`)
The `Crawler` class manages the recursive scraping process:
*   **Queue Management:** Implements Breadth-First Search (BFS).
*   **State Tracking:** Tracks visited URLs and current depth.
*   **Filtering:** Enforces domain confinement (`same_domain=True`) and optional subpath restriction (`only_subpaths=True`).

### 2.3 Interface Layers
*   **CLI (`src/md_scraper/cli.py`):**
    *   Built with `Click`.
    *   Handles argument parsing, file I/O, and batch processing logic.
    *   **Crawling:** Exposes flags `--crawl`, `--depth`, `--only-subpaths`, and `--max-pages`.
    *   **Remote Offloading:** Logic exists to serialize CLI arguments into a JSON payload and POST them to the Cloud Run instance.
*   **Web/API (`src/md_scraper/web/app.py`):**
    *   Built with `Flask`.
    *   **UI:** Renders Jinja2 templates (`src/md_scraper/web/templates/`) styled with `Pico.css`.
    *   **API (`/api/scrape`):** Accepts JSON payloads (including crawling params), executes `Scraper`/`Crawler`, and returns JSON responses.

### 2.4 Deployment Architecture
*   **Containerization:** `Dockerfile` is optimized for Cloud Run.
    *   Base: `python:3.12-slim`.
    *   Browsers: Installs Playwright dependencies + Chromium.
*   **Orchestration:** Deployed via `gcloud run`.
    *   Scaling: Autoscaling 0-N instances.
    *   Concurrency: Handled by `gunicorn` with multiple threads.

---

## 3. Development Workflow

### 3.1 Task Execution Cycle
1.  **Analyze:** Read the user request. Search `src/` to identify impacted components.
2.  **Plan:** Formulate a step-by-step plan. If complex, create a temporary specification file.
3.  **Test (Red):** Write a failing test in `tests/` that asserts the desired behavior.
4.  **Implement (Green):** Write the minimal code necessary to pass the test.
5.  **Refactor:** Optimize the code while ensuring tests stay green.
6.  **Verify:** Run the full suite (`poetry run pytest`).

### 3.2 Dependency Management (Poetry)
*   **Add Runtime Dependency:** `poetry add <package_name>`
*   **Add Dev Dependency:** `poetry add --group dev <package_name>`
*   **Sync Environment:** `poetry install`
*   **Lockfile:** Never manually edit `poetry.lock`. Let Poetry manage it.

### 3.3 Testing Standards (`pytest`)
*   **Location:** All tests reside in `tests/`.
*   **Mocking:**
    *   **Network Calls:** NEVER allow real HTTP requests during unit tests. Use `requests_mock` or `unittest.mock.patch`.
    *   **Playwright:** Mock the `sync_playwright` context manager to avoid spawning real browsers during basic unit tests.
*   **Fixtures:** Use `conftest.py` for shared fixtures (e.g., sample HTML content, mock scraper instances).

---

## 4. Key File Reference

| File Path | Description |
| :--- | :--- |
| `GEMINI.md` | **Context Master.** The high-level map of the project. |
| `pyproject.toml` | Build system, dependencies, and tool configuration. |
| `src/md_scraper/scraper.py` | **Core Logic.** HTML fetching, cleaning, and conversion. |
| `src/md_scraper/crawler.py` | **Crawler Logic.** Recursive link following and queue. |
| `src/md_scraper/cli.py` | CLI command definitions and argument handling. |
| `src/md_scraper/web/app.py` | Flask web server and API routes. |
| `tests/test_web_crawl.py` | Integration tests for API crawling parameters. |
| `tests/` | Test suite. Mirroring the `src` structure is encouraged. |
| `scraper-go.sh` | Bash script for batch operations and remote scraping. |

---

## 5. Troubleshooting & Edge Cases

*   **Dynamic Scraping Timeouts:** If Playwright times out, check if the site blocks headless browsers. Attempt to adjust `User-Agent` or add random delays.
*   **Termux Failures:** If scraping fails on Android, verify `CHROMIUM_PATH` is set and points to the system's chromium binary, as Playwright cannot manage binaries in Termux.
*   **Cloud Run Memory:** Playwright can be memory hungry. If the container crashes, check memory limits in `gcloud` config.

## 6. Future Roadmap Guidelines
*   **Modular Parsers:** Future refactors should split `Scraper` into specific parsers (e.g., `MediumParser`, `SubstackParser`) for better site-specific handling.
*   **Async Support:** Transitioning core logic to `asyncio` / `aiohttp` would improve throughput for batch operations.

**End of Handbook.**
