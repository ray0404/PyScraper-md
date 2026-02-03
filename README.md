# Markdown Scraper 🚀

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Poetry](https://img.shields.io/badge/package%20manager-poetry-blueviolet.svg)](https://python-poetry.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

A robust, developer-centric Python web scraper designed to transform complex web content into clean, high-fidelity **GitHub Flavored Markdown (GFM)**. 

Built for archival, LLM context gathering, research, and technical documentation. It handles everything from static blogs to complex, JavaScript-heavy Single Page Applications (SPAs).

## ✨ Key Features

-   **Intelligent Extraction:** Heuristically identifies main content, stripping navigation, ads, and footers.
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

-   **Core:** Python 3.12+
-   **Parsing:** `BeautifulSoup4`, `lxml`
-   **Conversion:** `markdownify`
-   **Browser Automation:** `Playwright`
-   **CLI:** `click`
-   **Web:** `Flask`, `gunicorn`, `Pico.css`
-   **Testing:** `pytest` ecosystem

## 🚀 Getting Started

### Prerequisites

-   **Python 3.12+**
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

Run the lightweight Flask UI:

```bash
poetry run python src/md_scraper/web/app.py
```
Access at `http://127.0.0.1:8080`.

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