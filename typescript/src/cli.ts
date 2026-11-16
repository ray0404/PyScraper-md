#!/usr/bin/env node
/**
 * cli.ts — CLI for the TypeScript scraper engine.
 *
 * Mirrors the Python CLI (`md_scraper.cli`) surface for the static path:
 *
 *   pyscraper-md-ts scrape URL... [options]
 *   pyscraper-md-ts --banner stderr scrape URL... --format html-document
 *   pyscraper-md-ts hello
 *
 * Plus a machine mode used by the Flask web app:
 *
 *   pyscraper-md-ts --json < request.json > result.json
 *
 * --json reads one JSON request from stdin and writes one JSON result
 * to stdout. Request shape (snake_case keys, as sent by Flask):
 *
 *   {"op": "scrape", "url": "https://example.com",
 *    "options": {"dynamic": false, "svg_action": "image",
 *      "image_action": "remote", "strip_tags": [],
 *      "crawl": false, "depth": 3, "max_pages": 10,
 *      "only_subpaths": false, "proxy": null, "user_agent": null,
 *      "delay": 0, "retries": 3, "ignore_https_errors": false}}
 *
 *   {"op": "wrap", "content_html": "...", "title": "...",
 *    "source_url": "...", "metadata": {...}, "include_base": true}
 *   {"op": "content_html", "raw_html": "..."}
 *
 * On success the ScrapeResult (or `{"results": [...]}` for crawl, or
 * the op-specific object) is written to stdout. On failure a JSON
 * `{"error": "..."}` object is written to stdout and the process
 * exits non-zero; diagnostics go to stderr.
 */
import * as fs from "node:fs";
import * as path from "node:path";
import {
  Scraper,
  Crawler,
  scrapeNative,
  crawlNative,
  contentHtml,
  wrapHtmlDocument,
  selectOutput,
  sanitizeFilename,
  titleForFilename,
  type ScrapeResult,
  type ScrapeCallOptions,
} from "./scraper.js";

const BANNER_MODES = ["default", "stdout", "stderr", "none"] as const;
type BannerMode = (typeof BANNER_MODES)[number];

const FORMATS = ["markdown", "html", "html-document", "html-raw"] as const;
type OutputFormat = (typeof FORMATS)[number];

function bannerTarget(
  bannerMode: BannerMode,
  outputFormat: OutputFormat,
): "stdout" | "stderr" | null {
  if (bannerMode === "none") return null;
  if (bannerMode === "stdout") return "stdout";
  if (bannerMode === "stderr") return "stderr";
  if (outputFormat === "html-document" || outputFormat === "html-raw") {
    return null;
  }
  return "stdout";
}

function fail(message: string, code = 1): never {
  process.stderr.write(`${message}\n`);
  process.exit(code);
}

interface ScrapeCliOptions {
  output?: string;
  dynamic: boolean;
  strip: string[];
  svgAction: "image" | "preserve" | "strip" | "file";
  imageAction: "remote" | "base64" | "file";
  assetsDir?: string;
  server?: string;
  crawl: boolean;
  depth: number;
  maxPages: number;
  onlySubpaths: boolean;
  proxy?: string;
  userAgent?: string;
  delay: number;
  retries: number;
  format: OutputFormat;
}

