# pyscraper-md-ts — TypeScript Engine

A faithful TypeScript port of the Python `md-scraper` engine
(`src/md_scraper/`), rebuilt from the Python source (the spec) and the
TypeScript engine that ships in the Muse Space for this project. It is
**not a byte copy** of the Space engine — fullstack artifacts do not
expose their source for export — but it reproduces the same pipeline,
the same result shape, and the same outputs, verified field-by-field
against the Python engine (see `tests/side-by-side.test.ts`).

## What it does

Fetch → parse → metadata (JSON-LD / OpenGraph / meta / title) → link
extraction → main-content extraction (same selector heuristics as
Python) → SVG / image / strip handling → GitHub Flavored Markdown +
cleaned HTML → standalone-document wrap (same CSS, base href,
canonical link, visible `Source:` line, dark mode).

It is dependency-free apart from the runtime itself: the HTML parser
and the Markdown converter are hand-written (`src/html.ts`,
`src/markdown.ts` — a port of `markdownify` 1.2.x semantics). The only
optional dependency is `playwright`, used solely for dynamic scraping
and loaded lazily, so the static engine works without it.

## Setup

**Bun (primary, no build step):**

```bash
cd typescript
bun install            # playwright is optional; static works without it
bun run src/cli.ts scrape https://example.com
```

**Node (build first):**

```bash
cd typescript
npm install
npm run build          # npx tsc -> dist/
node dist/cli.js scrape https://example.com
```

Requires Node 18+ (global `fetch`) or Bun 1.x. TypeScript 5.9, strict
mode, NodeNext modules, ES2022 target.

## CLI

Mirrors the Python CLI surface for the static path:

```bash
# All four output formats
bun run src/cli.ts scrape https://example.com --format markdown
bun run src/cli.ts scrape https://example.com --format html
bun run src/cli.ts scrape https://example.com --format html-document
bun run src/cli.ts scrape https://example.com --format html-raw

# Dynamic (JavaScript-rendered) pages — needs Playwright + Chromium
bun run src/cli.ts scrape http://quotes.toscrape.com/js/ --dynamic

# Crawl, assets, stripping, fetch tuning
bun run src/cli.ts scrape https://example.com --crawl --depth 2 --max-pages 10
bun run src/cli.ts scrape https://example.com --svg-action file --image-action file --assets-dir ./assets
bun run src/cli.ts scrape https://example.com --strip script --strip style
bun run src/cli.ts scrape https://example.com --proxy http://127.0.0.1:8080 --user-agent random --delay 0.5 --retries 3

# URL-list file, output file/directory, banner control (global, before the subcommand)
bun run src/cli.ts --banner none scrape urls.txt --output ./out
```

`--format`, `--dynamic`, `--crawl/--depth/--max-pages/--only-subpaths`,
`--svg-action/--image-action/--assets-dir`, `--strip` (repeatable),
`--proxy/--user-agent/--delay/--retries`, `--server` (remote mode,
posts to the Flask `/api/scrape` endpoint with `engine: "ts"`), and the
global `--banner` (`default` / `stdout` / `stderr` / `none`) all behave
like their Python counterparts.

### `--json` machine mode

The contract the Flask app uses. Reads **one** JSON request from
stdin, writes **one** JSON result to stdout, exits non-zero with
`{"error": "..."}` on failure:

```bash
echo '{"url": "https://example.com", "options": {"dynamic": false}}' \
  | bun run src/cli.ts --json
```

Request shape (snake_case keys, as sent by Flask):

```json
{ "op": "scrape" | "wrap" | "content_html",
  "url": "https://example.com",
  "options": { "dynamic": false, "svg_action": "image",
               "image_action": "remote", "strip_tags": [],
               "proxy": null, "user_agent": null, "delay": 0,
               "retries": 3, "ignore_https_errors": false,
               "crawl": false, "depth": 3, "max_pages": 10,
               "only_subpaths": false, "assets_dir": null } }
```

`scrape` returns the full `ScrapeResult` (or `{"results": [...]}` when
`options.crawl` is true); `wrap` returns `{"html_document": ...}`;
`content_html` returns `{"html": ...}`.

## Library

```typescript
import { scrapeNative, crawlNative, Scraper, wrapHtmlDocument } from "./src/index.ts";

// One-shot scrape — same result shape as Python's Scraper.scrape():
// { url, metadata: { title, description, author, date, tags },
//   markdown, html, html_document, raw_html, nav_links, internal_links }
const result = await scrapeNative("https://example.com", {
  svgAction: "image",
  imageAction: "remote",
});

// Crawl (BFS, same-domain, depth / max-pages / only-subpaths)
const pages = await crawlNative("https://example.com", { depth: 2, maxPages: 10 });

// Class API, matching Python's Scraper where it makes sense
const scraper = new Scraper({ proxy: "http://127.0.0.1:8080", retries: 3 });
const r2 = await scraper.scrape("https://example.com", { dynamic: true });
const html = scraper.toHtml("<h1>Hi</h1><p>Text.</p>");
const doc = Scraper.wrapHtmlDocument(html, { title: "Hi", sourceUrl: "https://example.com" });
```

