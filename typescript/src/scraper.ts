/**
 * scraper.ts — TypeScript port of `md_scraper.scraper.Scraper`.
 *
 * Dependency-free apart from the global `fetch` and `Buffer`. The
 * Playwright browser used for dynamic scraping is loaded lazily via
 * `require("playwright")` so the static path works with no browser
 * installed at all.
 *
 * This is a faithful re-implementation of the engine that previously
 * lived in the PyScraper-md Space (`server/src/scraper.ts`); the Space
 * does not expose its source for export, so this file was rebuilt from
 * the Python source (the spec) and the recorded inspection of the
 * Space engine. It is not a byte copy.
 */
import * as fs from "node:fs";
import * as path from "node:path";
import { createRequire } from "node:module";
import {
  type Node,
  type DocNode,
  type ElNode,
  parseHtml,
  serialize,
  documentBody,
  getAttr,
  setAttr,
  classList,
  textContent,
  findAll,
  findDescendants,
  findFirst,
  findFirstByTag,
  hasAncestor,
  detach,
  replaceWith,
  unwrap,
  appendChild,
  makeEl,
  makeText,
  selectAll,
} from "./html.js";
import { MarkdownConverter } from "./markdown.js";
import { MarkdownSanitizer } from "./sanitizer.js";

export type SvgAction = "image" | "preserve" | "strip" | "file";
export type ImageAction = "remote" | "base64" | "file";
export type OutputFormat = "markdown" | "html" | "html-document" | "html-raw";

export interface ScrapeMetadata {
  title: string | null;
  description: string | null;
  author: string | null;
  date: string | null;
  tags: string[];
}

export interface ScrapeResult {
  url: string;
  metadata: ScrapeMetadata;
  markdown: string;
  html: string;
  html_document: string;
  raw_html: string;
  nav_links: string[];
  internal_links: string[];
}

export interface ScrapeOptions {
  svgAction?: SvgAction;
  imageAction?: ImageAction;
  assetsDir?: string;
  baseUrl?: string;
  strip?: string[];
  /** Run the MarkdownSanitizer post-pass (default true). */
  sanitize?: boolean;
  /**
   * Keep processed image sources in the tree after toMarkdown()
   * (default true for direct callers; scrape() passes false so the
   * `html` output carries the same asset handling as the Markdown).
   */
  restoreOriginalSrcs?: boolean;
}

export interface FetchOptions {
  proxy?: string;
  userAgent?: string;
  delay?: number;
  retries?: number;
}

export interface ScraperOptions extends FetchOptions {
  /** Request timeout in seconds (default 30). */
  timeout?: number;
  /** Ignore TLS errors in the Playwright browser (default false). */
  ignoreHttpsErrors?: boolean;
  /** Injectable fetch implementation (used by tests). */
  fetchImpl?: typeof fetch;
}

export interface ScrapeCallOptions extends ScrapeOptions, FetchOptions {
  dynamic?: boolean;
  timeout?: number;
  ignoreHttpsErrors?: boolean;
  fetchImpl?: typeof fetch;
}

export interface CrawlOptions extends ScrapeCallOptions {
  depth?: number;
  maxPages?: number;
  onlySubpaths?: boolean;
}

const RETRY_STATUSES = new Set([429, 500, 502, 503, 504]);

const sleep = (ms: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, ms));

function resolveUrl(base: string, href: string): string {
  try {
    return new URL(href, base).href;
  } catch {
    // Non-URL base (a local file path): emulate urljoin on paths.
    // Absolute hrefs are returned as-is; fragments/queries attach to
    // the base path; other relative hrefs resolve against its directory.
    if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(href)) return href;
    const cleanBase = stripHashAndQuery(base);
    if (href.startsWith("#") || href.startsWith("?")) {
      return cleanBase + href;
    }
    if (href.startsWith("/")) return normalizePath(href);
    const dir = cleanBase.slice(0, cleanBase.lastIndexOf("/") + 1);
    return normalizePath(dir + href);
  }
}

/** Remove `.`/`..` dot segments, as urljoin does (RFC 3986 §5.2.4). */
function normalizePath(p: string): string {
  const trailingSlash =
    p.endsWith("/") || p.endsWith("/.") || p.endsWith("/..");
  const out: string[] = [];
  for (const seg of p.split("/")) {
    if (seg === ".") continue;
    if (seg === "..") {
      out.pop();
      continue;
    }
    out.push(seg);
  }
  let joined = out.join("/");
  if (p.startsWith("/") && !joined.startsWith("/")) joined = `/${joined}`;
  if (trailingSlash && !joined.endsWith("/")) joined += "/";
  return joined;
}

/** Host (netloc) of a URL, or "" for plain paths (cf. urlparse().netloc). */
function urlHost(target: string): string {
  try {
    return new URL(target).host;
  } catch {
    return "";
  }
}

function stripHashAndQuery(url: string): string {
  return url.split("#")[0].split("?")[0];
}

function isLocalFile(target: string): boolean {
  try {
    return fs.existsSync(target) && fs.statSync(target).isFile();
  } catch {
    return false;
  }
}

// Self-contained stylesheet for standalone HTML documents produced by
// wrapHtmlDocument(). No external requests: system font stack only, so a
// scraped page renders fully offline. (Copied verbatim from the Python
// engine's STANDALONE_DOCUMENT_CSS — it is the shared spec.)
export const STANDALONE_DOCUMENT_CSS = `
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1a1a1a; background: #fff; max-width: 800px; margin: 0 auto; padding: 1rem 1.5rem 3rem; overflow-wrap: break-word; }
h1, h2, h3, h4, h5, h6 { line-height: 1.25; margin: 1.5em 0 0.5em; }
h1 { font-size: 2rem; border-bottom: 1px solid #ddd; padding-bottom: 0.3em; }
h2 { font-size: 1.5rem; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }
a { color: #0969da; }
a:visited { color: #8250df; }
.scraped-source { font-size: 0.85em; color: #666; border-bottom: 1px solid #eee; padding-bottom: 0.5em; margin: 0 0 1.5em; }
img, svg, video { max-width: 100%; height: auto; }
pre { background: #f6f8fa; border: 1px solid #ddd; border-radius: 6px; padding: 1rem; overflow-x: auto; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.875em; }
pre code { font-size: 1em; background: none; padding: 0; }
p code, li code, td code { background: #f6f8fa; border-radius: 3px; padding: 0.2em 0.4em; }
table { border-collapse: collapse; display: block; overflow-x: auto; margin: 1em 0; }
th, td { border: 1px solid #ddd; padding: 0.5em 1em; text-align: left; }
th { background: #f6f8fa; }
blockquote { border-left: 4px solid #ddd; margin: 1em 0; padding: 0 1em; color: #555; }
hr { border: none; border-top: 1px solid #ddd; margin: 2em 0; }
@media (prefers-color-scheme: dark) {
  body { color: #e6e6e6; background: #0d1117; }
  h1 { border-bottom-color: #333; }
  h2 { border-bottom-color: #222; }
  a { color: #58a6ff; }
  a:visited { color: #bc8cff; }
  pre, p code, li code, td code, th { background: #161b22; }
  pre, th, td, blockquote { border-color: #333; }
  blockquote { color: #aaa; }
  .scraped-source { color: #aaa; border-bottom-color: #222; }
}
`;

