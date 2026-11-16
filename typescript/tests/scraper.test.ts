/**
 * scraper.test.ts — mirrors tests/test_scraper.py (Python suite).
 * Network is stubbed via the injectable fetch implementation; no real
 * HTTP requests happen here.
 */
import { describe, test, expect } from "bun:test";
import {
  Scraper,
  type ScrapeResult,
} from "../src/scraper.js";
import { parseHtml, serialize, findFirstByTag } from "../src/html.js";

function stubFetch(
  handler: (url: string, init?: RequestInit) => Response | Promise<Response>,
): typeof fetch {
  return ((url: string | URL | Request, init?: RequestInit) => {
    const u = typeof url === "string" ? url : url.toString();
    return Promise.resolve(handler(u, init));
  }) as typeof fetch;
}

function textResponse(text: string, status = 200): Response {
  return new Response(text, {
    status,
    headers: { "Content-Type": "text/html" },
  });
}

test("fetch_html success", async () => {
  const html = "<html><body><h1>Example</h1></body></html>";
  let seenUrl = "";
  const scraper = new Scraper({
    fetchImpl: stubFetch((url) => {
      seenUrl = url;
      return textResponse(html);
    }),
  });
  const result = await scraper.fetchHtml("https://example.com");
  expect(seenUrl).toBe("https://example.com");
  expect(result).toBe(html);
});

test("fetch_html failure raises on 404", async () => {
  const scraper = new Scraper({
    retries: 0,
    fetchImpl: stubFetch(() => textResponse("nope", 404)),
  });
  await expect(scraper.fetchHtml("https://example.com/404")).rejects.toThrow(
    /404/,
  );
});

test("fetch_html retries on 503 then succeeds", async () => {
  let calls = 0;
  const scraper = new Scraper({
    retries: 2,
    fetchImpl: stubFetch(() => {
      calls += 1;
      return calls === 1
        ? textResponse("down", 503)
        : textResponse("<html><body>Success</body></html>");
    }),
  });
  const result = await scraper.fetchHtml("https://example.com/retry");
  expect(result).toBe("<html><body>Success</body></html>");
  expect(calls).toBe(2);
});

test("fetch_html proxy and user agent", async () => {
  let seenHeaders: Record<string, string> = {};
  let seenProxy: string | undefined;
  const scraper = new Scraper({
    proxy: "http://127.0.0.1:8080",
    userAgent: "CustomAgent/1.0",
    retries: 0,
    fetchImpl: stubFetch((_url, init) => {
      seenHeaders = (init?.headers ?? {}) as Record<string, string>;
      seenProxy = process.env.http_proxy;
      return textResponse("<html><body><p>Proxy test</p></body></html>");
    }),
  });
  const result = await scraper.fetchHtml("https://example.com");
  expect(result).toContain("Proxy test");
  expect(seenHeaders["User-Agent"]).toBe("CustomAgent/1.0");
  expect(seenProxy).toBe("http://127.0.0.1:8080");
  expect(process.env.http_proxy).not.toBe("http://127.0.0.1:8080");
});

test("random user agent comes from the default list", () => {
  const scraper = new Scraper({ userAgent: "random" });
  expect(Scraper.DEFAULT_USER_AGENTS).toContain(scraper.getUserAgent());
});

test("extract_main_content removes nav/footer, keeps main", () => {
  const scraper = new Scraper();
  const html = `<html><body><nav>Navigation</nav><main><article>
    <h1>Title</h1><p>Main content here.</p></article></main>
    <footer>Footer</footer></body></html>`;
  const extracted = scraper.extractMainContent(html) as string;
  expect(extracted).toContain("Main content here.");
  expect(extracted).not.toContain("Navigation");
  expect(extracted).not.toContain("Footer");
});

test("extract_main_content falls back to div.content", () => {
  const scraper = new Scraper();
  const html = `<html><body><div class="nav">Nav</div>
    <div class="content"><h1>Title</h1><p>Content in div.content</p></div>
    <div class="footer">Foot</div></body></html>`;
  const extracted = scraper.extractMainContent(html) as string;
  expect(extracted).toContain("Content in div.content");
  expect(extracted).not.toContain("Nav");
  expect(extracted).not.toContain("Foot");
});