function parseScrapeArgs(args: string[]): { urls: string[]; opts: ScrapeCliOptions } {
  const opts: ScrapeCliOptions = {
    dynamic: false,
    strip: [],
    svgAction: "image",
    imageAction: "remote",
    crawl: false,
    depth: 3,
    maxPages: 10,
    onlySubpaths: false,
    delay: 0.0,
    retries: 3,
    format: "markdown",
  };
  const urls: string[] = [];
  const takeValue = (flag: string, i: number): [string, number] => {
    const eq = args[i].indexOf("=");
    if (eq >= 0) return [args[i].slice(eq + 1), i];
    if (i + 1 >= args.length) fail(`Error: ${flag} requires a value.`, 2);
    return [args[i + 1], i + 1];
  };
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    const flag = arg.split("=")[0];
    switch (flag) {
      case "--output":
      case "-o": {
        const [v, ni] = takeValue(flag, i);
        opts.output = v;
        i = ni;
        break;
      }
      case "--dynamic":
      case "-d":
        opts.dynamic = true;
        break;
      case "--strip":
      case "-s": {
        const [v, ni] = takeValue(flag, i);
        opts.strip.push(v);
        i = ni;
        break;
      }
      case "--svg-action": {
        const [v, ni] = takeValue(flag, i);
        if (!["image", "preserve", "strip", "file"].includes(v)) {
          fail(`Error: invalid --svg-action '${v}'.`, 2);
        }
        opts.svgAction = v as ScrapeCliOptions["svgAction"];
        i = ni;
        break;
      }
      case "--image-action": {
        const [v, ni] = takeValue(flag, i);
        if (!["remote", "base64", "file"].includes(v)) {
          fail(`Error: invalid --image-action '${v}'.`, 2);
        }
        opts.imageAction = v as ScrapeCliOptions["imageAction"];
        i = ni;
        break;
      }
      case "--assets-dir": {
        const [v, ni] = takeValue(flag, i);
        opts.assetsDir = v;
        i = ni;
        break;
      }
      case "--server": {
        const [v, ni] = takeValue(flag, i);
        opts.server = v;
        i = ni;
        break;
      }
      case "--crawl":
      case "-c":
        opts.crawl = true;
        break;
      case "--depth": {
        const [v, ni] = takeValue(flag, i);
        opts.depth = parseInt(v, 10);
        if (Number.isNaN(opts.depth)) fail(`Error: invalid --depth '${v}'.`, 2);
        i = ni;
        break;
      }
      case "--max-pages": {
        const [v, ni] = takeValue(flag, i);
        opts.maxPages = parseInt(v, 10);
        if (Number.isNaN(opts.maxPages)) fail(`Error: invalid --max-pages '${v}'.`, 2);
        i = ni;
        break;
      }
      case "--only-subpaths":
        opts.onlySubpaths = true;
        break;
      case "--proxy": {
        const [v, ni] = takeValue(flag, i);
        opts.proxy = v;
        i = ni;
        break;
      }
      case "--user-agent":
      case "-ua": {
        const [v, ni] = takeValue(flag, i);
        opts.userAgent = v;
        i = ni;
        break;
      }
      case "--delay": {
        const [v, ni] = takeValue(flag, i);
        opts.delay = parseFloat(v);
        if (Number.isNaN(opts.delay)) fail(`Error: invalid --delay '${v}'.`, 2);
        i = ni;
        break;
      }
      case "--retries": {
        const [v, ni] = takeValue(flag, i);
        opts.retries = parseInt(v, 10);
        if (Number.isNaN(opts.retries)) fail(`Error: invalid --retries '${v}'.`, 2);
        i = ni;
        break;
      }
      case "--format": {
        const [v, ni] = takeValue(flag, i);
        if (!(FORMATS as readonly string[]).includes(v)) {
          fail(`Error: invalid --format '${v}'.`, 2);
        }
        opts.format = v as OutputFormat;
        i = ni;
        break;
      }
      case "--engine":
        // Accepted for uniformity with the Python CLI's --engine flag;
        // this binary *is* the TS engine, so there is nothing to switch.
        takeValue(flag, i);
        break;
      case "--help":
      case "-h":
        printScrapeHelp();
        process.exit(0);
        break;
      default:
        if (arg.startsWith("-")) {
          fail(`Error: unknown option '${arg}'.`, 2);
        }
        urls.push(arg);
    }
  }
  return { urls, opts };
}

function printScrapeHelp(): void {
  process.stdout.write(
    `Usage: pyscraper-md-ts scrape URL... [options]

Scrape URL(s) and print/save content in the requested format.
URLS can be web links or a path to a text file containing URLs.

Options:
  -o, --output PATH        File path (single URL) or directory (multiple URLs)
  -d, --dynamic            Enable Playwright-based dynamic scraping
  -s, --strip TAG          Tags to strip (repeatable)
      --svg-action ACTION  image|preserve|strip|file (default: image)
      --image-action ACT   remote|base64|file (default: remote)
      --assets-dir DIR     Directory for 'file' actions
      --server URL         Remote scraper server URL
  -c, --crawl              Recursively crawl links found on the page
      --depth N            Crawling depth (default: 3)
      --max-pages N        Max pages per initial URL (default: 10)
      --only-subpaths      Restrict crawling to subpaths of the initial URL(s)
      --proxy URL          Proxy server URL
  -ua, --user-agent UA     Custom User-Agent header or "random"
      --delay SECONDS      Delay between requests (default: 0.0)
      --retries N          Max retry attempts (default: 3)
      --format FORMAT      markdown|html|html-document|html-raw (default: markdown)
`,
  );
}

