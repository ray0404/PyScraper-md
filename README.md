# Markdown Scraper 🚀

[![Python Version](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)
[![Poetry](https://img.shields.io/badge/package%20manager-poetry-blueviolet.svg)](https://python-poetry.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

A robust, developer-centric Python web scraper designed to transform complex web content into clean, high-fidelity **GitHub Flavored Markdown (GFM)**. 

Built for archival, LLM context gathering, research, and technical documentation. It handles everything from static blogs to complex, JavaScript-heavy Single Page Applications (SPAs).

## ✨ Key Features

-   **Intelligent Extraction:** Heuristically identifies main content, stripping navigation, ads, and footers.
-   **Performance-First:** Optimized core loops and pre-compiled regex patterns ensure high throughput (2.6x faster link extraction).
-   **Recursive Crawling:** Spiders through links to a specified depth and page limit.
-   **High-Fidelity GFM:** Preserves tables, code blocks (with language detection), and rich text formatting.
-   **Asset Management:**
    -   **Images:** Keep as remote URLs, convert to Base64, or download locally.
    -   **SVGs:** Render as images, preserve code, strip, or save to file.
-   **Local & Remote Sources:** Scrape live URLs or local HTML files.
-   **Dual Engines:** 
    -   **Static:** Fast `requests` + `BeautifulSoup4` for simple sites.
    -   **Dynamic:** Full `Playwright` integration for JS-heavy sites.
-   **Multiple Interfaces:** 
    -   **CLI:** Powerful terminal tool with rich flags.
    -   **Web UI:** Flask-based interface for browser workflows.
    -   **Library:** Clean Python API for integration.
-   **Remote Offloading:** Delegate heavy lifting (Playwright) to a remote Cloud Run instance (ideal for Termux/mobile).

## 🛠️ Tech Stack

-   **Core:** Python 3.13+
-   **Parsing:** `BeautifulSoup4`, `lxml`
-   **Conversion:** `markdownify`
-   **Browser Automation:** `Playwright`
-   **CLI:** `click`
-   **Web:** `Flask`, `gunicorn`, `Pico.css`
-   **Testing:** `pytest` ecosystem

## 🚀 Getting Started

### Prerequisites

-   **Python 3.13+**
-   **Poetry** (Recommended) or `pip`
-   **Playwright Browsers** (for dynamic scraping)

### Installation

#### 1. Clone & Install Dependencies

```bash
git clone https://github.com/yourusername/md-scraper.git
cd md-scraper
poetry install
```

#### 2. Install Playwright Browsers (Optional)

Required only if you plan to use `--dynamic` mode locally:

```bash
poetry run playwright install chromium
```

#### 3. Global CLI Access (Optional)

```bash
pip install --editable .
```

### Termux / Android Setup

If running on Android via Termux, local Playwright is **not supported**. You have two options:
1.  **Remote Mode:** Use the `--server` flag to offload processing to a deployed instance.
2.  **Static Mode:** Use the default static scraper (no JS execution).
3.  **Chromium (Experimental):** Install `pkg install chromium` and set `CHROMIUM_PATH`.

## 📖 Usage Guide

### Command Line Interface (CLI)

The `scraper` command is your primary tool.

#### Basic Scraping

```bash
# Scrape a single URL to stdout
scraper scrape https://example.com/article

# Save to file
scraper scrape https://example.com/article -o article.md

# Scrape a local file
scraper scrape path/to/local/file.html -o output.md
```

#### Output Formats (Markdown & HTML)

By default the scraper outputs clean Markdown. Use `--format` to get HTML instead:

```bash
# Cleaned main content as HTML — the content-equivalent of the Markdown
# output (same extraction, same SVG/image/strip handling), as an HTML fragment
scraper scrape https://example.com/article --format html -o article.html

# Full fetched document, untouched (includes nav, footer, scripts, etc.)
scraper scrape https://example.com/article --format html-raw -o article-full.html

# Standalone document: the cleaned content wrapped in a complete HTML
# document (DOCTYPE, charset, viewport, title, self-contained stylesheet).
# Open the file in any browser and it renders immediately, offline.
scraper scrape https://example.com/article --format html-document -o article.html
```

| Format | Description | File extension |
|--------|-------------|----------------|
| `markdown` (default) | Cleaned main content as GitHub Flavored Markdown. | `.md` |
| `html` | Cleaned main content as HTML — same content as the Markdown output. | `.html` |
| `html-document` | That same content wrapped in a complete standalone HTML document: DOCTYPE, `<html lang="en">`, UTF-8 charset, viewport, title, `<base href>` + canonical link (for http(s) sources, so relative links/images keep working), a visible `Source:` link at the top of the page, and an inline stylesheet — no external requests, renders fully offline. Already-wrapped input is returned unchanged. When printed to stdout, the CLI omits its `--- URL: ---` banner for this format so the output starts with the DOCTYPE (a banner before it would trigger quirks mode). | `.html` |
| `html-raw` | The complete fetched HTML document, untouched. | `.html` |

The same formats are available in the Python library (`result['html']`, `result['html_document']` and `result['raw_html']`), the Web API (`/api/scrape` returns all keys; `/api/download-zip` accepts `"format"`), and the Web UI (Output Format dropdown).

#### Asset Handling (Images & SVGs)

Control how assets are processed:

```bash
# Download images and SVGs to an 'assets' folder
scraper scrape https://example.com \
  --image-action file \
  --svg-action file \
  --assets-dir ./my-assets \
  -o ./output/page.md

# Convert images to Base64 (inline)
scraper scrape https://example.com --image-action base64

# Strip all images and SVGs
scraper scrape https://example.com --strip img --svg-action strip
```

| Flag | Options | Description |
|------|---------|-------------|
| `--image-action` | `remote` (default), `base64`, `file` | How to handle `<img>` tags. |
| `--svg-action` | `image` (default), `preserve`, `strip`, `file` | How to handle inline `<svg>` tags. |
| `--assets-dir` | `<path>` | Directory to save assets when `file` action is used. |

#### Recursive Crawling

Crawl a documentation site or blog:

```bash
scraper scrape https://tailscale.com/kb/ \
  --crawl \
  --depth 2 \
  --max-pages 20 \
  --only-subpaths \
  -o ./tailscale-docs
```

-   `--crawl`: Enable crawling.
-   `--depth <int>`: How deep to follow links (default: 3).
-   `--only-subpaths`: Only follow links that are children of the starting URL.

#### Dynamic Sites & Remote Offloading

For Single Page Applications (React, Vue, etc.):

```bash
# Local Dynamic (requires Playwright)
scraper scrape https://spa-site.com --dynamic

# Remote Offloading (Recommended for Termux/Low-resource)
scraper scrape https://spa-site.com \
  --server https://scraper-751660269987.us-central1.run.app
```

### Interactive Batch Mode

The `scraper-go.sh` script provides a user-friendly wizard for batch jobs.

```bash
./scraper-go.sh
```

**Features:**
-   Enter URLs manually or provide a `.txt` list.
-   Auto-detects page titles for filenames.
-   Organizes output into folders.
-   Defaults to remote server for reliability.

### Web Interface

Run the lightweight Flask UI for development:

```bash
poetry run python src/md_scraper/web/app.py
```

Alternatively, run a production-ready Gunicorn server:

```bash
poetry run gunicorn --bind 0.0.0.0:8080 --workers 1 --threads 8 md_scraper.web.app:app
```

To run Gunicorn in the background (detached mode) using `nohup`:

```bash
nohup poetry run gunicorn --bind 0.0.0.0:8080 --workers 1 --threads 8 md_scraper.web.app:app > output.log 2>&1 &
```

Access the UI at `http://127.0.0.1:8080`.

### Python Library Usage

Integrate into your own scripts:

```python
from md_scraper.scraper import Scraper

# Initialize
scraper = Scraper()

# Scrape
result = scraper.scrape(
    "https://example.com",
    dynamic=True,
    image_action='base64'
)

# Access Data
print(f"Title: {result['metadata']['title']}")
print(f"Markdown:\n{result['markdown']}")

# HTML outputs (same scrape, no extra request):
# - 'html': cleaned main content as HTML, content-equivalent of 'markdown'
# - 'html_document': that content wrapped in a complete standalone
#   HTML document, ready to open in a browser
# - 'raw_html': the complete fetched document, untouched
print(f"HTML:\n{result['html']}")
print(f"Raw HTML length: {len(result['raw_html'])}")

# Wrap any content HTML in a standalone document yourself:
from md_scraper.scraper import Scraper
doc = Scraper.wrap_html_document(result['html'], title=result['metadata']['title'],
                                 source_url=result['url'], metadata=result['metadata'])

# Convert an HTML fragment directly (no fetching, no main extraction):
from md_scraper.scraper import Scraper
html_fragment = Scraper().to_html("<h1>Title</h1><p>Text.</p>")
```

## 🐳 Docker Support

Isolate the environment with Docker.

```bash
# Build
docker build -t scraper .

# Run
docker run -p 8080:8080 scraper
```

## 🧪 Testing

Run the test suite to ensure reliability.

```bash
# Run all tests
poetry run pytest

# Check coverage
poetry run pytest --cov=md_scraper
```

## 🏗️ Architecture

```
src/md_scraper/
├── cli.py          # Command-line entry point
├── scraper.py      # Core extraction & cleaning logic
├── crawler.py      # Recursive crawling engine
├── utils.py        # Helper functions (sanitization, headers)
└── web/
    ├── app.py
    └── templates/
```

## ☁️ Deployment

The project is optimized for **Google Cloud Run**.

**Live Demo:** [https://scraper-751660269987.us-central1.run.app](https://scraper-751660269987.us-central1.run.app)

**Deploy Command:**
```bash
gcloud run deploy scraper \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

## 🤝 Contributing

1.  Fork the repository.
2.  Create a feature branch (`git checkout -b feature/amazing-feature`).
3.  Commit changes (`git commit -m 'Add amazing feature'`).
4.  Push to branch (`git push origin feature/amazing-feature`).
5.  Open a Pull Request.

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.