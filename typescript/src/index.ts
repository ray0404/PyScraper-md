/**
 * index.ts — library entry point for pyscraper-md-ts.
 *
 * The TypeScript port of the PyScraper-md engine: dependency-free
 * static scraping plus optional Playwright dynamic scraping, usable
 * as a library, from the CLI (`src/cli.ts`), or via the Flask web app
 * (`--json` mode, see the CLI).
 */
export {
  Scraper,
  Crawler,
  fetchHtml,
  scrapeNative,
  crawlNative,
  contentHtml,
  wrapHtmlDocument,
  selectOutput,
  sanitizeFilename,
  titleForFilename,
  STANDALONE_DOCUMENT_CSS,
} from "./scraper.js";
export type {
  ScrapeResult,
  ScrapeMetadata,
  ScrapeOptions,
  ScrapeCallOptions,
  CrawlOptions,
  FetchOptions,
  ScraperOptions,
  CrawlerOptions,
  SvgAction,
  ImageAction,
  OutputFormat,
} from "./scraper.js";
export { parseHtml, serialize } from "./html.js";
export type { DocNode, ElNode, TextNode, Node } from "./html.js";
export { MarkdownConverter, convertToMarkdown } from "./markdown.js";
export type { MarkdownOptions } from "./markdown.js";
export { MarkdownSanitizer } from "./sanitizer.js";