Other exports: `fetchHtml`, `contentHtml`, `selectOutput`,
`sanitizeFilename`, `titleForFilename`, `parseHtml`, `serialize`,
`detectCodeLanguage`.

## Dynamic scraping

Dynamic mode uses Playwright (optional dependency). The browser is
launched headless with `--no-sandbox --disable-gpu`, `executablePath`
from the `CHROMIUM_PATH` environment variable when set, proxy from the
`proxy` option or `PYSCRAPER_PROXY` / `http_proxy` / `https_proxy`
environment variables, and `ignore_https_errors` as a configurable
option (default `false`). Navigation uses `domcontentloaded` with a
120 s timeout plus a 3 s settle, then returns `page.content()`; the
computed-style SVG baking matches Python's `fetch_html_dynamic`.

On a restricted VM where Chromium can only make loopback connections,
point the proxy at a loopback relay, e.g.:

```bash
PYSCRAPER_PROXY=http://127.0.0.1:8891 bun run src/cli.ts scrape http://quotes.toscrape.com/js/ --dynamic
```

## Local files

Like the Python engine, a `.html` / `.htm` / `.mht` / `.mhtml` path
can be scraped directly (no fetch). `.mht` / `.mhtml` (MIME multipart)
is parsed with a minimal built-in parser, including base64 and
quoted-printable bodies.

## Tests

```bash
bun test            # 74 tests across 5 files
```

`tests/side-by-side.test.ts` scrapes the same fixture pages with both
engines (via `tests/helpers/py_scrape.py`) and compares every result
field. As of the last run, static outputs are byte-identical to Python
on `example.com`, the bundled blog fixture, and a saved arXiv page, and
dynamic output is byte-identical on `http://quotes.toscrape.com/js/`.

## Capability parity vs Python

| Capability | Python | TypeScript |
|---|---|---|
| Static fetch (proxy, UA rotation/`random`, delay, retries w/ backoff) | ✅ | ✅ |
| Dynamic scraping (Playwright) | ✅ | ✅ (optional dep) |
| Main-content extraction, metadata, link extraction | ✅ | ✅ |
| Markdown / HTML / html-document / html-raw outputs | ✅ | ✅ |
| SVG/image actions incl. `file` + `assets_dir` | ✅ | ✅ |
| Local `.html`/`.mht` input | ✅ | ✅ |
| Crawling (BFS, depth/max-pages/only-subpaths) | ✅ | ✅ |
| Code-language detection (incl. HTML/CSS cases) | ✅ | ✅ |
| CLI (scrape, banner, formats, server mode) | ✅ | ✅ |
| Flask web app | ✅ | via `engine: "ts"` (see below) |
| `--json` machine mode | — | ✅ (the Flask bridge) |

## Using it from Python / the web app

The Python side shells out to this package; nothing here needs to
know about Flask:

* `src/md_scraper/ts_engine.py` — `scrape_ts()` / `crawl_ts()` /
  `wrap_ts()` / `content_html_ts()`, plus `ts_command()` (locates the
  CLI: `PYSCRAPER_TS_CMD` env override, else `bun run src/cli.ts`,
  else `node dist/cli.js`).
* Python CLI: `scraper scrape URL --engine ts` (default `python`).
  With `--server`, the engine choice is sent to the server.
* Flask: `POST /api/scrape` accepts `engine: "python" | "ts"`
  (default `"python"`); `/api/download-zip` accepts the same field and
  rebuilds missing `html` / `html_document` with the TS engine. The
  web UI has an Engine dropdown.

## Known limits

* The HTML parser is a tolerant hand-rolled parser, not a full
  HTML5 parser: pathological documents (e.g. text before `<head>`
  that makes libxml2 dissolve the `<head>`) serialize slightly
  differently from BeautifulSoup/lxml. Real-world pages and
  browser-serialized DOM (`page.content()`) are unaffected.
* Dynamic scraping is slower than static (Chromium startup + render);
  on a slow VM a small JS page can take ~40 s, and HTTPS `CONNECT`
  through a loopback relay can be flaky for some hosts — prefer `http`
  for the dynamic smoke test.
* No `scraper-go.sh` equivalent; no Docker image of its own — the TS
  package is a library/CLI inside this repo, not a separate service.