test("extract_main_content with no body keeps the fragment", () => {
  const scraper = new Scraper();
  const extracted = scraper.extractMainContent("<h1>Minimal</h1>") as string;
  expect(extracted).toContain("<h1>Minimal</h1>");
});

test("extract_metadata from OpenGraph", () => {
  const scraper = new Scraper();
  const html = `<html><head>
    <meta property="og:title" content="OG Title">
    <meta property="og:description" content="OG Description">
    <meta name="author" content="OG Author"></head><body></body></html>`;
  const metadata = scraper.extractMetadata(html);
  expect(metadata.title).toBe("OG Title");
  expect(metadata.description).toBe("OG Description");
  expect(metadata.author).toBe("OG Author");
});

test("extract_metadata falls back to <title>", () => {
  const scraper = new Scraper();
  const html = `<html><head><title>Standard Title</title>
    <meta name="description" content="Standard Description"></head>
    <body></body></html>`;
  const metadata = scraper.extractMetadata(html);
  expect(metadata.title).toBe("Standard Title");
  expect(metadata.description).toBe("Standard Description");
});

test("extract_metadata from JSON-LD", () => {
  const scraper = new Scraper();
  const html = `<html><head><script type="application/ld+json">
    {"@context": "https://schema.org", "@type": "NewsArticle",
     "headline": "JSON-LD Title", "datePublished": "2023-10-27T12:00:00Z",
     "author": {"@type": "Person", "name": "JSON-LD Author"}}
    </script></head><body></body></html>`;
  const metadata = scraper.extractMetadata(html);
  expect(metadata.title).toBe("JSON-LD Title");
  expect(metadata.author).toBe("JSON-LD Author");
  expect(metadata.date).toBe("2023-10-27T12:00:00Z");
});

test("extract_metadata JSON-LD list author takes the first", () => {
  const scraper = new Scraper();
  const html = `<html><head><script type="application/ld+json">
    {"author": [{"@type": "Person", "name": "Author 1"},
                 {"@type": "Person", "name": "Author 2"}]}
    </script></head><body></body></html>`;
  expect(scraper.extractMetadata(html).author).toBe("Author 1");
});

test("extract_metadata ignores invalid JSON-LD", () => {
  const scraper = new Scraper();
  const html = `<html><head><script type="application/ld+json">
    { invalid json }</script></head><body></body></html>`;
  expect(scraper.extractMetadata(html).title).toBeNull();
});

test("to_markdown basic", async () => {
  const scraper = new Scraper();
  const markdown = await scraper.toMarkdown(
    "<h1>Title</h1><p>Paragraph with <strong>bold</strong> text.</p>",
  );
  expect(markdown).toContain("# Title");
  expect(markdown).toContain("Paragraph with **bold** text.");
});

test("to_markdown GFM table and code block", async () => {
  const scraper = new Scraper();
  const markdown = await scraper.toMarkdown(
    `<table><tr><th>Header</th></tr><tr><td>Data</td></tr></table>
     <pre><code>print("hello")</code></pre>`,
  );
  expect(markdown).toContain("| Header |");
  expect(markdown).toContain("```");
  expect(markdown).toContain('print("hello")');
});

test("to_markdown strip options", async () => {
  const scraper = new Scraper();
  const html =
    '<p>Check <a href="https://example.com">this link</a> and <img src="img.png" alt="image"></p>';
  const noLinks = await scraper.toMarkdown(html, { strip: ["a"] });
  expect(noLinks).toContain("this link");
  expect(noLinks).not.toContain("https://example.com");
  const noImages = await scraper.toMarkdown(html, { strip: ["img"] });
  expect(noImages).not.toContain("image");
  expect(noImages).toContain("this link");
});

test("to_markdown svg as base64 image", async () => {
  const scraper = new Scraper();
  const markdown = await scraper.toMarkdown(
    '<svg width="10" height="10"><circle r="5" /></svg>',
    { svgAction: "image" },
  );
  expect(markdown).toContain("![svg image](data:image/svg+xml;base64,");
});

test("to_markdown svg preserve", async () => {
  const scraper = new Scraper();
  const markdown = await scraper.toMarkdown(
    '<svg width="10" height="10"><circle r="5" /></svg>',
    { svgAction: "preserve" },
  );
  expect(markdown).toContain("<svg");
  expect(markdown).toContain("<circle");
});

