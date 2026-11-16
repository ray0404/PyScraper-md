/**
 * local-files.test.ts — mirrors tests/test_local_files.py (Python suite).
 */
import { test, expect } from "bun:test";
import { Scraper } from "../src/scraper.js";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

function tmpFile(name: string, content: string): string {
  const dir = mkdtempSync(join(tmpdir(), "ts-local-"));
  const p = join(dir, name);
  writeFileSync(p, content, "utf-8");
  return p;
}

test("scrape local HTML file", async () => {
  const p = tmpFile(
    "test.html",
    "<html><body><h1>Local HTML</h1></body></html>",
  );
  const result = await new Scraper().scrape(p);
  expect(result.markdown).toContain("Local HTML");
  expect(result.metadata.title).toBeNull();
});

test("scrape local MHT file", async () => {
  const p = tmpFile(
    "test.mht",
    'MIME-Version: 1.0\n' +
      'Content-Type: multipart/related; boundary="boundary"\n\n' +
      "--boundary\n" +
      'Content-Type: text/html; charset="utf-8"\n\n' +
      "<html><body><h1>Local MHT</h1></body></html>\n\n" +
      "--boundary--",
  );
  const result = await new Scraper().scrape(p);
  expect(result.markdown).toContain("Local MHT");
});

test("scrape local MHT file with base64 part", async () => {
  const body = Buffer.from(
    "<html><body><h1>Base64 MHT</h1></body></html>",
    "utf-8",
  ).toString("base64");
  const p = tmpFile(
    "test.mht",
    'MIME-Version: 1.0\n' +
      'Content-Type: multipart/related; boundary="b"\n\n' +
      "--b\n" +
      'Content-Type: text/html; charset="utf-8"\n' +
      "Content-Transfer-Encoding: base64\n\n" +
      `${body}\n\n` +
      "--b--",
  );
  const result = await new Scraper().scrape(p);
  expect(result.markdown).toContain("Base64 MHT");
});

test("scrape missing local file raises", async () => {
  await expect(new Scraper().scrape("non_existent_file.html")).rejects.toThrow();
});

test("scrape .htm file", async () => {
  const p = tmpFile(
    "page.htm",
    "<html><head><title>HTM</title></head><body><main><p>HTM body.</p></main></body></html>",
  );
  const result = await new Scraper().scrape(p);
  expect(result.markdown).toContain("HTM body.");
  expect(result.metadata.title).toBe("HTM");
});