export class Scraper {
  static readonly DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
  ];

  readonly proxy?: string;
  readonly userAgent?: string;
  readonly delay: number;
  readonly timeout: number;
  readonly retries: number;
  readonly ignoreHttpsErrors: boolean;
  readonly fetchImpl: typeof fetch;
  readonly sanitizer = new MarkdownSanitizer();

  private _playwright: unknown = null;
  private _browser: unknown = null;

  constructor(options: ScraperOptions = {}) {
    this.proxy = options.proxy;
    this.userAgent = options.userAgent;
    this.delay = options.delay ?? 0.0;
    this.timeout = options.timeout ?? 30;
    this.retries = options.retries ?? 3;
    this.ignoreHttpsErrors = options.ignoreHttpsErrors ?? false;
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  getUserAgent(customUa?: string): string {
    const target = customUa !== undefined ? customUa : this.userAgent;
    if (target && target !== "random") return target;
    const agents = Scraper.DEFAULT_USER_AGENTS;
    return agents[Math.floor(Math.random() * agents.length)];
  }

  async close(): Promise<void> {
    const browser = this._browser as {
      close?: () => Promise<void>;
    } | null;
    if (browser?.close) {
      await browser.close();
      this._browser = null;
    }
    const pw = this._playwright as { stop?: () => void } | null;
    if (pw?.stop) {
      pw.stop();
      this._playwright = null;
    }
  }

  // -- fetching -----------------------------------------------------------

  /**
   * Run `fn` with the proxy exported to the environment for its
   * duration. Bun and Node's `fetch` both honour `http_proxy` /
   * `https_proxy` from the environment (including when set at runtime),
   * which is how the `proxy` option is applied without a dependency.
   */
  private async withProxy<T>(
    proxy: string | undefined,
    fn: () => Promise<T>,
  ): Promise<T> {
    if (!proxy) return fn();
    const keys = ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"];
    const saved = keys.map(
      (k) => [k, process.env[k]] as [string, string | undefined],
    );
    for (const k of keys) process.env[k] = proxy;
    try {
      return await fn();
    } finally {
      for (const [k, v] of saved) {
        if (v === undefined) delete process.env[k];
        else process.env[k] = v;
      }
    }
  }

  async fetchHtml(
    url: string,
    options: FetchOptions = {},
  ): Promise<string> {
    if (isLocalFile(url)) return this.readLocalFile(url);

    // requests raises MissingSchema/InvalidSchema for URLs without an
    // http(s) scheme instead of attempting (and retrying) the request.
    let parsed: URL;
    try {
      parsed = new URL(url);
    } catch {
      throw new Error(`Invalid URL '${url}': No scheme supplied.`);
    }
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      throw new Error(
        `Invalid URL '${url}': No connection adapters were found for '${parsed.protocol}//'.`,
      );
    }

    const reqDelay = options.delay ?? this.delay;
    const reqRetries = options.retries ?? this.retries;
    const targetProxy = options.proxy ?? this.proxy;
    const ua = this.getUserAgent(options.userAgent);

    const headers: Record<string, string> = {
      "User-Agent": ua,
      Accept:
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
      "Accept-Language": "en-US,en;q=0.5",
    };

    let lastError: unknown = null;
    for (let attempt = 0; attempt <= reqRetries; attempt++) {
      if (reqDelay > 0) await sleep(reqDelay * 1000);
      try {
        const response = await this.withProxy(targetProxy, () =>
          this.fetchImpl(url, {
            headers,
            signal: AbortSignal.timeout(this.timeout * 1000),
          }),
        );
        if (response.ok) return await response.text();
        const error = new Error(
          `HTTP ${response.status} ${response.statusText} for ${url}`,
        );
        (error as Error & { status?: number }).status = response.status;
        lastError = error;
        if (attempt < reqRetries && RETRY_STATUSES.has(response.status)) {
          await sleep(2 ** attempt * 1000);
          continue;
        }
        throw error;
      } catch (e) {
        if (e === lastError) throw e;
        lastError = e;
        // Retry on connection/timeout errors (fetch throws TypeError
        // for network failures, DOMException for timeouts/aborts).
        if (attempt < reqRetries && isNetworkError(e)) {
          await sleep(2 ** attempt * 1000);
          continue;
        }
        throw e;
      }
    }
    if (lastError) throw lastError;
    throw new Error(`Failed to fetch ${url}`);
  }

  private readLocalFile(filePath: string): string {
    const lower = filePath.toLowerCase();
    if (lower.endsWith(".mht") || lower.endsWith(".mhtml")) {
      return parseMht(fs.readFileSync(filePath));
    }
    return fs.readFileSync(filePath, "utf-8");
  }

  // -- dynamic fetching (Playwright, optional) -----------------------------

  private async ensureBrowser(proxy?: string): Promise<{
    newContext: (opts: Record<string, unknown>) => Promise<{
      newPage: () => Promise<unknown>;
      close: () => Promise<void>;
    }>;
    close: () => Promise<void>;
  }> {
    if (!this._playwright) {
      let playwrightPkg: unknown;
      try {
        // require() keeps the static build working when Playwright is
        // not installed (it is an optional dependency).
        const require = createRequire(import.meta.url);
        playwrightPkg = require("playwright");
      } catch {
        throw new Error(
          "Playwright is not installed. Install it with 'npm install playwright' (or 'bun add playwright') and 'npx playwright install chromium'.",
        );
      }
      const pw = playwrightPkg as {
        chromium: {
          launch: (opts: Record<string, unknown>) => Promise<unknown>;
        };
      };
      this._playwright = pw;
    }

    const targetProxy =
      proxy ??
      this.proxy ??
      process.env.PYSCRAPER_PROXY ??
      process.env.HTTPS_PROXY ??
      process.env.HTTP_PROXY;

    if (!this._browser) {
      const pw = this._playwright as {
        chromium: {
          launch: (opts: Record<string, unknown>) => Promise<unknown>;
        };
      };
      const executablePath = process.env.CHROMIUM_PATH || undefined;
      const launchOptions: Record<string, unknown> = { headless: true };
      if (executablePath) {
        launchOptions.executablePath = executablePath;
        // Often needed for custom binaries / containerized or root runs.
        launchOptions.args = ["--no-sandbox", "--disable-gpu"];
      }
      if (targetProxy) {
        launchOptions.proxy = { server: targetProxy };
      }
      this._browser = await pw.chromium.launch(launchOptions);
    }
    return this._browser as {
      newContext: (opts: Record<string, unknown>) => Promise<{
        newPage: () => Promise<unknown>;
        close: () => Promise<void>;
      }>;
      close: () => Promise<void>;
    };
  }

  async fetchHtmlDynamic(
    url: string,
    options: FetchOptions & { ignoreHttpsErrors?: boolean } = {},
  ): Promise<string> {
    const reqDelay = options.delay ?? this.delay;
    if (reqDelay > 0) await sleep(reqDelay * 1000);

    const browser = await this.ensureBrowser(options.proxy);
    const ua = this.getUserAgent(options.userAgent);
    const ignoreHttpsErrors =
      options.ignoreHttpsErrors ??
      this.ignoreHttpsErrors ??
      ["1", "true"].includes(
        (process.env.PYSCRAPER_IGNORE_HTTPS_ERRORS ?? "").toLowerCase(),
      );
    const context = await browser.newContext({
      userAgent: ua,
      viewport: { width: 1280, height: 800 },
      ignoreHTTPSErrors: ignoreHttpsErrors,
    });
    const page = (await context.newPage()) as {
      goto: (
        url: string,
        opts: Record<string, unknown>,
      ) => Promise<unknown>;
      waitForTimeout: (ms: number) => Promise<void>;
      evaluate: (fn: string) => Promise<unknown>;
      content: () => Promise<string>;
      close: () => Promise<void>;
    };
    try {
      // domcontentloaded + a long timeout + a settle delay: this VM's
      // renderer is slow, and `networkidle` with the 30s default timed
      // out just before pages finished (same reasoning as the Python
      // engine's dynamic defaults).
      await page.goto(url, {
        waitUntil: "domcontentloaded",
        timeout: 120000,
      });
      await page.waitForTimeout(3000);

      // Bake computed styles into SVGs so they render correctly.
      await page.evaluate(`() => {
        document.querySelectorAll('svg').forEach(svg => {
          const style = window.getComputedStyle(svg);
          const rect = svg.getBoundingClientRect();
          const width = rect.width > 0 ? rect.width : (parseInt(svg.getAttribute('width')) || 16);
          const height = rect.height > 0 ? rect.height : (parseInt(svg.getAttribute('height')) || 16);
          svg.setAttribute('width', width);
          svg.setAttribute('height', height);
          if (svg.getAttribute('fill') === 'currentColor' || !svg.hasAttribute('fill')) {
            const fill = style.fill !== 'none' ? style.fill : (style.color || '#000000');
            svg.setAttribute('fill', fill);
          }
          if (svg.getAttribute('stroke') === 'currentColor') {
            svg.setAttribute('stroke', style.stroke || style.color || '#000000');
          }
          svg.style.opacity = '1';
          svg.style.visibility = 'visible';
          svg.style.display = 'inline-block';
          svg.removeAttribute('class');
        });
      }`);

      return await page.content();
    } finally {
      await page.close();
      await context.close();
    }
  }

  // -- code language detection ---------------------------------------------

  detectCodeLanguage(el: ElNode): string {
    for (const cls of classList(el)) {
      if (cls.startsWith("language-")) return cls.slice("language-".length);
    }
    const text = textContent(el);
    const stripped = text.trim();
    if (!stripped) return "";

    const bashPatterns = [
      /#!\s*\/bin\/(ba)?sh/,
      /\$\{?\w+\}?/,
      /\$\(/,
      /`[^`]*`/,
      /\s+[|&]\s+/,
      /^\s*(?:npm|npx|pip|poetry|git|cargo|docker|curl|wget|jref|cd|mkdir|ls|sudo|yarn|pnpm|gcloud|aws|kubectl|make|python|node|bash|sh|cat|echo|chmod|chown|systemctl|service)\b/,
    ];
    if (bashPatterns.some((re) => new RegExp(re.source, "m").test(text))) {
      return "bash";
    }

    const pythonPatterns = [
      /def\s+\w+\s*\(/,
      /class\s+\w+\s*[:()]/,
      /->\s*\w+/,
      /import\s+\w+/,
      /from\s+\w+\s+import/,
      /#\s*type:\s*/,
      /if\s+__name__\s*==\s*["']__main__["']/,
    ];
    if (pythonPatterns.some((re) => new RegExp(re.source, "m").test(text))) {
      return "python";
    }

    const jsPatterns = [
      /function\s+\w+\s*\(/,
      /const\s+\w+\s*=/,
      /let\s+\w+\s*=/,
      /var\s+\w+\s*=/,
      /=>/,
      /\{\s*\}/,
      /\[[^\]]*\]/,
      /document\./,
      /console\./,
    ];
    if (jsPatterns.some((re) => re.test(text))) return "javascript";

    const htmlPatterns = [
      /<\s*\w+[^>]*>/,
      /<\s*\/\s*\w+\s*>/,
      /&[a-zA-Z]+;/,
    ];
    if (htmlPatterns.some((re) => new RegExp(re.source, "i").test(text))) {
      if (/<\s*\w+[^>]*>.*<\s*\/\s*\w+\s*>/is.test(text)) return "html";
    }

    const cssPatterns = [
      /\.\s*\w+/,
      /#\s*\w+/,
      /\w+\s*\{[^}]*\}/,
      /@media/,
      /@import/,
    ];
    if (cssPatterns.some((re) => re.test(text))) {
      if (/[\w-]+\s*:/.test(text) && text.includes("{") && text.includes("}")) {
        return "css";
      }
    }

    if (stripped.startsWith("{") && stripped.endsWith("}")) {
      try {
        JSON.parse(stripped);
        return "json";
      } catch {
        // fall through
      }
    }
    if (stripped.startsWith("[") && stripped.endsWith("]")) {
      try {
        JSON.parse(stripped);
        return "json";
      } catch {
        // fall through
      }
    }

    const sqlPatterns = [
      /SELECT\s+.+\s+FROM/,
      /INSERT\s+INTO/,
      /UPDATE\s+.+\s+SET/,
      /DELETE\s+FROM/,
      /CREATE\s+TABLE/,
      /ALTER\s+TABLE/,
      /DROP\s+TABLE/,
    ];
    if (sqlPatterns.some((re) => new RegExp(re.source, "i").test(text))) {
      return "sql";
    }

    return "";
  }

  // -- extraction ---------------------------------------------------------

  private asDoc(input: string | DocNode | ElNode): DocNode | ElNode {
    return typeof input === "string" ? parseHtml(input) : input;
  }

  extractMainContent(
    input: string | DocNode | ElNode,
    asNode = false,
  ): string | DocNode | ElNode {
    const doc = this.asDoc(input);

    // Remove boilerplate tags and common UI clutter containers.
    const boilerplate = findAll(doc, (el) =>
      ["nav", "footer", "header", "aside", "script", "style"].includes(el.tag),
    );
    for (const el of boilerplate) detach(el);

    const noiseSelectors = [
      ".Layout-sidebar",
      ".js-header-wrapper",
      ".Header",
      "#repository-container-header",
      ".js-footer-container",
      ".site-footer",
      ".footer",
    ];
    for (const sel of noiseSelectors) {
      for (const el of selectAll(doc, sel)) detach(el);
    }

    // Primary selection, mirroring the Python order. Class/id patterns
    // are strict full matches so partial ids like
    // `user-query-content-0` do not win over a real <main>.
    const mainClassRe =
      /^(markdown-body|article-content|entry-content|post-content|main-content)$/i;
    const mainIdRe = /^(readme|main-content|main_content|article)$/i;
    const mainContent =
      findFirstByTag(doc, "main") ??
      findFirst(doc, (el) => getAttr(el, "role") === "main") ??
      findFirstByTag(doc, "article") ??
      findFirst(doc, (el) => getAttr(el, "itemprop") === "articleBody") ??
      findFirst(doc, (el) => classList(el).some((c) => mainClassRe.test(c))) ??
      findFirst(doc, (el) => {
        const id = getAttr(el, "id");
        return id !== undefined && mainIdRe.test(id);
      }) ??
      findFirst(
        doc,
        (el) =>
          el.tag === "div" &&
          classList(el).some((c) =>
            ["content", "main", "post-content"].includes(c),
          ),
      );

    const result = mainContent ?? documentBody(doc) ?? doc;
    return asNode ? result : serialize(result);
  }

  extractMetadata(input: string | DocNode | ElNode): ScrapeMetadata {
    const doc = this.asDoc(input);
    const metadata: ScrapeMetadata = {
      title: null,
      description: null,
      author: null,
      date: null,
      tags: [],
    };

    // 1. JSON-LD
    const jsonLdScripts = findAll(
      doc,
      (el) =>
        el.tag === "script" &&
        getAttr(el, "type") === "application/ld+json",
    );
    for (const script of jsonLdScripts) {
      try {
        const data: unknown = JSON.parse(textContent(script));
        if (typeof data === "object" && data !== null && !Array.isArray(data)) {
          const d = data as Record<string, unknown>;
          metadata.title =
            metadata.title ??
            (typeof d.headline === "string" ? d.headline : null) ??
            (typeof d.name === "string" ? d.name : null);
          metadata.description =
            metadata.description ??
            (typeof d.description === "string" ? d.description : null);
          metadata.date =
            metadata.date ??
            (typeof d.datePublished === "string" ? d.datePublished : null);
          const author = d.author;
          if (typeof author === "object" && author !== null && !Array.isArray(author)) {
            const name = (author as Record<string, unknown>).name;
            metadata.author =
              metadata.author ?? (typeof name === "string" ? name : null);
          } else if (Array.isArray(author) && author.length > 0) {
            const first = author[0];
            if (typeof first === "object" && first !== null) {
              const name = (first as Record<string, unknown>).name;
              metadata.author =
                metadata.author ?? (typeof name === "string" ? name : null);
            }
          }
        }
      } catch {
        continue;
      }
    }

    // 2. OpenGraph
    const ogTitle = findFirst(
      doc,
      (el) => el.tag === "meta" && getAttr(el, "property") === "og:title",
    );
    if (ogTitle) {
      metadata.title =
        metadata.title ?? getAttr(ogTitle, "content") ?? null;
    }
    const ogDesc = findFirst(
      doc,
      (el) => el.tag === "meta" && getAttr(el, "property") === "og:description",
    );
    if (ogDesc) {
      metadata.description =
        metadata.description ?? getAttr(ogDesc, "content") ?? null;
    }

    // 3. Standard meta tags
    const authorTag = findFirst(
      doc,
      (el) => el.tag === "meta" && getAttr(el, "name") === "author",
    );
    if (authorTag) {
      metadata.author =
        metadata.author ?? getAttr(authorTag, "content") ?? null;
    }
    const descTag = findFirst(
      doc,
      (el) => el.tag === "meta" && getAttr(el, "name") === "description",
    );
    if (descTag) {
      metadata.description =
        metadata.description ?? getAttr(descTag, "content") ?? null;
    }

    // 4. Fallback to <title>
    if (!metadata.title) {
      const titleEl = findFirstByTag(doc, "title");
      if (titleEl) {
        // bs4's `.string` is null when the title has nested tags.
        if (
          titleEl.children.length === 1 &&
          titleEl.children[0].kind === "text"
        ) {
          metadata.title = titleEl.children[0].text;
        }
      }
    }

    return metadata;
  }

  extractNavLinks(
    input: string | DocNode | ElNode,
    baseUrl: string,
  ): string[] {
    const doc = this.asDoc(input);
    const links: string[] = [];

    const navElements = [
      ...findAll(doc, (el) => el.tag === "nav" || el.tag === "aside"),
      ...findAll(
        doc,
        (el) =>
          el.tag === "div" &&
          classList(el).some((c) => /sidebar|menu|nav|toc/i.test(c)),
      ),
    ];
    const body = documentBody(doc);
    const searchScope: Array<DocNode | ElNode> =
      navElements.length > 0 ? navElements : body ? [body] : [doc];

    const baseDomain = urlHost(baseUrl);
    const cleanBaseUrl = stripHashAndQuery(baseUrl);
    const seen = new Set<string>();

    for (const element of searchScope) {
      for (const a of findAll(element, (el) => el.tag === "a")) {
        const href = getAttr(a, "href");
        if (href === undefined) continue;
        const fullUrl = resolveUrl(baseUrl, href);
        if (urlHost(fullUrl) !== baseDomain) continue;
        const cleanUrl = stripHashAndQuery(fullUrl);
        if (cleanUrl === cleanBaseUrl) continue;
        if (seen.has(cleanUrl)) continue;
        seen.add(cleanUrl);
        links.push(cleanUrl);
      }
    }
    return links;
  }

  extractLinks(input: string | DocNode | ElNode, baseUrl: string): string[] {
    const doc = this.asDoc(input);
    const links: string[] = [];
    const baseDomain = urlHost(baseUrl);
    const cleanBaseUrl = stripHashAndQuery(baseUrl);
    const seen = new Set<string>();

    for (const a of findAll(doc, (el) => el.tag === "a")) {
      const href = getAttr(a, "href");
      if (
        !href ||
        href.startsWith("javascript:") ||
        href.startsWith("mailto:") ||
        href.startsWith("tel:")
      ) {
        continue;
      }
      const fullUrl = resolveUrl(baseUrl, href);
      if (urlHost(fullUrl) !== baseDomain) continue;
      const cleanUrl = stripHashAndQuery(fullUrl);
      if (cleanUrl === cleanBaseUrl) continue;
      if (seen.has(cleanUrl)) continue;
      seen.add(cleanUrl);
      links.push(cleanUrl);
    }
    return links;
  }

  // -- conversion ---------------------------------------------------------

  async toMarkdown(
    input: string | DocNode | ElNode,
    options: ScrapeOptions = {},
  ): Promise<string> {
    const svgAction = options.svgAction ?? "image";
    const imageAction = options.imageAction ?? "remote";
    const assetsDir = options.assetsDir;
    const baseUrl = options.baseUrl;
    const restoreOriginalSrcs = options.restoreOriginalSrcs ?? true;

    const node = this.asDoc(input);

    // 0. Div-based code blocks (Docusaurus/StyleX-style monospace divs).
    const monospaceRe = /monospace|code-block|code-snippet|x1iwq0vh/i;
    const codeDivs = findAll(
      node,
      (el) =>
        el.tag === "div" && classList(el).some((c) => monospaceRe.test(c)),
    );
    for (const div of codeDivs) {
      if (hasAncestor(div, ["pre", "code"])) continue;
      if (textContent(div).trim() === "") continue;
      const hasBlockChild = findDescendants(
        div,
        (el) => el.tag === "div" || el.tag === "p",
      ).length > 0;
      if (hasBlockChild) continue;
      const pre = makeEl("pre");
      const code = makeEl("code");
      for (const child of [...div.children]) {
        detach(child);
        appendChild(code, child);
      }
      appendChild(pre, code);
      replaceWith(div, pre);
    }

    // 1. SVGs
    const placeholders = new Map<string, ElNode>();
    const preserved: Array<{ node: Node; svg: ElNode }> = [];
    const svgs = findAll(node, (el) => el.tag === "svg");
    if (svgAction === "strip") {
      for (const svg of svgs) detach(svg);
    } else if (svgAction === "image" || svgAction === "file") {
      if (svgAction === "file" && assetsDir) {
        fs.mkdirSync(assetsDir, { recursive: true });
      }
      svgs.forEach((svg, i) => {
        if (
          getAttr(svg, "fill") === "currentColor" ||
          getAttr(svg, "fill") === undefined
        ) {
          setAttr(svg, "fill", "#000000");
        }
        if (
          getAttr(svg, "width") === undefined ||
          getAttr(svg, "height") === undefined
        ) {
          const viewBox = getAttr(svg, "viewbox");
          if (viewBox) {
            try {
              const parts = viewBox.replace(/,/g, " ").split(/\s+/).map(Number);
              const [, , w, h] = parts;
              if (getAttr(svg, "width") === undefined && Number.isFinite(w)) {
                setAttr(svg, "width", String(Math.trunc(w)));
              }
              if (getAttr(svg, "height") === undefined && Number.isFinite(h)) {
                setAttr(svg, "height", String(Math.trunc(h)));
              }
            } catch {
              // keep the 16px fallback below
            }
          }
          if (getAttr(svg, "width") === undefined) setAttr(svg, "width", "16");
          if (getAttr(svg, "height") === undefined) setAttr(svg, "height", "16");
        }
        const svgStr = serialize(svg);
        let img: ElNode;
        if (svgAction === "file" && assetsDir) {
          const filename = `svg_icon_${i}.svg`;
          fs.writeFileSync(path.join(assetsDir, filename), svgStr, "utf-8");
          img = makeEl("img", [
            ["src", `${path.basename(assetsDir)}/${filename}`],
            ["alt", "svg icon"],
          ]);
        } else {
          const encoded = Buffer.from(svgStr, "utf-8").toString("base64");
          img = makeEl("img", [
            ["src", `data:image/svg+xml;base64,${encoded}`],
            ["alt", "svg image"],
          ]);
        }
        replaceWith(svg, img);
      });
    } else if (svgAction === "preserve") {
      svgs.forEach((svg, i) => {
        const placeholder = `MDScraperSVG${i}`;
        placeholders.set(placeholder, svg);
        const textNode = makeText(placeholder);
        replaceWith(svg, textNode);
        preserved.push({ node: textNode, svg });
      });
    }

    // 2. Standard images
    const originalSrcs = new Map<ElNode, string>();
    if (imageAction !== "remote") {
      const allImgs = findAll(node, (el) => el.tag === "img");
      const candidates: Array<{ i: number; img: ElNode; src: string }> = [];
      allImgs.forEach((img, i) => {
        const src = getAttr(img, "src");
        if (!src || src.startsWith("data:")) return;
        const resolved = baseUrl ? resolveUrl(baseUrl, src) : src;
        originalSrcs.set(img, src);
        candidates.push({ i, img, src: resolved });
      });
      if (imageAction === "file" && assetsDir && candidates.length > 0) {
        fs.mkdirSync(assetsDir, { recursive: true });
      }
      const results = await Promise.all(
        candidates.map(async ({ i, src }) => {
          try {
            const response = await this.fetchImpl(src, {
              signal: AbortSignal.timeout(10000),
            });
            if (!response.ok) return { i, newSrc: null as string | null };
            const bytes = Buffer.from(await response.arrayBuffer());
            if (imageAction === "base64") {
              const contentType =
                response.headers.get("Content-Type") ?? "image/png";
              return {
                i,
                newSrc: `data:${contentType};base64,${bytes.toString("base64")}`,
              };
            }
            if (imageAction === "file" && assetsDir) {
              let ext = src.split(".").at(-1)?.split("?")[0] ?? "";
              if (!ext) ext = "png";
              const filename = `image_${i}.${ext}`;
              fs.writeFileSync(path.join(assetsDir, filename), bytes);
              return { i, newSrc: `${path.basename(assetsDir)}/${filename}` };
            }
            return { i, newSrc: null as string | null };
          } catch {
            return { i, newSrc: null as string | null };
          }
        }),
      );
      const imgByIndex = new Map(allImgs.map((img, i) => [i, img]));
      for (const { i, newSrc } of results) {
        const img = imgByIndex.get(i);
        if (img && newSrc) setAttr(img, "src", newSrc);
      }
    }

    // 3. --strip: unwrap the tags (children survive).
    const stripTags = options.strip ?? [];
    for (const tagName of stripTags) {
      for (const el of findAll(node, (el) => el.tag === tagName.toLowerCase())) {
        unwrap(el);
      }
    }

    const converter = new MarkdownConverter({
      bullets: "-",
      codeLanguageCallback: (el) => this.detectCodeLanguage(el),
      strip: stripTags,
    });
    // Python converts `str(soup)` — the processed tree serialized and
    // re-parsed — rather than the tree itself. Re-parsing merges
    // adjacent text nodes left behind by decompose/unwrap (e.g. an
    // SVG stripped between two text runs), which is what collapses
    // their whitespace the same way markdownify sees it.
    let markdown = converter.convert(parseHtml(serialize(node)));

    // Restore preserved SVGs in the Markdown, and back into the tree.
    if (svgAction === "preserve" && placeholders.size > 0) {
      const pattern = new RegExp(
        [...placeholders.keys()].map(escapeRegExp).join("|"),
        "g",
      );
      markdown = markdown.replace(pattern, (m) => {
        const svg = placeholders.get(m);
        return svg ? serialize(svg) : m;
      });
      for (const { node: textNode, svg } of preserved) {
        replaceWith(textNode, svg);
      }
    }

    if (restoreOriginalSrcs) {
      for (const [img, src] of originalSrcs) setAttr(img, "src", src);
    }

    if (options.sanitize ?? true) {
      markdown = this.sanitizer.sanitize(markdown);
    }
    return markdown;
  }

  async toHtml(
    input: string | DocNode | ElNode,
    options: ScrapeOptions = {},
  ): Promise<string> {
    const node = this.asDoc(input);
    await this.toMarkdown(node, { ...options, restoreOriginalSrcs: false });
    return serialize(node);
  }

  contentHtml(rawHtml: string): string {
    const node = this.extractMainContent(rawHtml, true) as DocNode | ElNode;
    return serialize(node);
  }

  static wrapHtmlDocument(
    contentHtml: string,
    options: {
      title?: string;
      sourceUrl?: string;
      metadata?: ScrapeMetadata | Record<string, unknown>;
      includeBase?: boolean;
    } = {},
  ): string {
    const text = (contentHtml || "").trim();
    if (!text) return "";
    // Already a full document: do not double-wrap.
    if (/^(<!doctype html|<html[\s>])/is.test(text)) return contentHtml;

    // A top-level <body>...</body> fragment would nest a <body> inside
    // the document body; keep only its contents.
    const bodyMatch = /^<body[^>]*>([\s\S]*)<\/body\s*>$/i.exec(text);
    const bodyText = bodyMatch ? bodyMatch[1].trim() : text;

    const meta = (options.metadata ?? {}) as Record<string, unknown>;
    const escape = (s: string): string =>
      s
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#x27;");
    const pageTitle = escape(
      options.title ?? options.sourceUrl ?? "Scraped Page",
    );
    let isHttp = false;
    if (options.sourceUrl) {
      try {
        isHttp = ["http:", "https:"].includes(
          new URL(options.sourceUrl).protocol,
        );
      } catch {
        isHttp = false;
      }
    }

    const headLines = [
      '<meta charset="utf-8">',
      '<meta name="viewport" content="width=device-width, initial-scale=1">',
      `<title>${pageTitle}</title>`,
    ];
    const author = meta.author;
    if (author) {
      headLines.push(`<meta name="author" content="${escape(String(author))}">`);
    }
    const description = meta.description;
    if (description) {
      headLines.push(
        `<meta name="description" content="${escape(String(description))}">`,
      );
    }
    if (isHttp && options.sourceUrl) {
      if (options.includeBase ?? true) {
        headLines.push(`<base href="${escape(options.sourceUrl)}">`);
      }
      headLines.push(
        `<link rel="canonical" href="${escape(options.sourceUrl)}">`,
      );
    }
    headLines.push(`<style>\n${STANDALONE_DOCUMENT_CSS.trim()}\n</style>`);

    const head = headLines.join("\n");
    let sourceComment = "";
    let sourceLine = "";
    if (options.sourceUrl) {
      const escapedUrl = escape(options.sourceUrl);
      sourceComment = `<!-- Scraped from ${escapedUrl} by md-scraper -->\n`;
      if (isHttp) {
        sourceLine =
          `<p class="scraped-source">Source: ` +
          `<a href="${escape(options.sourceUrl)}">${escapedUrl}</a></p>\n`;
      } else {
        sourceLine = `<p class="scraped-source">Source: ${escapedUrl}</p>\n`;
      }
    }
    return (
      "<!DOCTYPE html>\n" +
      '<html lang="en">\n' +
      "<head>\n" +
      `${head}\n` +
      "</head>\n" +
      "<body>\n" +
      `${sourceComment}` +
      `${sourceLine}` +
      `${bodyText}\n` +
      "</body>\n" +
      "</html>\n"
    );
  }

  async scrape(url: string, options: ScrapeCallOptions = {}): Promise<ScrapeResult> {
    const {
      dynamic = false,
      svgAction,
      imageAction,
      assetsDir,
      baseUrl,
      strip,
      sanitize,
      proxy,
      userAgent,
      delay,
      retries,
    } = options;

    const html = dynamic
      ? await this.fetchHtmlDynamic(url, { proxy, userAgent, delay })
      : await this.fetchHtml(url, { proxy, userAgent, delay, retries });

    const doc = parseHtml(html);
    const metadata = this.extractMetadata(doc);
    const navLinks = this.extractNavLinks(doc, url);
    const internalLinks = this.extractLinks(doc, url);

    const main = this.extractMainContent(doc, true) as DocNode | ElNode;
    const markdown = await this.toMarkdown(main, {
      svgAction,
      imageAction,
      assetsDir,
      baseUrl,
      strip,
      sanitize,
      restoreOriginalSrcs: false,
    });
    const htmlContent = serialize(main);

    const includeBase =
      (imageAction ?? "remote") !== "file" &&
      (svgAction ?? "image") !== "file";
    const htmlDocument = Scraper.wrapHtmlDocument(htmlContent, {
      title: metadata.title ?? undefined,
      sourceUrl: url,
      metadata,
      includeBase,
    });

    return {
      url,
      metadata,
      markdown,
      html: htmlContent,
      html_document: htmlDocument,
      raw_html: html,
      nav_links: navLinks,
      internal_links: internalLinks,
    };
  }
}

function isNetworkError(e: unknown): boolean {
  if (e instanceof TypeError) return true; // undici network failures
  if (typeof e === "object" && e !== null && "name" in e) {
    const name = (e as { name?: string }).name;
    return name === "TimeoutError" || name === "AbortError";
  }
  return false;
}

// ---------------------------------------------------------------------------
// MHT / MHTML local files
// ---------------------------------------------------------------------------

function decodeQuotedPrintable(input: string): Buffer {
  const bytes: number[] = [];
  for (let i = 0; i < input.length; i++) {
    const c = input[i];
    if (c === "=") {
      if (input[i + 1] === "\r" && input[i + 2] === "\n") {
        i += 2;
        continue;
      }
      if (input[i + 1] === "\n") {
        i += 1;
        continue;
      }
      const hex = input.slice(i + 1, i + 3);
      if (/^[0-9A-Fa-f]{2}$/.test(hex)) {
        bytes.push(parseInt(hex, 16));
        i += 2;
        continue;
      }
    }
    bytes.push(input.charCodeAt(i) & 0xff);
  }
  return Buffer.from(bytes);
}

function decodePartBody(
  body: string,
  transferEncoding: string,
  charset: string,
): string {
  let bytes: Buffer;
  const enc = transferEncoding.toLowerCase().replace(/["\s]/g, "");
  if (enc === "base64") {
    bytes = Buffer.from(body.replace(/\s/g, ""), "base64");
  } else if (enc === "quoted-printable") {
    bytes = decodeQuotedPrintable(body);
  } else {
    bytes = Buffer.from(body, "latin1");
  }
  try {
    return new TextDecoder(charset || "utf-8", { fatal: false }).decode(bytes);
  } catch {
    return bytes.toString("utf-8");
  }
}

function parsePartHeaders(
  raw: string,
): { headers: Map<string, string>; body: string } {
  const headers = new Map<string, string>();
  const splitAt = raw.search(/\r?\n\r?\n/);
  const head = splitAt === -1 ? raw : raw.slice(0, splitAt);
  const body = splitAt === -1 ? "" : raw.slice(splitAt).replace(/^\r?\n\r?\n/, "");
  // Unfold continuation lines, then parse `Name: value`.
  const unfolded = head.replace(/\r?\n[ \t]+/g, " ");
  for (const line of unfolded.split(/\r?\n/)) {
    const idx = line.indexOf(":");
    if (idx > 0) {
      headers.set(line.slice(0, idx).trim().toLowerCase(), line.slice(idx + 1).trim());
    }
  }
  return { headers, body };
}

function headerParam(contentType: string | undefined, param: string): string | undefined {
  if (!contentType) return undefined;
  const m = new RegExp(`${param}\\s*=\\s*(?:"([^"]*)"|([^;\\s]*))`, "i").exec(contentType);
  return m ? (m[1] ?? m[2]) : undefined;
}