function expandUrlArgs(urls: string[]): string[] {
  const out: string[] = [];
  for (const u of urls) {
    if (fs.existsSync(u) && fs.statSync(u).isFile()) {
      const ext = path.extname(u).toLowerCase();
      if ([".html", ".htm", ".mht", ".mhtml"].includes(ext)) {
        out.push(u);
      } else {
        try {
          const lines = fs
            .readFileSync(u, "utf-8")
            .split(/\r?\n/)
            .map((l) => l.trim())
            .filter((l) => l && !l.startsWith("#"));
          out.push(...lines);
        } catch (e) {
          process.stderr.write(
            `Error reading file ${u}: ${e instanceof Error ? e.message : e}\n`,
          );
        }
      }
    } else {
      out.push(u);
    }
  }
  return out;
}

interface ServerPayload {
  url: string;
  dynamic: boolean;
  svg_action: string;
  image_action: string;
  strip_tags: string[];
  proxy?: string;
  user_agent?: string;
  delay: number;
  retries: number;
  format: string;
  engine: string;
}

async function scrapeViaServer(
  server: string,
  url: string,
  opts: ScrapeCliOptions,
): Promise<ScrapeResult> {
  const apiUrl = `${server.replace(/\/$/, "")}/api/scrape`;
  const payload: ServerPayload = {
    url,
    dynamic: opts.dynamic,
    svg_action: opts.svgAction,
    image_action: opts.imageAction,
    strip_tags: opts.strip,
    proxy: opts.proxy,
    user_agent: opts.userAgent,
    delay: opts.delay,
    retries: opts.retries,
    format: opts.format,
    engine: "ts",
  };
  let response: Response;
  try {
    response = await fetch(apiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    throw new Error(
      `Connection error: ${e instanceof Error ? e.message : e}`,
    );
  }
  if (!response.ok) {
    throw new Error(
      `Server error (${response.status}): ${await response.text()}`,
    );
  }
  return (await response.json()) as ScrapeResult;
}

async function runScrape(
  rawUrls: string[],
  opts: ScrapeCliOptions,
  bannerMode: BannerMode,
): Promise<void> {
  const target = bannerTarget(bannerMode, opts.format);
  const initialUrls = expandUrlArgs(rawUrls);
  if (initialUrls.length === 0) {
    process.stderr.write("No URLs provided.\n");
    return;
  }

  const count = initialUrls.length;
  const { output } = opts;
  if (output && (count > 1 || opts.crawl)) {
    if (fs.existsSync(output) && fs.statSync(output).isFile()) {
      fail(
        `Error: Output '${output}' is a file. When crawling or scraping multiple URLs, please specify a directory.`,
      );
    }
    if (!fs.existsSync(output)) fs.mkdirSync(output, { recursive: true });
  }

  const iterator: Crawler | Array<[string, number]> = opts.crawl
    ? new Crawler(initialUrls, {
        maxDepth: opts.depth,
        maxPages: opts.maxPages,
        onlySubpaths: opts.onlySubpaths,
      })
    : initialUrls.map((u) => [u, 0] as [string, number]);

  let processed = 0;
  const scraper = opts.server ? null : new Scraper({
    proxy: opts.proxy,
    userAgent: opts.userAgent,
    delay: opts.delay,
    retries: opts.retries,
  });

  try {
    if (iterator instanceof Crawler) {
      // Live BFS loop: pull one URL at a time so addLinks() feeds the queue.
      while (iterator.hasNext()) {
        const current = iterator.next();
        if (!current) break;
        processed += 1;
        await processOne(current.url, current.depth, processed, iterator);
      }
    } else {
      for (const [currentUrl, currentDepth] of iterator) {
        processed += 1;
        await processOne(currentUrl, currentDepth, processed, null);
      }
    }
  } finally {
    if (scraper) await scraper.close();
  }

  async function processOne(
    currentUrl: string,
    currentDepth: number,
    n: number,
    crawler: Crawler | null,
  ): Promise<void> {
    const prefix = `[${n}]${opts.crawl ? ` (Depth ${currentDepth})` : ""}`;
    process.stderr.write(`${prefix} Scraping ${currentUrl}...\n`);
    try {
      let currentAssetsDir = opts.assetsDir;
      if (
        (opts.svgAction === "file" || opts.imageAction === "file") &&
        !currentAssetsDir
      ) {
        if (output) {
          const basePath = fs.existsSync(output) && fs.statSync(output).isDirectory()
            ? output
            : path.dirname(output);
          currentAssetsDir = path.join(basePath || ".", "assets");
        } else {
          currentAssetsDir = "assets";
        }
      }

      const scrapeOptions: ScrapeCallOptions = {
        dynamic: opts.dynamic,
        svgAction: opts.svgAction,
        imageAction: opts.imageAction,
        assetsDir: currentAssetsDir,
        baseUrl: currentUrl,
        strip: opts.strip,
        proxy: opts.proxy,
        userAgent: opts.userAgent,
        delay: opts.delay,
        retries: opts.retries,
      };
      const result = opts.server
        ? await scrapeViaServer(opts.server, currentUrl, opts)
        : await (scraper as Scraper).scrape(currentUrl, scrapeOptions);
      const [content, extension] = selectOutput(result, opts.format);

      if (output) {
        let filePath: string;
        if (
          !opts.crawl &&
          count === 1 &&
          !(fs.existsSync(output) && fs.statSync(output).isDirectory()) &&
          !output.endsWith("/")
        ) {
          filePath = output;
        } else {
          const title = titleForFilename(result, currentUrl);
          filePath = path.join(output, `${sanitizeFilename(title)}${extension}`);
        }
        fs.writeFileSync(filePath, content, "utf-8");
        process.stdout.write(`  -> Saved: ${filePath}\n`);
      } else {
        if (target === "stdout") {
          process.stdout.write(`\n--- URL: ${currentUrl} ---\n\n`);
        } else if (target === "stderr") {
          process.stderr.write(`\n--- URL: ${currentUrl} ---\n\n`);
        }
        process.stdout.write(`${content}\n`);
      }

      if (opts.crawl && crawler) {
        let links = result.internal_links as string[] | undefined;
        if (links === undefined || links === null) {
          const rawHtml = result.raw_html ?? "";
          links = rawHtml
            ? (scraper as Scraper).extractLinks(rawHtml, currentUrl)
            : (result.nav_links ?? []);
        }
        crawler.addLinks(links ?? [], currentDepth);
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      process.stderr.write(`  -> Failed to scrape ${currentUrl}: ${message}\n`);
      if (!opts.crawl && count === 1) {
        throw e;
      }
    }
  }
}

// -- --json machine mode ------------------------------------------------------

type JsonRequest = {
  op?: string;
  url?: string;
  options?: Record<string, unknown>;
  content_html?: string;
  title?: string;
  source_url?: string;
  metadata?: Record<string, unknown>;
  include_base?: boolean;
  raw_html?: string;
};

function pick<T>(obj: Record<string, unknown>, ...keys: string[]): T | undefined {
  for (const k of keys) {
    if (obj[k] !== undefined) return obj[k] as T;
  }
  return undefined;
}

function normalizeScrapeOptions(
  options: Record<string, unknown>,
): ScrapeCallOptions & {
  crawl?: boolean;
  depth?: number;
  maxPages?: number;
  onlySubpaths?: boolean;
} {
  const stripRaw = pick<string[] | string>(options, "strip_tags", "strip");
  const strip = Array.isArray(stripRaw)
    ? stripRaw
    : typeof stripRaw === "string"
      ? [stripRaw]
      : undefined;
  return {
    dynamic: pick<boolean>(options, "dynamic") ?? false,
    svgAction: pick<string>(options, "svg_action", "svgAction") as ScrapeCallOptions["svgAction"],
    imageAction: pick<string>(options, "image_action", "imageAction") as ScrapeCallOptions["imageAction"],
    assetsDir: pick<string>(options, "assets_dir", "assetsDir"),
    baseUrl: pick<string>(options, "base_url", "baseUrl"),
    strip,
    proxy: pick<string>(options, "proxy") ?? undefined,
    userAgent: pick<string>(options, "user_agent", "userAgent"),
    delay: pick<number>(options, "delay"),
    retries: pick<number>(options, "retries"),
    ignoreHttpsErrors: pick<boolean>(
      options,
      "ignore_https_errors",
      "ignoreHttpsErrors",
    ),
    crawl: pick<boolean>(options, "crawl"),
    depth: pick<number>(options, "depth"),
    maxPages: pick<number>(options, "max_pages", "maxPages"),
    onlySubpaths: pick<boolean>(options, "only_subpaths", "onlySubpaths"),
  };
}

async function runJsonMode(): Promise<void> {
  const raw = fs.readFileSync(0, "utf-8");
  let request: JsonRequest;
  try {
    request = JSON.parse(raw) as JsonRequest;
  } catch (e) {
    process.stdout.write(
      JSON.stringify({ error: `Invalid JSON on stdin: ${e instanceof Error ? e.message : e}` }),
    );
    process.exit(1);
  }
  try {
    const op = request.op ?? "scrape";
    if (op === "scrape") {
      if (!request.url) throw new Error("URL is required");
      const options = normalizeScrapeOptions(request.options ?? {});
      if (options.crawl) {
        const results = await crawlNative([request.url], {
          ...options,
          depth: options.depth ?? 3,
          maxPages: options.maxPages ?? 10,
          onlySubpaths: options.onlySubpaths ?? false,
        });
        process.stdout.write(JSON.stringify({ results }));
      } else {
        const result = await scrapeNative(request.url, options);
        process.stdout.write(JSON.stringify(result));
      }
      return;
    }
    if (op === "wrap") {
      const doc = wrapHtmlDocument(request.content_html ?? "", {
        title: request.title,
        sourceUrl: request.source_url,
        metadata: request.metadata,
        includeBase: request.include_base,
      });
      process.stdout.write(JSON.stringify({ html_document: doc }));
      return;
    }
    if (op === "content_html") {
      process.stdout.write(
        JSON.stringify({ html: contentHtml(request.raw_html ?? "") }),
      );
      return;
    }
    throw new Error(`Unknown op: ${op}`);
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    process.stderr.write(`--json error: ${message}\n`);
    process.stdout.write(JSON.stringify({ error: message }));
    process.exit(1);
  }
}

// -- entry --------------------------------------------------------------------

async function main(): Promise<void> {
  const argv = process.argv.slice(2);
  if (argv.includes("--json")) {
    await runJsonMode();
    return;
  }

  let bannerMode: BannerMode = "default";
  let rest = argv;
  // Global --banner comes before the subcommand.
  if (rest[0] === "--banner") {
    const value = rest[1];
    if (!value || !(BANNER_MODES as readonly string[]).includes(value)) {
      fail(
        `Error: Invalid value for '--banner': '${value ?? ""}'. Expected one of: ${BANNER_MODES.join(", ")}.`,
        2,
      );
    }
    bannerMode = value as BannerMode;
    rest = rest.slice(2);
  } else if (rest[0]?.startsWith("--banner=")) {
    const value = rest[0].slice("--banner=".length);
    if (!(BANNER_MODES as readonly string[]).includes(value)) {
      fail(
        `Error: Invalid value for '--banner': '${value}'. Expected one of: ${BANNER_MODES.join(", ")}.`,
        2,
      );
    }
    bannerMode = value as BannerMode;
    rest = rest.slice(1);
  }

  const [command, ...cmdArgs] = rest;
  if (!command || command === "--help" || command === "-h") {
    process.stdout.write(
      `Usage: pyscraper-md-ts [--banner MODE] <command> [options]

Commands:
  scrape URL...   Scrape URL(s) to Markdown/HTML
  hello           Print a greeting

Global options:
  --banner MODE   default|stdout|stderr|none (where the '--- URL: ---' banner goes)
  --json          Machine mode: read a JSON request on stdin, write JSON to stdout

Run 'pyscraper-md-ts scrape --help' for scrape options.
`,
    );
    return;
  }

  if (command === "hello") {
    process.stdout.write("Hello from md-scraper!\n");
    return;
  }

  if (command === "scrape") {
    const { urls, opts } = parseScrapeArgs(cmdArgs);
    try {
      await runScrape(urls, opts, bannerMode);
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      process.stderr.write(`Fatal error: ${message}\n`);
      process.exit(1);
    }
    return;
  }

  fail(`Error: unknown command '${command}'.`, 2);
}

main().catch((e: unknown) => {
  const message = e instanceof Error ? e.message : String(e);
  process.stderr.write(`Fatal error: ${message}\n`);
  process.exit(1);
});
