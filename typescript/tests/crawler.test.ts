/**
 * crawler.test.ts — mirrors tests/test_crawler_logic.py (Python suite).
 */
import { describe, test, expect } from "bun:test";
import { Crawler } from "../src/scraper.js";

test("queue order is FIFO", () => {
  const crawler = new Crawler([
    "https://example.com/1",
    "https://example.com/2",
  ]);
  expect(crawler.queueLength).toBe(2);
  expect(crawler.next()).toEqual({ url: "https://example.com/1", depth: 0 });
  expect(crawler.next()).toEqual({ url: "https://example.com/2", depth: 0 });
  expect(crawler.hasNext()).toBe(false);
  expect(crawler.next()).toBeNull();
});

test("add_links appends to the queue", () => {
  const crawler = new Crawler(["https://example.com"]);
  crawler.next();
  crawler.addLinks(
    ["https://example.com/child1", "https://example.com/child2"],
    0,
  );
  expect(crawler.queueLength).toBe(2);
  expect(crawler.next()).toEqual({
    url: "https://example.com/child1",
    depth: 1,
  });
  expect(crawler.next()).toEqual({
    url: "https://example.com/child2",
    depth: 1,
  });
});

test("max_depth is enforced", () => {
  const crawler = new Crawler(["https://example.com"], { maxDepth: 1 });
  crawler.next();
  crawler.addLinks(["https://example.com/child"], 0);
  expect(crawler.queueLength).toBe(1);
  const child = crawler.next();
  expect(child?.depth).toBe(1);
  crawler.addLinks(["https://example.com/grandchild"], 1);
  expect(crawler.queueLength).toBe(0);
});

test("max_pages stops the crawl", () => {
  const crawler = new Crawler(["https://example.com"], { maxPages: 2 });
  crawler.next();
  crawler.addLinks(["https://example.com/2"], 0);
  crawler.next();
  crawler.addLinks(["https://example.com/3"], 1);
  expect(crawler.crawledCount).toBe(2);
  expect(crawler.hasNext()).toBe(false);
  expect(crawler.next()).toBeNull();
});

test("visited links are not re-added", () => {
  const crawler = new Crawler(["https://example.com"]);
  crawler.next();
  crawler.addLinks(["https://example.com/child"], 0);
  expect(crawler.queueLength).toBe(1);
  crawler.next();
  crawler.addLinks(["https://example.com/child"], 0);
  expect(crawler.queueLength).toBe(0);
});

test("same-domain filtering", () => {
  const crawler = new Crawler(["https://example.com"], { sameDomain: true });
  crawler.next();
  crawler.addLinks(["https://example.com/ok", "https://other.com/no"], 0);
  expect(crawler.queueLength).toBe(1);
  expect(crawler.next()?.url).toBe("https://example.com/ok");
});

test("subpath filtering", () => {
  const startUrl = "https://example.com/docs";
  const crawler = new Crawler([startUrl], { onlySubpaths: true });
  crawler.next();
  crawler.addLinks(
    [
      "https://example.com/docs/page1",
      "https://example.com/other",
      "https://example.com/docs",
    ],
    0,
  );
  expect(crawler.queueLength).toBe(1);
  expect(crawler.next()?.url).toBe("https://example.com/docs/page1");
});

test("iterates with for..of", () => {
  const crawler = new Crawler(["https://example.com/a"], { maxPages: 1 });
  const seen: string[] = [];
  for (const item of crawler) seen.push(item.url);
  expect(seen).toEqual(["https://example.com/a"]);
});