function parseMht(buffer: Buffer, filePath = ""): string {
  const raw = buffer.toString("latin1");
  const { headers, body } = parsePartHeaders(raw);
  const contentType = headers.get("content-type") ?? "";
  const boundary = headerParam(contentType, "boundary");

  const decodePart = (partRaw: string): string | null => {
    const { headers: partHeaders, body: partBody } = parsePartHeaders(partRaw);
    const partType = (partHeaders.get("content-type") ?? "").toLowerCase();
    if (!partType.startsWith("text/html")) return null;
    const charset = headerParam(partHeaders.get("content-type"), "charset") ?? "utf-8";
    return decodePartBody(
      partBody,
      partHeaders.get("content-transfer-encoding") ?? "",
      charset,
    );
  };

  if (boundary) {
    const parts = body.split(new RegExp(`--${escapeRegExp(boundary)}(?:--)?\\r?\\n`));
    for (const part of parts) {
      const decoded = decodePart(part);
      if (decoded !== null) return decoded;
    }
  } else if (contentType.toLowerCase().startsWith("text/html")) {
    return decodePartBody(
      body,
      headers.get("content-transfer-encoding") ?? "",
      headerParam(contentType, "charset") ?? "utf-8",
    );
  }

  throw new Error(`Could not find text/html content in MHT file: ${filePath}`);
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// ---------------------------------------------------------------------------
// Crawler (port of md_scraper.crawler.Crawler)
// ---------------------------------------------------------------------------

export interface CrawlerOptions {
  maxDepth?: number;
  maxPages?: number;
  sameDomain?: boolean;
  onlySubpaths?: boolean;
}

/** Breadth-first crawl queue with visited tracking and domain/subpath filters. */
export class Crawler {
  readonly maxDepth: number;
  readonly maxPages: number;
  readonly sameDomain: boolean;
  readonly onlySubpaths: boolean;
  readonly allowedDomains: Set<string>;
  readonly startUrls: string[];
  crawledCount = 0;

  private queue: Array<[string, number]> = [];
  private visited: Set<string>;

  constructor(startUrls: string[], options: CrawlerOptions = {}) {
    this.queue = startUrls.map((url) => [url, 0] as [string, number]);
    this.visited = new Set(startUrls);
    this.maxDepth = options.maxDepth ?? 3;
    this.maxPages = options.maxPages ?? 50;
    this.sameDomain = options.sameDomain ?? true;
    this.onlySubpaths = options.onlySubpaths ?? false;
    this.allowedDomains = new Set(
      startUrls.map((url) => {
        try {
          return new URL(url).host;
        } catch {
          return "";
        }
      }),
    );
    this.startUrls = [...startUrls];
  }

  get queueLength(): number {
    return this.queue.length;
  }

  hasNext(): boolean {
    return this.queue.length > 0 && this.crawledCount < this.maxPages;
  }

  /** Next URL and depth, or null when exhausted (cf. StopIteration). */
  next(): { url: string; depth: number } | null {
    if (!this.queue.length || this.crawledCount >= this.maxPages) return null;
    const [url, depth] = this.queue.shift() as [string, number];
    this.crawledCount += 1;
    return { url, depth };
  }

  addLinks(links: string[], currentDepth: number): void {
    if (currentDepth >= this.maxDepth) return;
    for (const link of links) {
      if (this.visited.has(link)) continue;
      if (this.sameDomain) {
        let domain: string;
        try {
          domain = new URL(link).host;
        } catch {
          continue;
        }
        if (!this.allowedDomains.has(domain)) continue;
      }
      if (this.onlySubpaths) {
        if (!this.startUrls.some((start) => link.startsWith(start))) continue;
      }
      this.visited.add(link);
      this.queue.push([link, currentDepth + 1]);
    }
  }

  [Symbol.iterator](): Iterator<{ url: string; depth: number }> {
    return {
      next: () => {
        const item = this.next();
        return item
          ? { value: item, done: false }
          : { value: undefined, done: true };
      },
    };
  }
}

// ---------------------------------------------------------------------------
// Standalone (Space-compatible) exports
// ---------------------------------------------------------------------------

/** Fetch a URL (or local file) to raw HTML. */
export async function fetchHtml(
  url: string,
  options: FetchOptions & { timeout?: number } = {},
): Promise<string> {
  const scraper = new Scraper(options);
  try {
    return await scraper.fetchHtml(url, options);
  } finally {
    await scraper.close();
  }
}

/** Scrape one URL, returning the full ScrapeResult. */
export async function scrapeNative(
  url: string,
  options: ScrapeCallOptions = {},
): Promise<ScrapeResult> {
  const scraper = new Scraper(options);
  try {
    return await scraper.scrape(url, options);
  } finally {
    await scraper.close();
  }
}

/** Breadth-first crawl from `startUrls`, returning one result per page. */
export async function crawlNative(
  startUrls: string[],
  options: CrawlOptions = {},
): Promise<ScrapeResult[]> {
  const { depth = 3, maxPages = 50, onlySubpaths = false, ...scrapeOptions } =
    options;
  const crawler = new Crawler(startUrls, {
    maxDepth: depth,
    maxPages,
    onlySubpaths,
  });
  const scraper = new Scraper(scrapeOptions);
  const results: ScrapeResult[] = [];
  try {
    while (crawler.hasNext()) {
      const item = crawler.next();
      if (!item) break;
      const result = await scraper.scrape(item.url, scrapeOptions);
      results.push(result);
      crawler.addLinks(result.internal_links, item.depth);
    }
    return results;
  } finally {
    await scraper.close();
  }
}

/** Best-effort content HTML for a raw document (main-content extraction only). */
export function contentHtml(rawHtml: string): string {
  return new Scraper().contentHtml(rawHtml);
}

/** Standalone-document wrapper (re-exported for library callers). */
export const wrapHtmlDocument = Scraper.wrapHtmlDocument;

/** Pick the output text and file extension for a scrape result. */
export function selectOutput(
  result: Partial<ScrapeResult>,
  outputFormat: string,
): [string, string] {
  if (outputFormat === "html-raw") {
    return [result.raw_html ?? "", ".html"];
  }
  if (outputFormat === "html" || outputFormat === "html-document") {
    let html = result.html;
    if (html === undefined || html === null) {
      html = contentHtml(result.raw_html ?? "");
    }
    if (outputFormat === "html-document") {
      let doc = result.html_document;
      if (doc === undefined || doc === null) {
        const metadata = result.metadata ?? {
          title: null,
          description: null,
          author: null,
          date: null,
          tags: [],
        };
        doc = Scraper.wrapHtmlDocument(html, {
          title: metadata.title ?? undefined,
          sourceUrl: result.url,
          metadata,
        });
      }
      return [doc, ".html"];
    }
    return [html, ".html"];
  }
  return [result.markdown ?? "", ".md"];
}

const FILENAME_SANITIZE_RE = /[^\p{L}\p{N}_.-]/gu;

/** Sanitize a string to be safe for filenames (max 50 chars). */
export function sanitizeFilename(name: string): string {
  return String(name)
    .trim()
    .replace(/ /g, "_")
    .replace(FILENAME_SANITIZE_RE, "")
    .slice(0, 50);
}

/** A filename title for a result, from metadata or URL (cf. utils.get_title_from_result). */
export function titleForFilename(
  result: Partial<ScrapeResult>,
  url: string,
): string {
  const metadata = result.metadata;
  let title = metadata?.title ?? null;
  if (!title) {
    try {
      const parsed = new URL(url);
      if (parsed.pathname && parsed.pathname !== "/") {
        title = parsed.pathname.replace(/\/$/, "").split("/").at(-1) ?? null;
      } else {
        title = parsed.host;
      }
    } catch {
      title = "scraped_page";
    }
  }
  if (!title) title = `scraped_${Math.floor(Date.now() / 1000)}`;
  return sanitizeFilename(title);
}