test("to_markdown svg strip", async () => {
  const scraper = new Scraper();
  const markdown = await scraper.toMarkdown(
    '<p>Text</p><svg width="10" height="10"><circle r="5" /></svg>',
    { svgAction: "strip" },
  );
  expect(markdown).not.toContain("<svg");
  expect(markdown).toContain("Text");
});

test("to_markdown svg static fallback fills viewBox dims and color", async () => {
  const scraper = new Scraper();
  const markdown = await scraper.toMarkdown(
    '<svg viewBox="0 0 24 24" fill="currentColor"><path d="..."/></svg>',
    { svgAction: "image" },
  );
  const match = /data:image\/svg\+xml;base64,([^"\)]+)/.exec(markdown);
  expect(match).not.toBeNull();
  const decoded = Buffer.from(match![1], "base64").toString("utf-8");
  expect(decoded).toContain('fill="#000000"');
  expect(decoded).toContain('width="24"');
  expect(decoded).toContain('height="24"');
});

test("to_markdown image base64", async () => {
  const scraper = new Scraper({
    fetchImpl: stubFetch(() => {
      return new Response("fake image data", {
        status: 200,
        headers: { "Content-Type": "image/png" },
      });
    }),
  });
  const markdown = await scraper.toMarkdown(
    '<img src="https://example.com/test.png">',
    { imageAction: "base64" },
  );
  expect(markdown).toContain("data:image/png;base64,");
  expect(markdown).toContain(Buffer.from("fake image data").toString("base64"));
});

test("to_markdown image file writes the asset", async () => {
  const assetsDir = `${import.meta.dir}/../.tmp-test-assets`;
  const scraper = new Scraper({
    fetchImpl: stubFetch(() => {
      return new Response("fake data", { status: 200 });
    }),
  });
  const markdown = await scraper.toMarkdown(
    '<img src="https://example.com/test.png">',
    { imageAction: "file", assetsDir },
  );
  expect(markdown).toContain("assets/image_0.png");
  const written = await Bun.file(`${assetsDir}/image_0.png`).text();
  expect(written).toBe("fake data");
  const { rmSync } = await import("node:fs");
  rmSync(`${import.meta.dir}/../.tmp-test-assets`, { recursive: true, force: true });
});

test("scrape orchestration with stubbed fetch", async () => {
  const html = `<html><head><title>Test Article</title></head><body>
    <main><h1>Test Article</h1><p>Content.</p></main></body></html>`;
  const scraper = new Scraper({
    fetchImpl: stubFetch(() => textResponse(html)),
  });
  const result: ScrapeResult = await scraper.scrape(
    "https://example.com/article",
  );
  expect(result.metadata.title).toBe("Test Article");
  expect(result.markdown).toContain("# Test Article");
  expect(result.markdown).toContain("Content.");
  expect(result.url).toBe("https://example.com/article");
  expect(result.raw_html).toBe(html);
});

test("scrape sample blog fixture", async () => {
  const html = await Bun.file(
    `${import.meta.dir}/fixtures/blog_post.html`,
  ).text();
  const scraper = new Scraper({
    fetchImpl: stubFetch(() => textResponse(html)),
  });
  const result = await scraper.scrape("https://example.com/blog/sample");
  expect(result.metadata.title).toBe("Sample Blog Post");
  expect(result.metadata.author).toBe("John Doe");
  expect(result.markdown).toContain("This is the **main content**");
  expect(result.markdown).toContain("## Subheading");
  expect(result.markdown).toContain("- Item 1");
  expect(result.markdown).not.toContain("Home");
  expect(result.markdown).not.toContain("©");
});

test("extract_main_content strips GitHub chrome", () => {
  const scraper = new Scraper();
  const html = `<html><body>
    <div class="js-header-wrapper">GitHub Header</div>
    <main><div id="repository-container-header">Repo Nav / Star / Fork</div>
    <div class="Layout-sidebar">Sidebar content / Stars 0</div>
    <article class="markdown-body"><h1>Jref - JSON Reference CLI</h1>
    <p>Lightweight tool.</p></article></main></body></html>`;
  const extracted = scraper.extractMainContent(html) as string;
  expect(extracted).toContain("Jref - JSON Reference CLI");
  expect(extracted).not.toContain("GitHub Header");
  expect(extracted).not.toContain("Sidebar content");
  expect(extracted).not.toContain("Repo Nav");
});

test("extract_main_content prefers <main> over partial id matches", () => {
  const scraper = new Scraper();
  const html = `<html><body><main>
    <div id="user-query-content-0" class="query-content">Short initial query</div>
    <div class="chat-container"><p>Full conversation content with comprehensive answer and details.</p></div>
    </main></body></html>`;
  const extracted = scraper.extractMainContent(html) as string;
  expect(extracted).toContain("Full conversation content with comprehensive answer");
  expect(extracted).toContain("Short initial query");
});

describe("detectCodeLanguage", () => {
  test("bash for shell commands", () => {
    const scraper = new Scraper();
    const doc = parseHtml(
      "<pre><code># From source\nnpm install\nnpm run build</code></pre>",
    );
    const code = findFirstByTag(doc, "code")!;
    expect(scraper.detectCodeLanguage(code)).toBe("bash");
  });

  test("python for def/import", () => {
    const scraper = new Scraper();
    const doc = parseHtml(
      "<pre><code>def f(x):\n    import os\n    return x</code></pre>",
    );
    expect(scraper.detectCodeLanguage(findFirstByTag(doc, "code")!)).toBe(
      "python",
    );
  });

  test("javascript for const/arrow", () => {
    const scraper = new Scraper();
    const doc = parseHtml(
      "<pre><code>const f = (x) => x + 1;</code></pre>",
    );
    expect(scraper.detectCodeLanguage(findFirstByTag(doc, "code")!)).toBe(
      "javascript",
    );
  });

  test("html for paired tags in the code text", () => {
    const scraper = new Scraper();
    const doc = parseHtml(
      "<pre><code>&lt;div class=\"x\"&gt;hi&lt;/div&gt;</code></pre>",
    );
    expect(scraper.detectCodeLanguage(findFirstByTag(doc, "code")!)).toBe(
      "html",
    );
  });

  test("css for rules", () => {
    const scraper = new Scraper();
    const doc = parseHtml(
      "<pre><code>.foo { color: red; }\n.bar { margin: 0; }</code></pre>",
    );
    expect(scraper.detectCodeLanguage(findFirstByTag(doc, "code")!)).toBe(
      "css",
    );
  });

  test("json for objects", () => {
    const scraper = new Scraper();
    const doc = parseHtml('<pre><code>{"a": 1, "b": 2}</code></pre>');
    expect(scraper.detectCodeLanguage(findFirstByTag(doc, "code")!)).toBe(
      "json",
    );
  });

  test("json-looking text with an array literal reads as javascript (Python does the same)", () => {
    const scraper = new Scraper();
    const doc = parseHtml('<pre><code>{"a": 1, "b": [2]}</code></pre>');
    expect(scraper.detectCodeLanguage(findFirstByTag(doc, "code")!)).toBe(
      "javascript",
    );
  });

  test("sql for SELECT", () => {
    const scraper = new Scraper();
    const doc = parseHtml(
      "<pre><code>SELECT id FROM users WHERE active = 1</code></pre>",
    );
    expect(scraper.detectCodeLanguage(findFirstByTag(doc, "code")!)).toBe(
      "sql",
    );
  });

  test("language-* class wins", () => {
    const scraper = new Scraper();
    const doc = parseHtml(
      '<pre class="language-rust"><code>fn main() {}</code></pre>',
    );
    expect(scraper.detectCodeLanguage(findFirstByTag(doc, "pre")!)).toBe(
      "rust",
    );
  });
});

test("html serialization matches lxml rules", () => {
  // Attributes sort alphabetically; void elements self-close; text escapes.
  const doc = parseHtml(
    '<p>a > b & c</p><img src="x.png" alt="a&b"><input disabled>',
  );
  const body = findFirstByTag(doc, "body")!;
  expect(serialize(body)).toBe(
    '<body><p>a &gt; b &amp; c</p><img alt="a&amp;b" src="x.png"/><input disabled=""/></body>',
  );
});

test("parser honours implied end tags", () => {
  const doc = parseHtml("<ul><li>one<li>two</ul><p>one<p>two");
  const body = findFirstByTag(doc, "body")!;
  expect(serialize(body)).toBe(
    "<body><ul><li>one</li><li>two</li></ul><p>one</p><p>two</p></body>",
  );
});
