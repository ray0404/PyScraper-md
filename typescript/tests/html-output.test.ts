/**
 * html-output.test.ts — mirrors tests/test_html_output.py (Python suite):
 * scrape() keys, html/markdown equivalence, wrap_html_document,
 * select_output, and the CLI --format surface.
 */
import { describe, test, expect } from "bun:test";
import { Scraper, selectOutput, wrapHtmlDocument } from "../src/scraper.js";
import { parseHtml, textContent } from "../src/html.js";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const SAMPLE_URL = "https://example.com/blog/sample";

async function sampleHtml(): Promise<string> {
  return Bun.file(`${import.meta.dir}/fixtures/blog_post.html`).text();
}

function textOf(html: string): string {
  return textContent(parseHtml(html)).split(/\s+/).join(" ").trim();
}

function runCli(args: string[]): { code: number; stdout: string; stderr: string } {
  const proc = spawnSync("bun", ["run", "src/cli.ts", ...args], {
    cwd: `${import.meta.dir}/..`,
    encoding: "utf-8",
  });
  return {
    code: proc.status ?? -1,
    stdout: proc.stdout ?? "",
    stderr: proc.stderr ?? "",
  };
}

describe("library: scrape() result keys", () => {
  test("returns html and raw_html", async () => {
    const html = await sampleHtml();
    const scraper = new Scraper({
      fetchImpl: (async () => new Response(html)) as typeof fetch,
    });
    const result = await scraper.scrape(SAMPLE_URL);
    expect(result.raw_html).toBe(html);
    expect(result.raw_html).toContain("<nav>");
    expect(result.raw_html).toContain("Home");
    expect(result.raw_html).toContain("<footer>");
    expect(result.html).toContain("<main>");
    expect(result.html).toContain("Sample Blog Post");
    expect(result.html).toContain("main content");
    expect(result.html).not.toContain("<nav>");
    expect(result.html).not.toContain("Home");
    expect(result.html).not.toContain("<footer>");
    expect(result.html).not.toContain("2023 Sample Blog");
  });

  test("html is the content-equivalent of markdown", async () => {
    const html = await sampleHtml();
    const scraper = new Scraper({
      fetchImpl: (async () => new Response(html)) as typeof fetch,
    });
    const result = await scraper.scrape(SAMPLE_URL);
    expect(result.markdown).toContain("# Sample Blog Post");
    expect(result.html).toContain("<h1>Sample Blog Post</h1>");
    expect(result.markdown).toContain("## Subheading");
    expect(result.html).toContain("<h2>Subheading</h2>");
    expect(result.markdown).toContain("- Item 1");
    expect(result.html).toContain("<li>Item 1</li>");
    expect(result.markdown).toContain("This is the **main content**");
    expect(result.html).toContain("<strong>main content</strong>");
  });

  test("html and markdown carry the same visible text", async () => {
    const html = await sampleHtml();
    const scraper = new Scraper({
      fetchImpl: (async () => new Response(html)) as typeof fetch,
    });
    const result = await scraper.scrape(SAMPLE_URL);
    const htmlText = textOf(result.html);
    const mdText = result.markdown
      .replace(/#/g, "")
      .replace(/\*/g, "")
      .replace(/-/g, "")
      .split(/\s+/)
      .join(" ")
      .trim();
    expect(htmlText).toBe(mdText);
  });
});

describe("library: SVG / image actions apply to HTML exactly as to Markdown", () => {
  test("svg as image in both outputs", async () => {
    const scraper = new Scraper();
    const html = '<svg width="10" height="10"><circle r="5" /></svg>';
    const markdown = await scraper.toMarkdown(html, { svgAction: "image" });
    const htmlOut = await scraper.toHtml(html, { svgAction: "image" });
    expect(markdown).toContain("data:image/svg+xml;base64,");
    expect(htmlOut).toContain("data:image/svg+xml;base64,");
    expect(htmlOut).not.toContain("<svg");
  });

  test("svg strip and preserve in HTML", async () => {
    const scraper = new Scraper();
    const html = '<p>Text</p><svg width="10" height="10"><circle r="5" /></svg>';
    const stripped = await scraper.toHtml(html, { svgAction: "strip" });
    expect(stripped).not.toContain("<svg");
    expect(stripped).toContain("Text");
    const preserved = await scraper.toHtml(html, { svgAction: "preserve" });
    expect(preserved).toContain("<svg");
    expect(preserved).toContain("<circle");
  });

  test("to_html converts what it is given; it does not extract main content", async () => {
    const scraper = new Scraper();
    const out = await scraper.toHtml(
      "<h1>Title</h1><p>Paragraph with <strong>bold</strong> text.</p>",
    );
    expect(out).toContain("<h1>Title</h1>");
    expect(out).toContain("<strong>bold</strong>");
    expect(
      await scraper.toHtml("<nav>Nav</nav><main><p>Main</p></main>"),
    ).toContain("<nav>Nav</nav>");
  });

  test("content_html fallback extraction", () => {
    const scraper = new Scraper();
    return sampleHtml().then((html) => {
      const out = scraper.contentHtml(html);
      expect(out).toContain("<main>");
      expect(out).toContain("Sample Blog Post");
      expect(out).not.toContain("<nav>");
      expect(out).not.toContain("Home");
    });
  });

  test("strip matches in both outputs", async () => {
    const scraper = new Scraper();
    const html =
      '<p>Check <a href="https://example.com">this link</a> and <img src="img.png" alt="image"></p>';
    const markdown = await scraper.toMarkdown(html, { strip: ["a", "img"] });
    const htmlOut = await scraper.toHtml(html, { strip: ["a", "img"] });
    expect(markdown).toContain("this link");
    expect(markdown).not.toContain("https://example.com");
    expect(htmlOut).toContain("this link");
    expect(htmlOut).not.toContain("<a");
    expect(htmlOut).not.toContain("https://example.com");
    expect(htmlOut).not.toContain("<img");
    expect(htmlOut).not.toContain("img.png");
  });
});

describe("select_output", () => {
  test("all four formats", () => {
    const result = {
      markdown: "# Title",
      html: "<main><h1>Title</h1></main>",
      raw_html: "<html><body><main><h1>Title</h1></main></body></html>",
    };
    expect(selectOutput(result, "markdown")).toEqual(["# Title", ".md"]);
    expect(selectOutput(result, "html")).toEqual([
      "<main><h1>Title</h1></main>",
      ".html",
    ]);
    expect(selectOutput(result, "html-raw")).toEqual([
      "<html><body><main><h1>Title</h1></main></body></html>",
      ".html",
    ]);
    expect(selectOutput(result, "bogus")).toEqual(["# Title", ".md"]);
  });

  test("falls back for old results without an html key", async () => {
    const html = await sampleHtml();
    const result = { markdown: "# Title", raw_html: html };
    const [content, ext] = selectOutput(result, "html");
    expect(ext).toBe(".html");
    expect(content).toContain("<main>");
    expect(content).toContain("Sample Blog Post");
    expect(content).not.toContain("Home");
  });
});

describe("wrapHtmlDocument", () => {
  test("structure", () => {
    const doc = Scraper.wrapHtmlDocument(
      "<main><h1>Title</h1><p>Text.</p></main>",
      {
        title: "My Page",
        sourceUrl: "https://example.com/article",
        metadata: { author: "Jane", description: "A page." },
      },
    );
    expect(doc.startsWith("<!DOCTYPE html>\n<html lang=\"en\">")).toBe(true);
    expect(doc).toContain('<meta charset="utf-8">');
    expect(doc).toContain(
      '<meta name="viewport" content="width=device-width, initial-scale=1">',
    );
    expect(doc).toContain("<title>My Page</title>");
    expect(doc).toContain('<meta name="author" content="Jane">');
    expect(doc).toContain('<meta name="description" content="A page.">');
    expect(doc).toContain('<base href="https://example.com/article">');
    expect(doc).toContain(
      '<link rel="canonical" href="https://example.com/article">',
    );
    expect(doc).toContain("<style>");
    expect(doc).toContain("max-width: 800px");
    expect(doc).toContain(".scraped-source");
    expect(doc).toContain("<main><h1>Title</h1><p>Text.</p></main>");
    expect(doc).toContain(
      "<!-- Scraped from https://example.com/article by md-scraper -->",
    );
    expect(doc).toContain(
      '<p class="scraped-source">Source: <a href="https://example.com/article">https://example.com/article</a></p>',
    );
    expect(doc.indexOf("scraped-source")).toBeLessThan(doc.indexOf("<main>"));
    expect(doc.trimEnd().endsWith("</html>")).toBe(true);
    expect(doc.match(/<body>/g)?.length).toBe(1);
    expect(doc.match(/<\/body>/g)?.length).toBe(1);
  });

  test("escapes title and meta", () => {
    const doc = Scraper.wrapHtmlDocument("<p>x</p>", {
      title: '<b>Bold</b> & "quoted"',
    });
    expect(doc).toContain(
      "<title>&lt;b&gt;Bold&lt;/b&gt; &amp; &quot;quoted&quot;</title>",
    );
    expect(doc.split("<body>")[0]).not.toContain("<b>Bold</b>");
  });

  test("title fallbacks", () => {
    expect(
      Scraper.wrapHtmlDocument("<p>x</p>", {
        sourceUrl: "https://example.com/x",
      }),
    ).toContain("<title>https://example.com/x</title>");
    expect(Scraper.wrapHtmlDocument("<p>x</p>")).toContain(
      "<title>Scraped Page</title>",
    );
  });

  test("no base for local sources; plain-text source line", () => {
    const doc = Scraper.wrapHtmlDocument("<p>x</p>", {
      title: "Local",
      sourceUrl: "/tmp/page.html",
    });
    expect(doc).not.toContain("<base");
    expect(doc).not.toContain('rel="canonical"');
    const doc2 = Scraper.wrapHtmlDocument("<p>x</p>", {
      title: "Local",
      sourceUrl: "/tmp/a&b.html",
    });
    expect(doc2).toContain(
      '<p class="scraped-source">Source: /tmp/a&amp;b.html</p>',
    );
    expect(doc2).not.toContain("<a href");
  });

  test("no source line without a URL", () => {
    const doc = Scraper.wrapHtmlDocument("<p>x</p>", { title: "T" });
    expect(doc).not.toContain('<p class="scraped-source">');
  });

  test("include_base false keeps the canonical link", () => {
    const doc = Scraper.wrapHtmlDocument("<p>x</p>", {
      title: "T",
      sourceUrl: "https://example.com/x",
      includeBase: false,
    });
    expect(doc).not.toContain("<base");
    expect(doc).toContain(
      '<link rel="canonical" href="https://example.com/x">',
    );
  });

  test("returns full documents unchanged; unwraps body fragments; empty input", () => {
    const full =
      "<!DOCTYPE html>\n<html><head><title>Old</title></head><body><p>x</p></body></html>";
    expect(Scraper.wrapHtmlDocument(full)).toBe(full);
    const full2 = '<html lang="en"><head></head><body><p>x</p></body></html>';
    expect(Scraper.wrapHtmlDocument(full2)).toBe(full2);
    const doc = Scraper.wrapHtmlDocument("<body><p>Inner</p></body>", {
      title: "T",
    });
    expect(doc.match(/<body>/g)?.length).toBe(1);
    expect(doc).toContain("<p>Inner</p>");
    expect(Scraper.wrapHtmlDocument("")).toBe("");
    expect(Scraper.wrapHtmlDocument("   ")).toBe("");
  });

  test("scrape() html_document omits base for file assets", async () => {
    const html = await sampleHtml();
    const dir = mkdtempSync(join(tmpdir(), "ts-assets-"));
    const scraper = new Scraper({
      fetchImpl: (async () => new Response(html)) as typeof fetch,
    });
    const result = await scraper.scrape(SAMPLE_URL, {
      imageAction: "file",
      assetsDir: join(dir, "assets"),
    });
    expect(result.html_document).not.toContain("<base");
    expect(result.html_document.startsWith("<!DOCTYPE html>")).toBe(true);
  });
});

describe("CLI --format (spawned)", () => {
  test("defaults to markdown; html/html-raw select content", async () => {
    const page = join(mkdtempSync(join(tmpdir(), "ts-cli-")), "page.html");
    writeFileSync(
      page,
      "<html><head><title>Local</title></head><body><nav>Nav</nav><main><h1>Local</h1><p>Text.</p></main></body></html>",
    );
    const md = runCli(["scrape", page]);
    expect(md.code).toBe(0);
    expect(md.stdout).toContain("# Local");
    expect(md.stdout).not.toContain("<main>");
    const html = runCli(["scrape", page, "--format", "html"]);
    expect(html.code).toBe(0);
    expect(html.stdout).toContain("<main>");
    expect(html.stdout).toContain("Local");
    expect(html.stdout).not.toContain("Nav");
    const raw = runCli(["scrape", page, "--format", "html-raw"]);
    expect(raw.code).toBe(0);
    expect(raw.stdout).toContain("<nav>Nav</nav>");
    const doc = runCli(["scrape", page, "--format", "html-document"]);
    expect(doc.code).toBe(0);
    expect(doc.stdout.startsWith("<!DOCTYPE html>")).toBe(true);
    expect(doc.stdout).toContain("<title>Local</title>");
    expect(doc.stdout).not.toContain("--- URL:");
    const bad = runCli(["scrape", page, "--format", "pdf"]);
    expect(bad.code).not.toBe(0);
  });

  test("banner modes", async () => {
    const page = join(mkdtempSync(join(tmpdir(), "ts-cli-")), "page.html");
    writeFileSync(page, "<html><body><main><h1>Local</h1></main></body></html>");
    const def = runCli(["scrape", page]);
    expect(def.stdout).toContain(`--- URL: ${page} ---`);
    const none = runCli(["--banner", "none", "scrape", page]);
    expect(none.stdout).not.toContain("--- URL:");
    expect(none.stderr).not.toContain("--- URL:");
    const err = runCli(["--banner", "stderr", "scrape", page]);
    expect(err.stdout).not.toContain("--- URL:");
    expect(err.stderr).toContain(`--- URL: ${page} ---`);
    const bad = runCli(["--banner", "bogus", "scrape", page]);
    expect(bad.code).not.toBe(0);
  });
});
